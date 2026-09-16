"""Bootstrap automatic migration validation without touching live services."""

import fcntl
import hashlib
import json
import re
import sys
from pathlib import Path
from uuid import uuid4

NAME = "scripts/fillable_runtime.py"
PREVIOUS = "f3c6da0dc286ef44e75b2ad96b061b9a428b358631ed29c4f304f87623830eb8"


def replace(path, data):
    temporary = path.with_name(path.name + ".upgrade-" + uuid4().hex)
    try:
        temporary.write_bytes(data)
        temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def upgrade(root, source, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or root.is_symlink():
        raise ValueError("Invalid reviewed installation")
    with (root / "release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        runtime = root / "ops" / NAME
        manifest = root / "installed-files.json"
        candidate = source / NAME
        if any(path.is_symlink() for path in (runtime, manifest, candidate)):
            raise ValueError("Unsafe runtime path")
        before, evidence = runtime.read_bytes(), manifest.read_bytes()
        fingerprints = json.loads(evidence)
        actual = hashlib.sha256(before).hexdigest()
        updated = candidate.read_bytes()
        target = hashlib.sha256(updated).hexdigest()
        if fingerprints.get(NAME) != actual or actual not in {PREVIOUS, target}:
            raise ValueError("Unexpected installed runtime")
        # No other installed file or configuration is replaced by this operation.
        fingerprints[NAME] = target
        written = False
        try:
            if runtime.read_bytes() != before or manifest.read_bytes() != evidence:
                raise ValueError("Concurrent runtime change")
            replace(runtime, updated)
            written = True
            replace(manifest, json.dumps(fingerprints, sort_keys=True).encode())
        except Exception:
            if written and runtime.read_bytes() == updated:
                replace(runtime, before)
            raise
    return {"upgraded": True, "source_sha": revision, "runtime_sha256": target}


if __name__ == "__main__":
    print(json.dumps(upgrade(Path.home() / "fillable", Path(sys.argv[1]), sys.argv[2])))
