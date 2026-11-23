import os

from redis import Redis
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker


def setting(name, default):
    return os.environ.get(name, default)


engine = create_engine(
    URL.create(
        'mysql+pymysql', username=setting('MYSQL_USER', 'berth'),
        password=setting('MYSQL_PASSWORD', 'berth_local'),
        host=setting('MYSQL_HOST', 'db'), port=int(setting('MYSQL_PORT', '3306')),
        database=setting('MYSQL_DATABASE', 'berth'), query={'charset': 'utf8mb4'},
    ),
    pool_pre_ping=True,
    isolation_level='READ COMMITTED',
)
Session = sessionmaker(engine, expire_on_commit=False)
queue = Redis.from_url(setting('REDIS_URL', 'redis://redis:6379/0'), socket_connect_timeout=2, socket_timeout=4)
WAKE_QUEUE = 'berth:classify'
