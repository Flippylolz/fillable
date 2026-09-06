from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Queue, SimpleWorker
from rq.job import Job
from rq.serializers import JSONSerializer
from sqlalchemy import delete, insert, select, update
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_persistence import DATA, client, upload
from test_document_persistence import document_store as document_store

from app.accounts import service as account_service
from app.accounts.schema import AccountInput, users
from app.documents.schema import resources, versions
from app.infrastructure import database, queue_connection
from app.jobs import dispatcher, service, worker
from app.jobs.schema import jobs
from app.storage.schema import accounts, files
from app.storage.service import now


@pytest.fixture(autouse=True)
def processing_store(document_store):
    with queue_connection() as redis:
        Queue("fillable", connection=redis, serializer=JSONSerializer).empty()
    yield
    with database().begin() as connection:
        connection.execute(delete(jobs))
    with queue_connection() as redis:
        Queue("fillable", connection=redis, serializer=JSONSerializer).empty()


def start():
    owner = account()
    web = client()
    saved = upload(web).json()
    url = "/api/documents/" + saved["id"] + "/processing"
    assert web.get(url).json()["status"] == "not_started"
    result = web.post(url)
    assert result.status_code == 200, result.text
    return owner, web, saved, url, result.json()


def row(identity):
    with database().connect() as connection:
        return (
            connection.execute(select(jobs).where(jobs.c.id == UUID(identity)))
            .mappings()
            .one()
        )


def run_queue():
    with queue_connection() as redis:
        SimpleWorker(["fillable"], connection=redis, serializer=JSONSerializer).work(
            burst=True, logging_level="WARNING"
        )


def test_durable_intent_real_json_queue_owned_status_and_no_file_allocation():
    owner, web, saved, url, job = start()
    assert job["status"] == "queued" and job["attempt"] == 1
    assert web.post(url).json()["id"] == job["id"]
    assert browser().post(url).status_code == 401
    assert web.post(url, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert browser().get(url).status_code == 401
    other = account_service.provision(
        AccountInput(email="other@example.test", display_name="Other"), PASSWORD
    )
    peer = browser()
    login = peer.post(
        "/api/auth/login", json={"email": other.email, "password": PASSWORD}
    )
    peer.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert peer.get(url).status_code == 404 and peer.post(url).status_code == 404
    assert dispatcher.dispatch()["enqueued"] == 1
    assert dispatcher.dispatch()["enqueued"] == 0
    with queue_connection() as redis:
        queued = Job.fetch(
            f"fillable-{job['id']}-1", connection=redis, serializer=JSONSerializer
        )
        assert queued.args == [job["id"], 1]
        assert queued.timeout == worker.JOB_SECONDS
        assert queued.func_name == "app.jobs.worker.process"
    run_queue()
    completed = web.get(url)
    assert completed.headers["cache-control"] == "no-store"
    assert completed.json()["status"] == "succeeded"
    assert completed.json()["summary"]["supported_controls"] > 0
    assert completed.json()["source_version_id"] == saved["current_version_id"]
    assert web.post(url).json()["id"] == job["id"]
    with database().connect() as connection:
        assert len(connection.execute(select(files)).all()) == 1
        assert connection.execute(
            select(accounts.c.used_bytes).where(accounts.c.user_id == owner.id)
        ).scalar_one() == len(DATA)
    with pytest.raises(RuntimeError, match="Processing jobs exist"):
        command.downgrade(Config("alembic.ini"), "0005_documents")


def test_redis_outage_and_lost_queue_are_reconstructed_from_postgres(monkeypatch):
    _, web, _, url, job = start()
    original = Job.fetch
    monkeypatch.setattr(
        Job,
        "fetch",
        lambda *a, **k: (_ for _ in ()).throw(RedisConnectionError("offline")),
    )
    assert dispatcher.dispatch()["failed"] == 1
    assert web.get(url).json()["status"] == "queued"
    monkeypatch.setattr(Job, "fetch", original)
    assert dispatcher.dispatch()["enqueued"] == 1
    with queue_connection() as redis:
        Queue("fillable", connection=redis, serializer=JSONSerializer).empty()
    assert dispatcher.dispatch()["enqueued"] == 1
    run_queue()
    assert row(job["id"])["status"] == "succeeded"


def test_worker_failures_are_bounded_sanitized_and_explicit_retry_is_new_attempt(
    monkeypatch, capsys
):
    _, web, _, url, job = start()
    original = worker.inspect_file
    monkeypatch.setattr(
        worker,
        "inspect_file",
        lambda *a: (_ for _ in ()).throw(RuntimeError("private document text")),
    )
    for attempt in range(1, 4):
        worker.process(job["id"], attempt)
    failed = web.get(url).json()
    assert (
        failed["status"] == "failed" and failed["failure_code"] == "processing_failed"
    )
    assert "private document" not in capsys.readouterr().out
    retried = web.post(url).json()
    assert retried["attempt"] == 4 and retried["id"] == job["id"]
    monkeypatch.setattr(worker, "inspect_file", original)
    worker.process(job["id"], 1)  # Obsolete deliveries cannot claim the retry.
    worker.process(job["id"], 4)
    worker.finish(UUID(job["id"]), 1, {"paragraphs": 999})
    assert web.get(url).json()["status"] == "succeeded"
    assert web.get(url).json()["summary"]["paragraphs"] != 999


def test_expired_worker_leases_retry_then_stop_and_live_leases_are_left_alone():
    _, web, _, url, job = start()
    for attempt in range(1, 4):
        assert worker.claim(UUID(job["id"]), attempt) is not None
        assert dispatcher.dispatch()["examined"] == 0
        with database().begin() as connection:
            connection.execute(
                update(jobs)
                .where(jobs.c.id == UUID(job["id"]))
                .values(lease_until=now() - timedelta(seconds=1))
            )
        worker.finish(UUID(job["id"]), attempt, {"paragraphs": 999})
        assert row(job["id"])["status"] == "running"
        result = dispatcher.dispatch()
        assert result["failed"] == (attempt == 3)
    assert web.get(url).json()["status"] == "failed"


def test_revision_change_and_deletion_fence_claim_and_late_results():
    _, web, saved, url, job = start()
    assert worker.claim(UUID(job["id"]), 1)
    web.delete("/api/documents/" + saved["id"])
    worker.finish(UUID(job["id"]), 1, {"supported_controls": 999})
    assert row(job["id"])["status"] == "stale"
    assert web.get(url).status_code == 404
    other = upload(web, key="second").json()
    other_url = "/api/documents/" + other["id"] + "/processing"
    other_job = web.post(other_url).json()
    with database().begin() as connection:
        current = (
            connection.execute(
                select(versions).where(
                    versions.c.id == UUID(other["current_version_id"])
                )
            )
            .mappings()
            .one()
        )
        new_id = uuid4()
        connection.execute(
            insert(versions).values(
                **{
                    k: current[k]
                    for k in (
                        "document_id",
                        "owner_id",
                        "file_id",
                        "document_model",
                        "unsupported_count",
                    )
                },
                id=new_id,
                number=2,
            )
        )
        connection.execute(
            update(resources)
            .where(resources.c.id == UUID(other["id"]))
            .values(current_version_id=new_id)
        )
    worker.process(other_job["id"], 1)
    assert row(other_job["id"])["status"] == "stale"
    assert web.get(other_url).json()["status"] == "not_started"


def test_concurrent_delivery_runs_one_attempt_and_inactive_owner_cancels(monkeypatch):
    owner, _, _, _, job = start()
    entered, release = Event(), Event()

    def inspect(*args):
        entered.set()
        assert release.wait(5)
        return {"supported_controls": 1}

    monkeypatch.setattr(worker, "inspect_file", inspect)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker.process, job["id"], 1)
        assert entered.wait(5)
        pool.submit(worker.process, job["id"], 1).result(5)
        release.set()
        first.result(5)
    assert row(job["id"])["status"] == "succeeded"
    with database().begin() as connection:
        connection.execute(update(jobs).values(status="queued"))
        connection.execute(
            update(users).where(users.c.id == owner.id).values(active=False)
        )
    worker.process(job["id"], 1)
    assert row(job["id"])["status"] == "stale"


def test_submission_admission_and_dispatch_loop_failures_are_bounded(
    monkeypatch, capsys
):
    _, web, _, _, _ = start()
    for index in range(5):
        saved = upload(web, key=str(index)).json()
        response = web.post("/api/documents/" + saved["id"] + "/processing")
        assert response.status_code == (429 if index == 4 else 200)
    with pytest.raises(ValueError):
        dispatcher.dispatch(101)
    worker.process("bad-id", 1)
    worker.process(str(uuid4()), 1)
    worker.finish(uuid4(), 1, {})
    monkeypatch.setattr(dispatcher, "dispatch", lambda: {"enqueued": 1, "failed": 0})
    dispatcher.main(once=True)
    monkeypatch.setattr(
        dispatcher,
        "dispatch",
        lambda: (_ for _ in ()).throw(RedisConnectionError("private detail")),
    )
    dispatcher.main(once=True)
    assert "private detail" not in capsys.readouterr().out
    state = account_service.read_session(web.cookies.get("fillable_session_v1"))
    web.post("/api/auth/logout")
    from app.errors import AppError

    with pytest.raises(AppError):
        service.submit(state, UUID(saved["id"]))


def test_abandoned_delivery_before_business_claim_is_retried_and_bounded():
    from rq.job import JobStatus

    _, web, _, url, job = start()
    for attempt in range(1, 4):
        assert dispatcher.dispatch()["enqueued"] == 1
        with queue_connection() as redis:
            delivery = Job.fetch(
                f"fillable-{job['id']}-{attempt}",
                connection=redis,
                serializer=JSONSerializer,
            )
            if attempt == 1:
                delivery.started_at = now() - timedelta(
                    seconds=worker.LEASE_SECONDS + 1
                )
                delivery.save()
                delivery.set_status(JobStatus.STARTED)
            else:
                delivery.set_status(JobStatus.FAILED)
        assert dispatcher.dispatch()["failed"] == (attempt == 3)
    assert web.get(url).json()["status"] == "failed"
