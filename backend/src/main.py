import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from scripts.seed_demo import seed

from .operations_evidence import router as operations_evidence
from .database import Session, engine, queue, setting
from .models import Base
from .planning import Rejected, audit
from .routes import router

log = logging.getLogger('uvicorn.error')


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if setting('SEED_DEMO', 'true').lower() == 'true':
        try:
            log.info('Demo seed %s', seed())
        except Exception:
            log.exception('Demo seed failed')
    yield
    engine.dispose()


app = FastAPI(title='船舶靠泊延误边界分类', lifespan=lifespan)
app.include_router(operations_evidence)
app.include_router(router)


@app.middleware('http')
async def correlate(request: Request, call_next):
    request_id = uuid4().hex
    started = time.perf_counter()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    log.info('%s %s %s %s %.1fms', request_id, request.method, request.url.path,
             response.status_code, (time.perf_counter() - started) * 1000)
    return response


@app.middleware('http')
async def response_policy(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(Rejected)
def business_error(request: Request, exc: Rejected):
    with Session.begin() as db:
        audit(db, getattr(request.state, 'actor', 'system'), exc.reference, exc.code, exc.message)
    return JSONResponse(status_code=exc.status, content={'code': exc.code, 'detail': exc.message})


@app.exception_handler(IntegrityError)
def collision(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={'code': 'RECORD_CONFLICT', 'detail': '记录编号或关联已被占用，请刷新后重试'})


@app.get('/healthz', include_in_schema=False)
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        queue.ping()
    except (SQLAlchemyError, RedisError):
        return JSONResponse(status_code=503, content={'status': 'dependencies_unavailable'})
    return {'status': 'ok'}
