import os
from pathlib import Path

from app.infrastructure import database
from app.storage.filesystem import FileSystem
from app.storage.schema import MAX_BYTES
from app.storage.service import Policy, Storage


def configured():
    names = {
        "file_bytes": ("STORAGE_FILE_BYTES", 10 * 1024**2),
        "staging_bytes": ("STORAGE_STAGING_BYTES", 64 * 1024**2),
        "disk_headroom_bytes": ("STORAGE_DISK_HEADROOM_BYTES", 64 * 1024**2),
        "lease_seconds": ("STORAGE_LEASE_SECONDS", 60),
    }
    values = {}
    for field, (name, default) in names.items():
        raw = os.environ.get(name, str(default))
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 16:
            raise ValueError("invalid storage configuration")
        value = int(raw)
        if value > MAX_BYTES:
            raise ValueError("invalid storage configuration")
        values[field] = value
    if values["file_bytes"] > 10 * 1024**2 or not 1 <= values["lease_seconds"] <= 3600:
        raise ValueError("invalid storage configuration")
    root = Path(os.environ["STORAGE_ROOT"])
    if not root.is_absolute() or root == Path("/"):
        raise ValueError("invalid storage configuration")
    return Storage(database(), FileSystem(root), Policy(**values))
