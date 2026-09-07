"""Forced-command deployment entrypoint; its installed runtime is the authority."""

import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from uuid import uuid4

from release_artifact import MAX_ARCHIVE_BYTES, unpack

COMMAND = re.compile(r"(receive|apply) ([0-9a-f]{40}) ([0-9a-f]{64})")


def parse_command(command):
    if command == "check":
        return ("check",)
    match = COMMAND.fullmatch(command)
    if match is None:
        raise ValueError("Unsupported receiver command")
    return match.groups()


def receive(root, source, digest, stream):
    releases = root / "releases"
    if releases.is_symlink() or (root / "incoming").is_symlink():
        raise ValueError("Unsafe receiver directories")
    releases.mkdir(exist_ok=True)
    destination = releases / f"{source}-{digest}"
    temporary = root / "incoming" / uuid4().hex
    temporary.parent.mkdir(exist_ok=True)
    available = shutil.disk_usage(root).free
    # Preserve capacity for existing services, unpacking and Docker image load.
    if available < MAX_ARCHIVE_BYTES * 3 + 2 * 1024**3:
        raise ValueError("Insufficient release headroom")
    size = 0
    actual = hashlib.sha256()
    with temporary.open("xb") as target:
        while chunk := stream.read(1024**2):
            size += len(chunk)
            if size > MAX_ARCHIVE_BYTES:
                raise ValueError("Release upload exceeds bound")
            actual.update(chunk)
            target.write(chunk)
        target.flush()
        os.fsync(target.fileno())
    if actual.hexdigest() != digest:
        raise ValueError("Release upload digest mismatch")
    if destination.exists():
        if destination.is_symlink() or (destination / "verified.json").is_symlink():
            raise ValueError("Unsafe release receipt")
        previous = json.loads((destination / "verified.json").read_text())
        if previous != {"source_sha": source, "sha256": digest}:
            raise ValueError("Invalid previous receipt")
        # Still validate this complete incoming archive; never trust metadata alone.
    verified = temporary.with_name(temporary.name + "-verified")
    unpack(temporary, source, digest, verified)
    temporary.rename(verified / "release.tar")
    (verified / "verified.json").write_text(
        json.dumps({"source_sha": source, "sha256": digest})
    )
    if not destination.exists():
        verified.rename(destination)
    # Preserve failed/interrupted and redundant incoming evidence; no broad cleanup.
    return {"source_sha": source, "sha256": digest, "verified": True}


def main():
    os.umask(0o077)
    root = Path(__file__).resolve().parents[2]
    if root != Path.home() / "fillable" or not (root / "runtime.env").is_file():
        raise ValueError("Receiver is not installed")
    command = parse_command(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    from fillable_runtime import Runtime

    runtime = Runtime(root)
    with (root / "release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        runtime.preflight()
        if command[0] == "check":
            return {"protocol": 1, "ready": True}
        _, source, digest = command
        if command[0] == "receive":
            return receive(root, source, digest, sys.stdin.buffer)
        runtime.apply(source, digest)
        return {"source_sha": source, "status": "succeeded"}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception:
        print("fillable_receiver_failed", file=sys.stderr)
        raise SystemExit(1) from None
