from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DatabaseSession

from .models import Audit, Berth, BerthRequest, RequestState, TideWindow, Tug, TugAssignment
from .schemas import RequestInput, Schedule, TideInput


class Rejected(Exception):
    def __init__(self, code, message, reference, status=409):
        self.code = code
        self.message = message
        self.reference = reference
        self.status = status


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def audit(db, actor, reference, event, note):
    db.add(Audit(actor=actor, reference=reference, event=event, note=note))


def find(db, model, key, *, lock=False):
    row = db.get(model, key, with_for_update=lock)
    if row is None:
        raise Rejected('NOT_FOUND', f'找不到记录 {key}', key, 404)
    return row


def ends(request):
    return request.eta + timedelta(minutes=request.maneuver_minutes)


def add_window(db: DatabaseSession, actor: str, data: TideInput):
    find(db, Berth, data.berth_code, lock=True)
    if db.get(TideWindow, data.code):
        raise Rejected('DUPLICATE_WINDOW', '潮窗编号已发布，请为新通告使用独立编号', data.code)
    window = TideWindow(**data.model_dump())
    db.add(window)
    audit(db, actor, window.code, 'TIDE_PUBLISHED', f'{window.berth_code} · {window.bulletin}')
    return window


def add_request(db: DatabaseSession, actor: str, data: RequestInput):
    find(db, Berth, data.berth_code, lock=True)
    if db.get(BerthRequest, data.code):
        raise Rejected('DUPLICATE_REQUEST', '靠泊申请编号已存在', data.code)
    require_window(db, data.window_code, data.berth_code, data.code)
    request = BerthRequest(state=RequestState.REQUESTED, **data.model_dump())
    db.add(request)
    audit(db, actor, request.code, 'REQUEST_FILED', f'{request.vessel} · {request.window_code}')
    return request


def require_window(db, window_code, berth_code, reference):
    window = find(db, TideWindow, window_code)
    if window.berth_code != berth_code:
        raise Rejected('WRONG_BERTH', '所选潮窗属于另一泊位', reference)
    return window


def require_editable(request):
    if request.state not in (RequestState.REQUESTED, RequestState.TUG_RESERVED):
        raise Rejected('SCHEDULE_FROZEN', '已确认的申请已冻结，请在延误案件处置中记录调整', request.code)


def tide_clearance(request, window):
    reserve = (window.ends_at - ends(request)).total_seconds() / 60
    if request.eta < window.starts_at or reserve < 0:
        return reserve, '潮窗须完全覆盖进港操纵时段'
    if request.draft_m > window.max_draft_m:
        return reserve, f'申请吃水 {request.draft_m:g} m 超过潮窗限值 {window.max_draft_m:g} m'
    return reserve, None


def active_tug(db, code):
    return db.scalar(select(TugAssignment).filter_by(request_code=code, released_at=None))


def revise(db: DatabaseSession, actor: str, code: str, data: Schedule):
    request = find(db, BerthRequest, code, lock=True)
    require_editable(request)
    require_window(db, data.window_code, request.berth_code, code)
    reservation = active_tug(db, code)
    if reservation:
        find(db, Tug, reservation.tug_code, lock=True)
        reservation.released_at = utc_now()
    previous = f'{request.window_code} {request.eta:%m-%d %H:%M}'
    request.window_code = data.window_code
    request.eta = data.eta
    request.maneuver_minutes = data.maneuver_minutes
    request.state = RequestState.REQUESTED
    audit(db, actor, code, 'SCHEDULE_REVISED', f'{previous} → {request.window_code} {request.eta:%m-%d %H:%M}。原拖轮预约已释放（如有）。')
    return request


def conflicting_tug(db, request, tug_code):
    return db.scalar(select(TugAssignment).where(
        TugAssignment.tug_code == tug_code,
        TugAssignment.released_at.is_(None),
        TugAssignment.request_code != request.code,
        TugAssignment.starts_at < ends(request),
        TugAssignment.ends_at > request.eta,
    ).limit(1))


def require_free_tug(db, request, tug_code):
    conflict = conflicting_tug(db, request, tug_code)
    if conflict:
        note = f'{tug_code} 与 {conflict.request_code} 的 {conflict.starts_at:%H:%M}–{conflict.ends_at:%H:%M} 重叠，请换轮或改期'
        raise Rejected('TUG_CONFLICT', note, request.code)


def reserve_tug(db: DatabaseSession, actor: str, code: str, tug_code: str):
    request = find(db, BerthRequest, code, lock=True)
    require_editable(request)
    existing = active_tug(db, code)
    tug_codes = {tug_code}
    if existing:
        tug_codes.add(existing.tug_code)
    for key in sorted(tug_codes):
        find(db, Tug, key, lock=True)
    require_free_tug(db, request, tug_code)
    if existing and existing.tug_code == tug_code:
        return existing
    if existing:
        existing.released_at = utc_now()
    reservation = TugAssignment(tug_code=tug_code, request_code=code, starts_at=request.eta, ends_at=ends(request))
    db.add(reservation)
    request.state = RequestState.TUG_RESERVED
    audit(db, actor, code, 'TUG_RESERVED', f'{tug_code} · {request.eta:%H:%M}–{ends(request):%H:%M}')
    return reservation


def confirm(db: DatabaseSession, actor: str, code: str):
    request = find(db, BerthRequest, code, lock=True)
    require_editable(request)
    # Serialize berth confirmations across different windows for the same physical berth.
    find(db, Berth, request.berth_code, lock=True)
    window = require_window(db, request.window_code, request.berth_code, code)
    reserve, issue = tide_clearance(request, window)
    if issue:
        raise Rejected('INSUFFICIENT_TIDE', issue, code)
    reservation = active_tug(db, code)
    if not reservation or reservation.starts_at != request.eta or reservation.ends_at != ends(request):
        raise Rejected('TUG_REQUIRED', '请为当前时段预约拖轮', code)
    find(db, Tug, reservation.tug_code, lock=True)
    require_free_tug(db, request, reservation.tug_code)
    competing = db.scalars(select(BerthRequest).where(
        BerthRequest.berth_code == request.berth_code,
        BerthRequest.state.in_([RequestState.CONFIRMED, RequestState.COMPLETED]),
        BerthRequest.eta < ends(request),
    ))
    for other in competing:
        if ends(other) > request.eta:
            raise Rejected('BERTH_CONFLICT', f'{request.berth_code} 已有操纵作业 {other.code}', code)
    request.state = RequestState.CONFIRMED
    audit(db, actor, code, 'BERTH_CONFIRMED', f'{window.code} · 余量 {reserve:g} 分钟 · {reservation.tug_code}')
    return request
