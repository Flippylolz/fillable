import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, insert, select, update

from app.accounts.schema import users
from app.infrastructure import database
from app.storage.filesystem import FileSystem, initialize
from app.storage.schema import (
    DEFAULT_LIMIT_BYTES,
    accounts,
    files,
    reservations,
    settings,
)
from app.storage.service import Policy, Storage, StorageError, now


@pytest.fixture
def setup(tmp_path):
    command.upgrade(Config("alembic.ini"), "head")
    initialize(tmp_path, os.getuid(), os.getgid())
    owner, other = uuid4(), uuid4()
    with database().begin() as connection:
        for identity in (owner, other):
            connection.execute(
                insert(users).values(
                    id=identity,
                    email=f"{identity}@example.test",
                    display_name="Їжак",
                    password_hash="synthetic-unusable",
                )
            )
            connection.execute(insert(accounts).values(user_id=identity))
    store = Storage(database(), FileSystem(tmp_path), Policy(disk_headroom_bytes=0))
    yield store, owner, other, tmp_path
    with database().begin() as connection:
        connection.execute(delete(files))
        connection.execute(delete(reservations))
        connection.execute(delete(accounts))
        connection.execute(delete(users))
        connection.execute(
            update(settings).values(
                default_limit_bytes=DEFAULT_LIMIT_BYTES,
                revision=0,
            )
        )


def save(store, owner, data=b"original", key=None, **options):
    return store.store(
        owner, key or str(uuid4()), "a" * 64, "original", [data], **options
    )


def counters(owner):
    with database().connect() as connection:
        row = (
            connection.execute(
                select(accounts).where(
                    accounts.c.user_id == owner,
                )
            )
            .mappings()
            .one()
        )
        return row["used_bytes"], row["reserved_bytes"]


def limit(owner, amount):
    with database().begin() as connection:
        connection.execute(select(settings).with_for_update())
        connection.execute(
            update(accounts)
            .where(accounts.c.user_id == owner)
            .values(
                override_bytes=amount,
            )
        )


def operation(owner):
    with database().connect() as connection:
        return dict(
            connection.execute(
                select(reservations)
                .where(
                    reservations.c.owner_id == owner,
                )
                .order_by(reservations.c.created_at.desc())
            )
            .mappings()
            .first()
        )


def expire(op):
    with database().begin() as connection:
        connection.execute(
            update(reservations)
            .where(reservations.c.id == op["id"])
            .values(
                lease_expires_at=now() - timedelta(seconds=1),
            )
        )


def test_exact_quota_immutable_read_and_retry(setup):
    store, owner, other, root = setup
    data = "Ґанна Їжак".encode()
    limit(owner, len(data))
    result = save(store, owner, data, key="same", expected_bytes=len(data))
    assert counters(owner) == (len(data), 0)
    assert result.digest == hashlib.sha256(data).hexdigest()
    assert (
        save(store, owner, b"ignored retry", key="same", expected_bytes=len(data))
        == result
    )
    with store.read(owner, result.id) as stream:
        assert stream.read() == data
    assert (
        root / "files" / str(owner) / str(result.id)
    ).stat().st_mode & 0o777 == 0o400
    assert list((root / "staging").iterdir()) == []
    with pytest.raises(StorageError, match="not_found"):
        with store.read(other, result.id):
            pass
    with pytest.raises(StorageError, match="idempotency_conflict"):
        store.store(owner, "same", "b" * 64, "original", [])
    with pytest.raises(StorageError, match="quota_exceeded"):
        save(store, owner, b"x")
    limit(owner, 0)
    with store.read(owner, result.id) as stream:
        assert stream.read() == data
    assert store.recover(owner, operation(owner)["id"])
    assert counters(owner) == (len(data), 0)


def test_inheritance_zero_unknown_and_wrong_size(setup):
    store, owner, _, _ = setup
    with database().begin() as connection:
        connection.execute(update(settings).values(default_limit_bytes=4))
    save(store, owner, b"1234")
    with pytest.raises(StorageError, match="quota_exceeded"):
        save(store, owner, b"5")
    limit(owner, 20)
    for declared in (2, 6):
        with pytest.raises(StorageError, match="size_mismatch"):
            save(store, owner, b"1234", key=f"wrong{declared}", expected_bytes=declared)
        assert counters(owner) == (4, 0)
        with pytest.raises(StorageError, match="operation_aborted"):
            save(store, owner, key=f"wrong{declared}", expected_bytes=declared)
    store.store(owner, "chunks", "a" * 64, "version", [b"", b"12", b"34"])
    assert counters(owner) == (8, 0)
    limit(owner, 0)
    with pytest.raises(StorageError, match="quota_exceeded"):
        save(store, owner, b"")


def test_conflicting_concurrent_allocations_and_active_lease(setup):
    store, owner, _, _ = setup
    limit(owner, 10)
    reserved, finish = Event(), Event()

    def chunks():
        reserved.set()
        assert finish.wait(10)
        yield b"123456"

    with ThreadPoolExecutor(2) as pool:
        task = pool.submit(
            store.store,
            owner,
            "active",
            "a" * 64,
            "original",
            chunks(),
            expected_bytes=6,
        )
        assert reserved.wait(10)
        op = operation(owner)
        assert counters(owner) == (0, 6)
        assert not store.recover(owner, op["id"])
        expire(op)
        assert not store.recover(owner, op["id"])
        with pytest.raises(StorageError, match="operation_in_progress"):
            save(store, owner, key="active", expected_bytes=6)
        with pytest.raises(StorageError, match="quota_exceeded"):
            save(store, owner, b"abcdef", expected_bytes=6)
        finish.set()
        result = task.result(10)
    assert counters(owner) == (6, 0)
    with store.read(owner, result.id) as stream:
        assert stream.read() == b"123456"


def test_quota_reduction_and_callback_rollback_preserve_original(setup):
    store, owner, _, root = setup
    original = save(store, owner)

    def reduced():
        yield b"12"
        limit(owner, 0)

    with pytest.raises(StorageError, match="quota_exceeded"):
        store.store(owner, "reduced", "a" * 64, "version", reduced())
    limit(owner, 100)

    def stale(connection, _result):
        connection.execute(
            update(users).where(users.c.id == owner).values(display_name="bad")
        )
        raise StorageError("stale_revision")

    with pytest.raises(StorageError, match="stale_revision"):
        save(store, owner, finalize=stale)
    with database().connect() as connection:
        assert (
            connection.execute(
                select(users.c.display_name).where(users.c.id == owner)
            ).scalar_one()
            == "Їжак"
        )
    with store.read(owner, original.id) as stream:
        assert stream.read() == b"original"
    assert counters(owner) == (8, 0)
    assert len(list((root / "files" / str(owner)).iterdir())) == 1


def test_capacity_input_validation_and_bounded_chunks(setup, monkeypatch):
    store, owner, _, _ = setup
    for options in ({"file_bytes": -1}, {"lease_seconds": 0}, {"staging_bytes": True}):
        with pytest.raises(ValueError):
            Policy(**options)
    for expected in (-1, True):
        with pytest.raises(StorageError, match="invalid_request"):
            save(store, owner, expected_bytes=expected)
    for key, fingerprint, purpose in (
        (" ", "a" * 64, "original"),
        ("x", "bad", "original"),
        ("x", "a" * 64, "bad"),
    ):
        with pytest.raises(StorageError, match="invalid_request"):
            store.store(owner, key, fingerprint, purpose, [])
    with pytest.raises(StorageError, match="not_found"):
        save(store, uuid4())
    store.policy = Policy(file_bytes=4, staging_bytes=3, disk_headroom_bytes=0)
    with pytest.raises(StorageError, match="file_too_large"):
        save(store, owner, expected_bytes=5)
    with pytest.raises(StorageError, match="file_too_large"):
        save(store, owner, b"12345")
    with pytest.raises(StorageError, match="temporary_capacity"):
        save(store, owner, b"1234")
    monkeypatch.setattr(store.fs, "available", lambda: 0)
    with pytest.raises(StorageError, match="disk_capacity"):
        save(store, owner, b"1")
    assert counters(owner) == (0, 0)
    monkeypatch.undo()
    store.policy = Policy(disk_headroom_bytes=0)
    with pytest.raises(StorageError, match="invalid_request"):
        store.store(owner, "invalid-chunk", "a" * 64, "export", ["not bytes"])
    data = b"x" * 150000
    result = save(store, owner, data)
    with store.read(owner, result.id) as stream:
        assert stream.read() == data


def test_failed_cleanup_holds_capacity_until_expired_recovery(setup, monkeypatch):
    store, owner, _, root = setup
    clean = store.fs.clean

    def unavailable(*args, **kwargs):
        raise OSError("synthetic failure")

    monkeypatch.setattr(store.fs, "clean", unavailable)
    with pytest.raises(StorageError, match="storage_failure"):
        save(store, owner, b"123", expected_bytes=4)
    op = operation(owner)
    assert op["state"] == "cleanup_pending" and counters(owner) == (0, 4)
    assert not store.recover(owner, op["id"])
    expire(op)
    with pytest.raises(StorageError, match="storage_failure"):
        store.recover(owner, op["id"])
    monkeypatch.setattr(store.fs, "clean", clean)
    assert store.recover(owner, op["id"])
    assert store.recover(owner, op["id"])
    assert counters(owner) == (0, 0) and not list((root / "staging").iterdir())
    with pytest.raises(StorageError, match="not_found"):
        store.recover(uuid4(), op["id"])


def test_real_process_crash_after_publication_is_cleaned_once(setup):
    store, owner, _, root = setup
    script = """
import os, sys
from pathlib import Path
from uuid import UUID
from app.infrastructure import database
from app.storage.filesystem import FileSystem
from app.storage.service import Storage, Policy
class Crash(FileSystem):
    def publish(self, *args):
        super().publish(*args)
        os._exit(73)
Storage(database(), Crash(Path(sys.argv[1])), Policy(disk_headroom_bytes=0)).store(
    UUID(sys.argv[2]), 'crash', 'a' * 64, 'version', [b'crashed'], expected_bytes=7)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(root), str(owner)], timeout=20
    )
    assert completed.returncode == 73
    op = operation(owner)
    assert op["state"] == "staged" and counters(owner) == (0, 7)
    assert (root / "files" / str(owner) / str(op["file_id"])).read_bytes() == b"crashed"
    with pytest.raises(StorageError, match="not_found"):
        with store.read(owner, op["file_id"]):
            pass
    expire(op)
    assert store.recover(owner, op["id"]) and store.recover(owner, op["id"])
    assert counters(owner) == (0, 0)
    assert not list((root / "files" / str(owner)).iterdir())


def test_committed_cleanup_failure_and_lost_response_are_retryable(setup, monkeypatch):
    store, owner, _, root = setup
    clean = store.fs.clean
    monkeypatch.setattr(
        store.fs, "clean", lambda *a, **kw: (_ for _ in ()).throw(OSError())
    )
    result = save(store, owner, key="committed")
    op = operation(owner)
    assert counters(owner) == (8, 0) and list((root / "staging").iterdir())
    assert save(store, owner, key="committed") == result
    monkeypatch.setattr(store.fs, "clean", clean)
    assert store.recover(owner, op["id"])
    assert store.recover(owner, op["id"])
    assert not list((root / "staging").iterdir())
    # A response exception after durable SQL commit must never abort the file.
    finish = store._finish

    def lost(*args):
        finish(*args)
        raise RuntimeError("lost response")

    monkeypatch.setattr(store, "_finish", lost)
    with pytest.raises(RuntimeError, match="lost response"):
        save(store, owner, key="lost")
    recovered = save(store, owner, key="lost")
    with store.read(owner, recovered.id) as stream:
        assert stream.read() == b"original"
    assert counters(owner) == (16, 0)


def test_safe_paths_collisions_and_corrupt_reads(setup, monkeypatch):
    store, owner, _, root = setup
    outside = root / "outside"
    outside.mkdir()
    owned = root / "files" / str(owner)
    owned.symlink_to(outside, target_is_directory=True)
    with pytest.raises(StorageError, match="storage_failure"):
        save(store, owner)
    assert list(outside.iterdir()) == []
    owned.unlink()
    op = operation(owner)
    expire(op)
    assert store.recover(owner, op["id"])
    publish = store.fs.publish

    def collision(operation_id, owner_id, file_id):
        target = root / "files" / str(owner_id) / str(file_id)
        target.write_bytes(b"unrelated")
        publish(operation_id, owner_id, file_id)

    monkeypatch.setattr(store.fs, "publish", collision)
    with pytest.raises(StorageError, match="storage_failure"):
        save(store, owner)
    op = operation(owner)
    target = owned / str(op["file_id"])
    assert target.read_bytes() == b"unrelated" and counters(owner) == (0, 8)
    target.unlink()  # Remove only this test's deliberately injected collision.
    expire(op)
    assert store.recover(owner, op["id"])
    monkeypatch.setattr(store.fs, "publish", publish)
    result = save(store, owner)
    target = owned / str(result.id)
    target.chmod(0o600)
    target.write_bytes(b"bad")
    with pytest.raises(StorageError, match="storage_failure"):
        with store.read(owner, result.id):
            pass
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(StorageError, match="storage_failure"):
        with store.read(owner, result.id):
            pass


def test_fenced_writer_and_reserved_crash_without_stage(setup):
    store, owner, _, root = setup
    op, _ = store._begin(owner, "before-stage", "a" * 64, "original", 5)
    expire(op)
    assert store.recover(owner, op["id"])
    assert counters(owner) == (0, 0)
    with pytest.raises(StorageError, match="operation_expired"):
        store._advance(op, 1)
    assert not list((root / "staging").iterdir())


def test_special_files_cannot_block_read_or_lock(setup):
    store, owner, _, root = setup
    result = save(store, owner)
    target = root / "files" / str(owner) / str(result.id)
    target.unlink()
    os.mkfifo(target)
    with pytest.raises(StorageError, match="storage_failure"):
        with store.read(owner, result.id):
            pass
    op = operation(owner)
    lock = root / "locks" / str(op["id"])
    lock.unlink()  # No writer runs; replace only this synthetic test's lock.
    os.mkfifo(lock)
    with pytest.raises(StorageError, match="storage_failure"):
        store.recover(owner, op["id"])


def test_success_callback_and_same_length_corruption(setup):
    store, owner, _, root = setup

    def finalized(connection, result):
        connection.execute(
            update(users)
            .where(users.c.id == owner)
            .values(
                display_name=str(result.id),
            )
        )

    result = save(store, owner, finalize=finalized)
    with database().connect() as connection:
        assert connection.execute(
            select(users.c.display_name).where(
                users.c.id == owner,
            )
        ).scalar_one() == str(result.id)
    target = root / "files" / str(owner) / str(result.id)
    target.chmod(0o600)
    target.write_bytes(b"modified")
    with pytest.raises(StorageError, match="storage_failure"):
        with store.read(owner, result.id):
            pass
    with database().begin() as connection:
        connection.execute(
            update(files)
            .where(files.c.id == result.id)
            .values(
                state="deleted",
                deleted_at=now(),
            )
        )
    with pytest.raises(StorageError, match="not_found"):
        save(store, owner, key=operation(owner)["idempotency_key"])


def test_short_writes_and_disk_failure_keep_accounting_correct(setup, monkeypatch):
    from contextlib import contextmanager

    store, owner, _, _ = setup
    stage = store.fs.stage

    @contextmanager
    def partial(op):
        with stage(op) as stream:

            class Partial:
                def write(self, data):
                    return stream.write(data[:2])

            yield Partial()

    monkeypatch.setattr(store.fs, "stage", partial)
    result = save(store, owner)
    with store.read(owner, result.id) as stream:
        assert stream.read() == b"original"

    @contextmanager
    def full(op):
        with stage(op):

            class Full:
                def write(self, _data):
                    return 0

            yield Full()

    monkeypatch.setattr(store.fs, "stage", full)
    with pytest.raises(StorageError, match="storage_failure"):
        save(store, owner)
    assert counters(owner) == (8, 0)


def test_actual_enospc_is_distinct_from_quota_failure(setup, monkeypatch):
    import errno
    from contextlib import contextmanager

    store, owner, _, _ = setup
    stage = store.fs.stage

    @contextmanager
    def exhausted(op):
        with stage(op):

            class Full:
                def write(self, _data):
                    raise OSError(errno.ENOSPC, "synthetic disk full")

            yield Full()

    monkeypatch.setattr(store.fs, "stage", exhausted)
    with pytest.raises(StorageError, match="disk_capacity"):
        save(store, owner)
    assert counters(owner) == (0, 0)


def test_committed_cleanup_preserves_last_link_if_final_is_missing(setup, monkeypatch):
    store, owner, _, root = setup
    clean = store.fs.clean
    monkeypatch.setattr(
        store.fs, "clean", lambda *a, **kw: (_ for _ in ()).throw(OSError())
    )
    result = save(store, owner)
    op = operation(owner)
    monkeypatch.setattr(store.fs, "clean", clean)
    final = root / "files" / str(owner) / str(result.id)
    final.unlink()
    for replacement in (False, True):
        if replacement:
            final.write_bytes(b"unrelated")
        with pytest.raises(StorageError, match="storage_failure"):
            store.recover(owner, op["id"])
        assert (root / "staging" / str(op["id"])).read_bytes() == b"original"
        assert counters(owner) == (8, 0)


def test_active_retry_cannot_take_the_creating_writers_lock(setup, monkeypatch):
    store, owner, _, _ = setup
    created, release = Event(), Event()
    begin, lock = store._begin, store.fs.lock
    locks = []

    def paused_begin(*args):
        result = begin(*args)
        if result[1]:
            created.set()
            assert release.wait(5)
        return result

    def observed_lock(*args, **kwargs):
        locks.append(args[0])
        return lock(*args, **kwargs)

    monkeypatch.setattr(store, "_begin", paused_begin)
    monkeypatch.setattr(store.fs, "lock", observed_lock)
    with ThreadPoolExecutor(max_workers=1) as pool:
        writer = pool.submit(save, store, owner, key="race", expected_bytes=8)
        try:
            assert created.wait(5)
            with pytest.raises(StorageError, match="operation_in_progress"):
                save(store, owner, key="race", expected_bytes=8)
            assert locks == []
            assert counters(owner) == (0, 8)
        finally:
            release.set()
        result = writer.result(timeout=5)
    assert len(locks) == 1
    assert counters(owner) == (8, 0)
    assert save(store, owner, key="race", expected_bytes=8) == result
    assert len(locks) == 2
    assert counters(owner) == (8, 0)
