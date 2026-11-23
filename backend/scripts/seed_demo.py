from sqlalchemy import func, select

from src.database import Session
from src.incidents import report
from src.models import Audit, Berth, BerthRequest, DelayIncident, DispatchReview, Role, TideWindow, Tug, TugAssignment, User
from src.planning import add_request, add_window, confirm, reserve_tug
from src.schemas import IncidentInput, RequestInput, TideInput
from src.security import password_hash

DEMO_PASSWORD = 'Harbor1074!'


def seed():
    with Session.begin() as db:
        for username, role in [('operator', Role.OPERATOR), ('supervisor', Role.SUPERVISOR), ('viewer', Role.VIEWER)]:
            if not db.get(User, username):
                db.add(User(username=username, role=role, password_hash=password_hash(DEMO_PASSWORD)))
        for code, label in [('B07', '东七码头'), ('B09', '东九散货泊位'), ('B12', '南十二泊位')]:
            if not db.get(Berth, code):
                db.add(Berth(code=code, label=label))
        for code, label, strength in [('TG12', '海勤 12', 58), ('TG18', '海勤 18', 65), ('TG23', '远协 23', 72)]:
            if not db.get(Tug, code):
                db.add(Tug(code=code, label=label, bollard_pull_t=strength))
        for code, berth, start, end, draft in [
            ('TW-071', 'B07', '07:45', '09:10', 11.8), ('TW-072', 'B07', '09:10', '10:45', 13.2),
            ('TW-091', 'B09', '08:30', '11:40', 12.5), ('TW-121', 'B12', '07:25', '12:10', 13.5),
        ]:
            if not db.get(TideWindow, code):
                add_window(db, 'supervisor', TideInput(code=code, berth_code=berth,
                           starts_at=f'2026-11-21T{start}', ends_at=f'2026-11-21T{end}',
                           max_draft_m=draft, bulletin='TIDE-EAST-1121-AM.pdf'))
        db.flush()
        for code, vessel, berth, window, eta, minutes, draft in [
            ('BR-410', '海岚 27', 'B07', 'TW-071', '08:50', 45, 12.4),
            ('BR-411', '临海 308', 'B09', 'TW-091', '09:25', 55, 11.8),
            ('BR-412', '松航 16', 'B12', 'TW-121', '11:00', 45, 12.5),
            ('BR-413', '远桥 75', 'B07', 'TW-072', '09:30', 50, 11.9),
        ]:
            if db.get(BerthRequest, code):
                continue
            add_request(db, 'operator', RequestInput(code=code, vessel=vessel, berth_code=berth, window_code=window,
                        eta=f'2026-11-21T{eta}', maneuver_minutes=minutes, draft_m=draft))
            db.flush()
            if code in ('BR-411', 'BR-413'):
                reserve_tug(db, 'operator', code, 'TG12' if code == 'BR-411' else 'TG18')
                confirm(db, 'supervisor', code)
        if not db.get(DelayIncident, 'DL-413'):
            report(db, 'operator', IncidentInput(code='DL-413', request_code='BR-413',
                   radio_reference='VHF-12/0930-19', observed_at='2026-11-21T09:48', wind_kn=14,
                   tug_wait_min=12, event_note='引航员通报拖轮还在回转区，现场请示是否申请待命。'))
        db.flush()
        tables = (User, Berth, Tug, TideWindow, BerthRequest, TugAssignment, DelayIncident, DispatchReview, Audit)
        return {table.__tablename__: db.scalar(select(func.count()).select_from(table)) for table in tables}


if __name__ == '__main__':
    print(seed())
