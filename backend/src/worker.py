import logging
import time
from pathlib import Path

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .classifier import classify
from .database import Session, WAKE_QUEUE, queue
from .models import DelayClass, DelayIncident, IncidentState
from .planning import audit

log = logging.getLogger(__name__)
heartbeat = Path('/tmp/berth-heartbeat')


def process_next():
    with Session.begin() as db:
        incident = db.scalar(select(DelayIncident).where(DelayIncident.state == IncidentState.QUEUED)
                             .order_by(DelayIncident.code).limit(1).with_for_update(skip_locked=True))
        if not incident:
            return False
        incident.attempts += 1
        try:
            result = classify(incident.features, incident.input_digest)
        except Exception as exc:
            log.exception('Classification failed for %s', incident.code)
            incident.state = IncidentState.FAILED
            incident.error = str(exc)[:180]
            audit(db, 'worker', incident.code, 'MODEL_FAILED', incident.error)
            return True
        incident.result = result
        incident.state = IncidentState.MARGIN_REVIEW if result['needs_review'] else IncidentState.READY
        if incident.state == IncidentState.READY:
            incident.decision = DelayClass(result['prediction'])
        audit(db, 'worker', incident.code, 'MODEL_CLASSIFIED', f"f(x)={result['score']:+.5f} · {incident.state}")
        log.info('%s %s', incident.code, incident.state)
        return True


def run():
    logging.basicConfig(level=logging.INFO)
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
