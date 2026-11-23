from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, text
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Role(StrEnum):
    OPERATOR = 'operator'
    SUPERVISOR = 'supervisor'
    VIEWER = 'viewer'


class RequestState(StrEnum):
    REQUESTED = 'requested'
    TUG_RESERVED = 'tug_reserved'
    CONFIRMED = 'confirmed'
    COMPLETED = 'completed'


class IncidentState(StrEnum):
    QUEUED = 'queued'
    FAILED = 'failed'
    MARGIN_REVIEW = 'margin_review'
    READY = 'ready'
    ACTIONED = 'actioned'
    CLOSED = 'closed'


class DelayClass(StrEnum):
    ROUTINE = 'routine'
    PRIORITY = 'priority'


class Action(StrEnum):
    MONITOR = 'monitor'
    RETIME = 'retime'
    STANDBY = 'standby'


def enum(kind):
    return Enum(kind, values_callable=lambda members: [member.value for member in members])


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    username = mapped_column(String(32), primary_key=True)
    role = mapped_column(enum(Role), nullable=False)
    password_hash = mapped_column(String(180), nullable=False)


class Berth(Base):
    __tablename__ = 'berths'
    code = mapped_column(String(12), primary_key=True)
    label = mapped_column(String(60), nullable=False)


class TideWindow(Base):
    __tablename__ = 'tide_windows'
    __table_args__ = (CheckConstraint('ends_at > starts_at AND max_draft_m > 0'),)
    code = mapped_column(String(32), primary_key=True)
    berth_code = mapped_column(ForeignKey('berths.code'), nullable=False)
    starts_at = mapped_column(DateTime, nullable=False)
    ends_at = mapped_column(DateTime, nullable=False)
    max_draft_m = mapped_column(Float, nullable=False)
    bulletin = mapped_column(String(120), nullable=False)


class Tug(Base):
    __tablename__ = 'tugs'
    code = mapped_column(String(12), primary_key=True)
    label = mapped_column(String(60), nullable=False)
    bollard_pull_t = mapped_column(Integer, nullable=False)


class BerthRequest(Base):
    __tablename__ = 'berth_requests'
    __table_args__ = (
        CheckConstraint('draft_m > 0 AND maneuver_minutes > 0'),
        Index('berth_schedule_idx', 'berth_code', 'state', 'eta'),
    )
    code = mapped_column(String(32), primary_key=True)
    vessel = mapped_column(String(80), nullable=False)
    berth_code = mapped_column(ForeignKey('berths.code'), nullable=False)
    window_code = mapped_column(ForeignKey('tide_windows.code'), nullable=False)
    eta = mapped_column(DateTime, nullable=False)
    maneuver_minutes = mapped_column(Integer, nullable=False)
    draft_m = mapped_column(Float, nullable=False)
    state = mapped_column(enum(RequestState), nullable=False, default=RequestState.REQUESTED)


class TugAssignment(Base):
    __tablename__ = 'tug_assignments'
    __table_args__ = (
        CheckConstraint('ends_at > starts_at'),
        Index('tug_calendar_idx', 'tug_code', 'released_at', 'starts_at', 'ends_at'),
    )
    id = mapped_column(Integer, primary_key=True)
    request_code = mapped_column(ForeignKey('berth_requests.code'), nullable=False)
    tug_code = mapped_column(ForeignKey('tugs.code'), nullable=False)
    starts_at = mapped_column(DateTime, nullable=False)
    ends_at = mapped_column(DateTime, nullable=False)
    released_at = mapped_column(DateTime)


class DelayIncident(Base):
    __tablename__ = 'delay_incidents'
    code = mapped_column(String(32), primary_key=True)
    request_code = mapped_column(ForeignKey('berth_requests.code'), nullable=False, unique=True)
    radio_reference = mapped_column(String(64), nullable=False, unique=True)
    observed_at = mapped_column(DateTime, nullable=False)
    event_note = mapped_column(String(300), nullable=False)
    state = mapped_column(enum(IncidentState), nullable=False, default=IncidentState.QUEUED, index=True)
    features = mapped_column(JSON, nullable=False)
    input_digest = mapped_column(String(64), nullable=False)
    result = mapped_column(JSON)
    error = mapped_column(String(180))
    attempts = mapped_column(Integer, nullable=False, default=0)
    decision = mapped_column(enum(DelayClass))
    decided_by = mapped_column(ForeignKey('users.username'))
    decision_reason = mapped_column(String(300))
    decided_at = mapped_column(DateTime)


class DispatchReview(Base):
    __tablename__ = 'dispatch_reviews'
    incident_code = mapped_column(ForeignKey('delay_incidents.code'), primary_key=True)
    action = mapped_column(enum(Action), nullable=False)
    instruction = mapped_column(String(300), nullable=False)
    issued_by = mapped_column(ForeignKey('users.username'), nullable=False)
    issued_at = mapped_column(DateTime, nullable=False)
    all_fast_at = mapped_column(DateTime)
    outcome = mapped_column(String(300))
    closed_by = mapped_column(ForeignKey('users.username'))
    closed_at = mapped_column(DateTime)


class Audit(Base):
    __tablename__ = 'audit_events'
    id = mapped_column(Integer, primary_key=True)
    event_at = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    actor = mapped_column(String(32), nullable=False)
    reference = mapped_column(String(100), nullable=False, index=True)
    event = mapped_column(String(48), nullable=False)
    note = mapped_column(String(400), nullable=False)
