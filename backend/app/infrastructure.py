import os
from functools import lru_cache

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


@lru_cache
def database():
    return create_engine(
        os.environ["DATABASE_URL"],
        pool_pre_ping=True,
        connect_args={"connect_timeout": 2},
    )


def queue_connection():
    return Redis.from_url(
        os.environ["REDIS_URL"], socket_connect_timeout=2, socket_timeout=2
    )


def dependencies_ready() -> bool:
    try:
        with database().connect() as connection:
            current = MigrationContext.configure(connection).get_current_heads()
            expected = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
            if set(current) != set(expected):
                return False
        with queue_connection() as connection:
            return bool(connection.ping())
    except (SQLAlchemyError, RedisError):
        return False
