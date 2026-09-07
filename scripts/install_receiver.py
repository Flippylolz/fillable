"""Install only Fillable's private receiver and dedicated SSH authorization."""

import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import sys
from pathlib import Path
from uuid import uuid4

from fillable_runtime import FILES


def install(source, revision, configuration):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid installation revision")
    if set(configuration) != {
        "hostname",
        "public_key",
        "manager_sha256",
        "templates_sha256",
    } or set(configuration["templates_sha256"]) != {"bootstrap", "tls", "tls-redirect"}:
        raise ValueError("Unexpected private installation configuration")
    hostname = configuration["hostname"]
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", hostname):
        raise ValueError("Invalid hostname")
    key = configuration.pop("public_key")
    if not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/=]+ fillable-deploy", key):
        raise ValueError("Expected dedicated deployment key")
    owner = Path.home() / "wef-shared-edge/ops"
    expected = {
        "scripts/deploy/shared_edge_release.py": configuration["manager_sha256"]
    }
    expected.update(
        {
            f"infra/nginx/{name}.conf.in": value
            for name, value in configuration["templates_sha256"].items()
        }
    )
    for name, digest in expected.items():
        path = owner / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Shared manager changed since inspected preflight")
    root = Path.home() / "fillable"
    configuration["installed_source_sha"] = revision
    if root.exists():
        if (
            root.is_symlink()
            or json.loads((root / "configuration.json").read_text()) != configuration
        ):
            raise ValueError("Existing Fillable installation must be preserved")
    else:
        temporary = Path.home() / (".fillable-install-" + uuid4().hex)
        temporary.mkdir(mode=0o700)
        fingerprints = {}
        for name in FILES:
            path = source / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Incomplete installation source")
            destination = temporary / "ops" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            if name == "infra/nginx.relay.conf":
                destination.chmod(0o644)
            fingerprints[name] = hashlib.sha256(destination.read_bytes()).hexdigest()
        (temporary / "installed-files.json").write_text(
            json.dumps(fingerprints, sort_keys=True)
        )
        (temporary / "configuration.json").write_text(
            json.dumps(configuration, sort_keys=True)
        )
        settings = {
            "COMPOSE_PROJECT_NAME": "fillable-production",
            "FILLABLE_PUBLIC_ORIGIN": f"http://{hostname}:3200",
            "POSTGRES_PASSWORD": secrets.token_urlsafe(48),
            "DOCUMENTS_HOST_PATH": str(root / "documents"),
            "STORAGE_DISK_HEADROOM_BYTES": str(2 * 1024**3),
        }
        (temporary / "runtime.env").write_text(
            "".join(f"{key}={value}\n" for key, value in settings.items())
        )
        temporary.rename(root)
    ssh = Path.home() / ".ssh"
    ssh.mkdir(mode=0o700, exist_ok=True)
    authorized = ssh / "authorized_keys"
    if authorized.is_symlink():
        raise ValueError("Unexpected SSH authorization path")
    command = shlex.join(
        ["/usr/bin/python3", str(root / "ops/scripts/release_receiver.py")]
    )
    command = command.replace("\\", "\\\\").replace('"', '\\"')
    line = f'restrict,command="{command}" {key}\n'
    current = authorized.read_text() if authorized.exists() else ""
    if key in current:
        if line not in current:
            raise ValueError("Dedicated key already has different authorization")
    else:
        with authorized.open("a") as stream:
            stream.write("\n" + line)
        authorized.chmod(0o600)
    return {"installed": True, "source_sha": revision, "protocol": 1}


if __name__ == "__main__":
    os.umask(0o077)
    try:
        result = install(Path(sys.argv[1]), sys.argv[2], json.load(sys.stdin))
        print(json.dumps(result, sort_keys=True))
    except Exception:
        print("fillable_receiver_install_failed", file=sys.stderr)
        raise SystemExit(1) from None
