"""Synthetic fresh-stack proof only; invoked explicitly by verify-development.sh."""
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.accounts.schema import users
from app.infrastructure import database
from app.storage.filesystem import FileSystem
from app.storage.schema import accounts, files, reservations
from app.storage.service import Storage

assert os.getuid() == 10001
engine = database()
store = Storage(engine, FileSystem(Path(os.environ['STORAGE_ROOT'])))
with engine.connect() as connection:
    owner = connection.execute(select(users.c.id).where(
        users.c.email == 'browser@example.test',
    )).scalar_one()
payload = 'Synthetic retained storage: Ґанна Їжак'.encode()
if sys.argv[1] == 'write':
    store.store(owner, 'fresh-storage-proof', 'c' * 64, 'original', [payload],
                expected_bytes=len(payload))
with engine.connect() as connection:
    result = connection.execute(select(files.c.id).join(
        reservations, reservations.c.id == files.c.reservation_id,
    ).where(reservations.c.owner_id == owner,
            reservations.c.idempotency_key == 'fresh-storage-proof',
            files.c.state == 'ready')).scalar_one()
    used, reserved = connection.execute(select(
        accounts.c.used_bytes, accounts.c.reserved_bytes,
    ).where(accounts.c.user_id == owner)).one()
    assert used == len(payload) and reserved == 0
with store.read(owner, result) as stream:
    assert stream.read() == payload
print('PASS: non-root shared storage, immutable bytes and exact persisted accounting')
