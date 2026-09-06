"""Quota enforcement shared by HTTP callers, jobs and maintenance commands."""

import errno
import hashlib
import re
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, func, insert, select, update

from app.storage.filesystem import FileSystem
from app.storage.schema import (
    PURPOSES,
    QuotaAmounts,
    accounts,
    calculate_usage,
    files,
    reservations,
    settings,
)

ACTIVE = ("reserved", "writing", "staged", "cleanup_pending")
CHUNK_BYTES = 64 * 1024


class StorageError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class StoredFile:
    id: UUID
    owner_id: UUID
    size_bytes: int
    digest: str


@dataclass(frozen=True)
class Policy:
    file_bytes: int = 10 * 1024**2
    staging_bytes: int = 64 * 1024**2
    disk_headroom_bytes: int = 64 * 1024**2
    lease_seconds: int = 60

    def __post_init__(self):
        if (
            any(
                type(value) is not int or value < 0
                for value in (
                    self.file_bytes,
                    self.staging_bytes,
                    self.disk_headroom_bytes,
                )
            )
            or type(self.lease_seconds) is not int
            or self.lease_seconds <= 0
        ):
            raise ValueError("invalid storage policy")


def now():
    return datetime.now(timezone.utc)


def lock_account(connection, owner):
    """Allocation AND quota configuration must use this order."""
    default = connection.execute(select(settings).with_for_update()).mappings().one()
    account = (
        connection.execute(
            select(accounts).where(accounts.c.user_id == owner).with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if account is None:
        raise StorageError("not_found")
    usage = calculate_usage(
        QuotaAmounts(
            default_limit_bytes=default["default_limit_bytes"],
            override_bytes=account["override_bytes"],
            used_bytes=account["used_bytes"],
            reserved_bytes=account["reserved_bytes"],
        )
    )
    return account, usage


class Storage:
    def __init__(self, engine: Engine, filesystem: FileSystem, policy=Policy()):
        self.engine, self.fs, self.policy = engine, filesystem, policy

    def _capacity(self, connection, usage, growth):
        if usage.over_limit or growth > usage.available_bytes:
            raise StorageError("quota_exceeded")
        allocated, promised = connection.execute(
            select(
                func.coalesce(func.sum(reservations.c.allocated_bytes), 0),
                func.coalesce(
                    func.sum(
                        reservations.c.allocated_bytes - reservations.c.written_bytes
                    ),
                    0,
                ),
            ).where(reservations.c.state.in_(ACTIVE))
        ).one()
        if allocated + growth > self.policy.staging_bytes:
            raise StorageError("temporary_capacity")
        if promised + growth + self.policy.disk_headroom_bytes > self.fs.available():
            raise StorageError("disk_capacity")

    def _begin(self, owner, key, fingerprint, purpose, expected):
        with self.engine.begin() as connection:
            account, usage = lock_account(connection, owner)
            existing = (
                connection.execute(
                    select(reservations)
                    .where(
                        reservations.c.owner_id == owner,
                        reservations.c.idempotency_key == key,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if (
                    existing["request_fingerprint"],
                    existing["purpose"],
                    existing["expected_bytes"],
                ) != (fingerprint, purpose, expected):
                    raise StorageError("idempotency_conflict")
                return dict(existing), False
            amount = expected or 0
            self._capacity(connection, usage, amount)
            op = dict(
                id=uuid4(),
                owner_id=owner,
                file_id=uuid4(),
                idempotency_key=key,
                request_fingerprint=fingerprint,
                purpose=purpose,
                expected_bytes=expected,
                allocated_bytes=amount,
                lease_token=uuid4(),
                lease_expires_at=self._deadline(),
            )
            connection.execute(insert(reservations).values(**op))
            connection.execute(
                update(accounts)
                .where(accounts.c.user_id == owner)
                .values(
                    reserved_bytes=account["reserved_bytes"] + amount,
                )
            )
            return op, True

    def _deadline(self):
        return now() + timedelta(seconds=self.policy.lease_seconds)

    def _operation(self, connection, op):
        row = (
            connection.execute(
                select(reservations)
                .where(
                    reservations.c.id == op["id"],
                    reservations.c.owner_id == op["owner_id"],
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        if row["lease_token"] != op["lease_token"] or row["state"] not in ACTIVE:
            raise StorageError("operation_expired")
        return row

    def _advance(self, op, size, *, written=False):
        with self.engine.begin() as connection:
            account, usage = lock_account(connection, op["owner_id"])
            row = self._operation(connection, op)
            growth = max(0, size - row["allocated_bytes"])
            if not written:
                self._capacity(connection, usage, growth)
            connection.execute(
                update(accounts)
                .where(
                    accounts.c.user_id == op["owner_id"],
                )
                .values(reserved_bytes=account["reserved_bytes"] + growth)
            )
            values = dict(
                allocated_bytes=row["allocated_bytes"] + growth,
                state="writing",
                lease_expires_at=self._deadline(),
                updated_at=now(),
            )
            if written:
                values["written_bytes"] = size
            connection.execute(
                update(reservations)
                .where(
                    reservations.c.id == op["id"],
                )
                .values(**values)
            )

    def _result(self, connection, op):
        row = (
            connection.execute(
                select(files).where(
                    files.c.reservation_id == op["id"],
                    files.c.owner_id == op["owner_id"],
                    files.c.state == "ready",
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise StorageError("not_found")
        return StoredFile(row["id"], row["owner_id"], row["size_bytes"], row["digest"])

    def _finish(self, op, size, digest, finalize):
        result = StoredFile(op["file_id"], op["owner_id"], size, digest)
        with self.engine.begin() as connection:
            lock_account(connection, op["owner_id"])
            self._operation(connection, op)
            connection.execute(
                insert(files).values(
                    id=result.id,
                    owner_id=result.owner_id,
                    reservation_id=op["id"],
                    size_bytes=size,
                    digest=digest,
                )
            )
            connection.execute(
                update(reservations)
                .where(
                    reservations.c.id == op["id"],
                )
                .values(state="staged", updated_at=now())
            )
        with self.engine.begin() as connection:
            account, usage = lock_account(connection, op["owner_id"])
            row = self._operation(connection, op)
            self._capacity(connection, usage, 0)
            self.fs.publish(op["id"], op["owner_id"], op["file_id"])
            if finalize is not None:
                finalize(connection, result)
            connection.execute(
                update(files)
                .where(files.c.id == result.id)
                .values(
                    state="ready",
                    ready_at=now(),
                )
            )
            connection.execute(
                update(accounts)
                .where(
                    accounts.c.user_id == op["owner_id"],
                )
                .values(
                    used_bytes=account["used_bytes"] + size,
                    reserved_bytes=account["reserved_bytes"] - row["allocated_bytes"],
                )
            )
            connection.execute(
                update(reservations)
                .where(
                    reservations.c.id == op["id"],
                )
                .values(state="committed", updated_at=now())
            )
        return result

    def _clean(self, op):
        with self.engine.begin() as connection:
            lock_account(connection, op["owner_id"])
            row = (
                connection.execute(
                    select(reservations)
                    .where(
                        reservations.c.id == op["id"],
                    )
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            if row["state"] == "aborted":
                return
            committed = row["state"] == "committed"
            if not committed:
                connection.execute(
                    update(reservations)
                    .where(
                        reservations.c.id == op["id"],
                    )
                    .values(state="cleanup_pending", updated_at=now())
                )
        self.fs.clean(op["id"], op["owner_id"], op["file_id"], committed=committed)
        if committed:
            return
        with self.engine.begin() as connection:
            account, _usage = lock_account(connection, op["owner_id"])
            row = self._operation(connection, op)
            connection.execute(
                update(accounts)
                .where(
                    accounts.c.user_id == op["owner_id"],
                )
                .values(
                    reserved_bytes=account["reserved_bytes"] - row["allocated_bytes"]
                )
            )
            connection.execute(
                update(files)
                .where(
                    files.c.reservation_id == op["id"],
                )
                .values(state="deleted", deleted_at=now())
            )
            connection.execute(
                update(reservations)
                .where(
                    reservations.c.id == op["id"],
                )
                .values(state="aborted", updated_at=now())
            )

    def store(
        self,
        owner: UUID,
        key: str,
        fingerprint: str,
        purpose: str,
        chunks: Iterable[bytes],
        *,
        expected_bytes: int | None = None,
        finalize: Callable[[Connection, StoredFile], None] | None = None,
    ):
        """Caller authorizes owner/context; callback changes ONLY this SQL transaction.

        Fingerprint binds the validated request/source revision, not untrusted names.
        A definitive aborted attempt needs a new key. Lost responses reuse the key.
        """
        if (
            not isinstance(owner, UUID)
            or not key.strip()
            or len(key) > 128
            or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            or purpose not in PURPOSES
        ):
            raise StorageError("invalid_request")
        if expected_bytes is not None and (
            type(expected_bytes) is not int or expected_bytes < 0
        ):
            raise StorageError("invalid_request")
        if expected_bytes is not None and expected_bytes > self.policy.file_bytes:
            raise StorageError("file_too_large")
        try:
            op, fresh = self._begin(owner, key, fingerprint, purpose, expected_bytes)
            with self.fs.lock(op["id"]):
                if not fresh:
                    if op["state"] == "committed":
                        with self.engine.connect() as connection:
                            return self._result(connection, op)
                    raise StorageError(
                        "operation_aborted"
                        if op["state"] == "aborted"
                        else "operation_in_progress"
                    )
                try:
                    size, digest = 0, hashlib.sha256()
                    with self.fs.stage(op["id"]) as stream:
                        for chunk in chunks:
                            if not isinstance(chunk, bytes):
                                raise StorageError("invalid_request")
                            if size + len(chunk) > self.policy.file_bytes:
                                raise StorageError("file_too_large")
                            for offset in range(0, len(chunk), CHUNK_BYTES):
                                part = chunk[offset : offset + CHUNK_BYTES]
                                self._advance(op, size + len(part))
                                view = memoryview(part)
                                while view:
                                    count = stream.write(view)
                                    if not count:
                                        raise OSError("short write")
                                    view = view[count:]
                                size += len(part)
                                digest.update(part)
                                self._advance(op, size, written=True)
                    if expected_bytes is not None and size != expected_bytes:
                        raise StorageError("size_mismatch")
                    result = self._finish(op, size, digest.hexdigest(), finalize)
                except Exception:
                    # A failed SQL commit response may mean it committed. _clean
                    # consults durable state and NEVER removes a committed result.
                    self._clean(op)
                    raise
                try:
                    self._clean(op)
                except OSError:
                    # Only a redundant hard link remains; recovery can retry it.
                    pass
                return result
        except BlockingIOError:
            raise StorageError("operation_in_progress") from None
        except OSError as error:
            code = (
                "disk_capacity"
                if error.errno in (errno.ENOSPC, errno.EDQUOT)
                else "storage_failure"
            )
            raise StorageError(code) from None

    def recover(self, owner: UUID, operation: UUID):
        with self.engine.connect() as connection:
            op = (
                connection.execute(
                    select(reservations).where(
                        reservations.c.id == operation,
                        reservations.c.owner_id == owner,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if op is None:
            raise StorageError("not_found")
        try:
            with self.fs.lock(operation):
                # Reread after acquiring liveness lock, without holding SQL locks
                # while waiting for a writer. A live writer always keeps flock.
                with self.engine.connect() as connection:
                    row = (
                        connection.execute(
                            select(reservations).where(
                                reservations.c.id == operation,
                            )
                        )
                        .mappings()
                        .one()
                    )
                if row["state"] in ACTIVE and row["lease_expires_at"] > now():
                    return False
                self._clean(dict(row))
                return True
        except BlockingIOError:
            return False
        except OSError:
            raise StorageError("storage_failure") from None

    @contextmanager
    def read(self, owner: UUID, file_id: UUID):
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(files).where(
                        files.c.id == file_id,
                        files.c.owner_id == owner,
                        files.c.state == "ready",
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise StorageError("not_found")
        try:
            with self.fs.lock(row["reservation_id"], shared=True):
                with self.engine.connect() as connection:
                    ready = connection.execute(
                        select(files.c.state).where(
                            files.c.id == file_id,
                            files.c.owner_id == owner,
                        )
                    ).scalar_one()
                if ready != "ready":
                    raise StorageError("not_found")
                with self.fs.read(owner, file_id) as stream:
                    if stream.seek(0, 2) != row["size_bytes"]:
                        raise StorageError("storage_failure")
                    stream.seek(0)
                    if (
                        hashlib.file_digest(stream, "sha256").hexdigest()
                        != row["digest"]
                    ):
                        raise StorageError("storage_failure")
                    stream.seek(0)
                    yield stream
        except BlockingIOError:
            raise StorageError("operation_in_progress") from None
        except OSError:
            raise StorageError("storage_failure") from None
