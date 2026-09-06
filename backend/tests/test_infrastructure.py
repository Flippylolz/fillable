import io
import os
import subprocess
import uuid
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Queue
from rq.serializers import JSONSerializer
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import worker_config
from app.infrastructure import database, dependencies_ready, queue_connection
from app.main import app


def test_migration_upgrade_repeat_and_preservation():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    with database().begin() as connection:
        connection.execute(
            text("CREATE TABLE IF NOT EXISTS test_persistence (id text PRIMARY KEY)")
        )
        connection.execute(
            text(
                "INSERT INTO test_persistence VALUES ('retained') "
                "ON CONFLICT DO NOTHING"
            )
        )
    command.upgrade(config, "head")
    with database().connect() as connection:
        assert (
            connection.execute(text("SELECT id FROM test_persistence")).scalar()
            == "retained"
        )
    assert dependencies_ready()
    assert TestClient(app).get("/api/ready").json() == {"status": "ok"}
    command.downgrade(config, "base")
    assert not dependencies_ready()
    command.upgrade(config, "head")
    assert dependencies_ready()
    output = io.StringIO()
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    assert "alembic_version" in output.getvalue()


def test_database_and_queue_failures_are_private():
    with patch("app.infrastructure.database") as mocked:
        mocked.return_value.connect.side_effect = OperationalError(
            "private", {}, Exception()
        )
        response = TestClient(app).get("/api/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": {"code": "dependencies_unavailable"}}
    with patch("app.infrastructure.queue_connection") as mocked:
        mocked.return_value.__enter__.return_value.ping.side_effect = (
            RedisConnectionError("private")
        )
        assert not dependencies_ready()


def test_real_json_queue_worker_roundtrip():
    assert worker_config.REDIS_URL == os.environ["REDIS_URL"]
    with queue_connection() as connection:
        queue = Queue(
            worker_config.QUEUES[0], connection=connection, serializer=JSONSerializer
        )
        job = queue.enqueue("builtins.sum", [2, 3], job_id=str(uuid.uuid4()))
        result = subprocess.run(
            [
                "rq",
                "worker",
                "--config",
                "app.worker_config",
                "--serializer",
                "rq.serializers.JSONSerializer",
                "--disable-job-desc-logging",
                "--burst",
            ],
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr.decode()
        job.refresh()
        assert job.is_finished
        assert job.return_value() == 5
        job.delete()
