import logging
import socket
import time
from datetime import timedelta
from pathlib import Path

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .classifier import classify
from .database import Session, WAKE_QUEUE, queue, setting
from .models import ClassificationRun, DelayClass, DelayIncident, IncidentState, RunOutcome
from .planning import audit, utc_now

log = logging.getLogger(__name__)
heartbeat = Path('/tmp/berth-heartbeat')
SEAT = setting('SEAT_NAME', '') or socket.gethostname()
LEASE = timedelta(minutes=float(setting('RUN_LEASE_MINUTES', '5')))


def claim(db):
    """Sweep stalled runs, then lease the next queued incident to this seat."""
    now = utc_now()
    stalled = db.scalars(select(ClassificationRun).where(
        ClassificationRun.outcome == RunOutcome.COMPUTING,
        ClassificationRun.deadline_at <= now,
    ).with_for_update(skip_locked=True))
    for run in stalled:
        run.outcome = RunOutcome.TIMED_OUT
        run.finished_at = now
        audit(db, 'worker', run.incident_code, 'RUN_TIMED_OUT',
              f'{run.seat} 第 {run.attempt} 次接算超过五分钟未回分，由空闲席接算')
    engaged = select(ClassificationRun.incident_code).where(ClassificationRun.outcome == RunOutcome.COMPUTING)
    incident = db.scalar(select(DelayIncident).where(
        DelayIncident.state == IncidentState.QUEUED,
        DelayIncident.code.not_in(engaged),
    ).order_by(DelayIncident.code).limit(1).with_for_update(skip_locked=True))
    if not incident:
        return None
    incident.attempts += 1
    run = ClassificationRun(incident_code=incident.code, seat=SEAT, attempt=incident.attempts,
                            started_at=now, deadline_at=now + LEASE)
    db.add(run)
    db.flush()
    audit(db, 'worker', incident.code, 'RUN_CLAIMED', f'{SEAT} 第 {run.attempt} 次接算 · {run.deadline_at:%H:%M} 前回分')
    return run.id, incident.code, incident.features, incident.input_digest


def submit(run_id, result=None, error=None):
    """Accept only the score from the seat currently holding the lease; archive late ones."""
    with Session.begin() as db:
        run = db.get(ClassificationRun, run_id, with_for_update=True)
        if not run or run.outcome not in (RunOutcome.COMPUTING, RunOutcome.TIMED_OUT):
            return
        incident = db.get(DelayIncident, run.incident_code, with_for_update=True)
        now = utc_now()
        current = run.outcome == RunOutcome.COMPUTING and now <= run.deadline_at
        run.finished_at = now
        if error is not None:
            run.outcome = RunOutcome.FAILED
            run.error = error[:180]
            if current:
                incident.state = IncidentState.FAILED
                incident.error = run.error
                audit(db, 'worker', incident.code, 'MODEL_FAILED', f'{SEAT} 第 {run.attempt} 次接算失败 · {run.error}')
            else:
                audit(db, 'worker', incident.code, 'RUN_LATE_FAILED', f'{SEAT} 第 {run.attempt} 次超时后回报失败 · {run.error}')
            return
        run.result = result
        if current:
            run.outcome = RunOutcome.ACCEPTED
            incident.result = result
            incident.state = IncidentState.MARGIN_REVIEW if result['needs_review'] else IncidentState.READY
            if incident.state == IncidentState.READY:
                incident.decision = DelayClass(result['prediction'])
            audit(db, 'worker', incident.code, 'RUN_ACCEPTED',
                  f"{SEAT} 第 {run.attempt} 次判分采信 · f(x)={result['score']:+.5f} · {incident.state}")
            log.info('%s %s', incident.code, incident.state)
        else:
            run.outcome = RunOutcome.EXPIRED
            audit(db, 'worker', incident.code, 'RUN_ARCHIVED',
                  f"{SEAT} 第 {run.attempt} 次判分超时到达，留档不采信 · f(x)={result['score']:+.5f}")
            log.info('%s archived expired score from %s', incident.code, SEAT)


def process_next():
    with Session.begin() as db:
        claimed = claim(db)
        if not claimed:
            return False
        run_id, code, features, digest = claimed
    try:
        result = classify(features, digest)
    except Exception as exc:
        log.exception('Classification failed for %s', code)
        submit(run_id, error=str(exc))
    else:
        submit(run_id, result=result)
    return True


def run():
    logging.basicConfig(level=logging.INFO)
    log.info('Classification seat %s · lease %s', SEAT, LEASE)
    while True:
        try:
            processed = process_next()
        except SQLAlchemyError:
            log.exception('Database unavailable')
            time.sleep(2)
            continue
        heartbeat.touch()
        if not processed:
            try:
                queue.brpop(WAKE_QUEUE, timeout=2)
            except RedisError:
                log.warning('Redis unavailable; using durable queue')
                time.sleep(2)


if __name__ == '__main__':
    run()
