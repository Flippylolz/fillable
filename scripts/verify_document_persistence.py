"""Explicit isolated synthetic QA: API upload, restart, immutable storage read."""
import hashlib
import base64
import json
import os
import sys

import httpx
from sqlalchemy import select

from app.accounts.schema import users
from app.documents.schema import resources, versions
from app.infrastructure import database
from app.storage.configuration import configured

assert os.getuid() == 10001
assert sys.argv[1] in {'write', 'read'}
data = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
assert 0 < len(data) <= 10 * 1024 * 1024
origin = os.environ['FILLABLE_PUBLIC_ORIGIN']
with httpx.Client(base_url=origin, headers={'Origin': origin}, timeout=30) as client:
    bootstrap = client.get('/api/auth/session')
    bootstrap.raise_for_status()
    client.headers['X-CSRF-Token'] = bootstrap.json()['csrf_token']
    login = client.post('/api/auth/login', json={
        'email': 'profile@example.test', 'password': 'Synthetic-browser-Їжак-2026',
    })
    login.raise_for_status()
    client.headers['X-CSRF-Token'] = login.json()['csrf_token']
    if sys.argv[1] == 'write':
        rejected = client.post('/api/documents', content=b'x' * (1024 * 1024 + 1), headers={
            'Content-Type': 'application/octet-stream', 'Idempotency-Key': 'invalid-large-proof',
            'X-Upload-Metadata': base64.b64encode(json.dumps({
                'kind': 'template', 'filename': 'invalid.docx', 'title': 'Synthetic invalid',
            }).encode()).decode(),
        })
        assert rejected.status_code == 422
        assert rejected.json()['error']['code'] == 'invalid_document'
        for _ in range(2):
            metadata = {
                'kind': 'template', 'filename': 'Синтетичний.docx',
                'title': 'Перевірка збереження',
            }
            result = client.post('/api/documents', content=data, headers={
                'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'Idempotency-Key': 'fresh-document-proof',
                'X-Upload-Metadata': base64.b64encode(json.dumps(metadata, ensure_ascii=False).encode()).decode(),
            })
            result.raise_for_status()
    listing = client.get('/api/documents', params={'kind': 'template'})
    listing.raise_for_status()
    items = listing.json()['items']
    assert len(items) == 1
    assert items[0]['digest'] == hashlib.sha256(data).hexdigest()
    assert items[0]['size_bytes'] == len(data)
    assert items[0]['processing_status'] in {'queued', 'running', 'succeeded'}
    client.post('/api/auth/logout').raise_for_status()
with database().connect() as connection:
    owner = connection.execute(select(users.c.id).where(users.c.email == 'profile@example.test')).scalar_one()
    row = connection.execute(select(resources).where(resources.c.owner_id == owner)).mappings().one()
    version = connection.execute(select(versions).where(versions.c.document_id == row['id'])).mappings().one()
    assert row['original_file_id'] == version['file_id']
    assert version['number'] == 1 and version['document_model']['type'] == 'doc'
with configured().read(owner, row['original_file_id']) as stream:
    assert stream.read() == data
print('PASS: API upload/retry, owned initial revision and immutable original survive recreation')
