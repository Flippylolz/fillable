"""Recoverable, bounded PostgreSQL outbox dispatch; Redis is not the source of truth."""

import json
import time
from datetime import timedelta

from redis.exceptions import RedisError
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job
from rq.serializers import JSONSerializer
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure import database, queue_connection
from app.jobs.schema import jobs
from app.jobs.worker import JOB_SECONDS, LEASE_SECONDS
from app.storage.service import now


def advance(connection, row):
    retry = row["attempt"] < row["retry_until"]
    connection.execute(
        update(jobs)
        .where(jobs.c.id == row["id"])
        .values(
            status="queued" if retry else "failed",
            attempt=row["attempt"] + 1 if retry else row["attempt"],
            failure_code=None if retry else "processing_failed",
            lease_until=None,
            dispatched_at=None,
            updated_at=now(),
        )
    )
    return retry


def dispatch(batch=100):
    if type(batch) is not int or not 1 <= batch <= 100:
        raise ValueError("invalid batch")
    result = {"examined": 0, "enqueued": 0, "failed": 0}
    with database().connect() as connection:
        identities = (
            connection.execute(
                select(jobs.c.id)
                .where(
                    or_(
                        jobs.c.status == "queued",
                        and_(jobs.c.status == "running", jobs.c.lease_until < now()),
                    )
                )
                .order_by(
                    func.coalesce(jobs.c.dispatched_at, jobs.c.created_at), jobs.c.id
                )
                .limit(batch)
            )
            .scalars()
            .all()
        )
    with queue_connection() as redis:
        queue = Queue("fillable", connection=redis, serializer=JSONSerializer)
        for identity in identities:
            result["examined"] += 1
            with database().begin() as connection:
                row = (
                    connection.execute(
                        select(jobs).where(jobs.c.id == identity).with_for_update()
                    )
                    .mappings()
                    .one()
                )
                if row["status"] == "running" and row["lease_until"] < now():
                    if row["attempt"] >= row["retry_until"]:
                        connection.execute(
                            update(jobs)
                            .where(jobs.c.id == identity)
                            .values(
                                status="failed",
                                failure_code="processing_failed",
                                lease_until=None,
                                updated_at=now(),
                            )
                        )
                        result["failed"] += 1
                        continue
                    connection.execute(
                        update(jobs)
                        .where(jobs.c.id == identity)
                        .values(
                            status="queued",
                            attempt=row["attempt"] + 1,
                            lease_until=None,
                            updated_at=now(),
                        )
                    )
                    row = (
                        connection.execute(select(jobs).where(jobs.c.id == identity))
                        .mappings()
                        .one()
                    )
                if row["status"] != "queued":
                    continue
                attempt = row["attempt"]
            queue_id = f"fillable-{identity}-{attempt}"
            try:
                try:
                    existing = Job.fetch(
                        queue_id, connection=redis, serializer=JSONSerializer
                    )
                    status = existing.get_status()
                    active = status in {
                        "queued",
                        "deferred",
                        "scheduled",
                    } or (
                        status == "started"
                        and existing.started_at is not None
                        and existing.started_at
                        > now() - timedelta(seconds=LEASE_SECONDS)
                    )
                    if not active:
                        # A worker can die before the business claim, leaving PG queued.
                        with database().begin() as connection:
                            current = (
                                connection.execute(
                                    select(jobs)
                                    .where(jobs.c.id == identity)
                                    .with_for_update()
                                )
                                .mappings()
                                .one()
                            )
                            if (
                                current["status"] == "queued"
                                and current["attempt"] == attempt
                            ):
                                result["failed"] += not advance(connection, current)
                        continue
                except NoSuchJobError:
                    active = False
                if not active:
                    queue.enqueue_call(
                        "app.jobs.worker.process",
                        args=(str(identity), attempt),
                        job_id=queue_id,
                        timeout=JOB_SECONDS,
                        result_ttl=300,
                        failure_ttl=300,
                        description="saved-document-inspection",
                    )
                    result["enqueued"] += 1
            except RedisError:
                result["failed"] += 1
                break
            with database().begin() as connection:
                connection.execute(
                    update(jobs)
                    .where(jobs.c.id == identity, jobs.c.attempt == attempt)
                    .values(dispatched_at=now())
                )
    return result


def main(once=False):
    while True:
        try:
            result = dispatch()
            if result["enqueued"] or result["failed"]:
                print(json.dumps(result), flush=True)
        except (SQLAlchemyError, RedisError):
            print(json.dumps({"error": "processing_dispatch_unavailable"}), flush=True)
        if once:
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
