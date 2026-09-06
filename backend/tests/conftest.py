"""Never run destructive integration fixtures against an application database."""

import os

import pytest
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session", autouse=True)
def require_isolated_database():
    url = make_url(os.environ["DATABASE_URL"])
    if (url.host, url.database, url.password) != ("test-db", "fillable", "test-only"):
        pytest.exit("Use the isolated database from compose.test.yaml", returncode=2)
