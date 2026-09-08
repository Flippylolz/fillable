"""Install only Fillable's private receiver and dedicated SSH authorization."""

import fcntl
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

from fillable_runtime import FILES, environment_file, execute


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
    configuration["ingress_mode"] = "external_tls"
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
            "FILLABLE_PUBLIC_ORIGIN": f"https://{hostname}:3200",
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


def upgrade_https(source, revision):
    """Upgrade only the idle predeployment receiver; never edit shared ingress."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid installation revision")
    root = Path.home() / "fillable"
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Expected existing Fillable installation")
    with (root / "release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (root / "state.json").exists() or execute(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=fillable-production",
            ]
        ):
            raise ValueError("Receiver upgrade requires the undeployed application")
        fingerprints = json.loads((root / "installed-files.json").read_text())
        if set(fingerprints) != set(FILES):
            raise ValueError("Unexpected installed receiver files")
        changes = {}
        for name in FILES:
            current, updated = root / "ops" / name, source / name
            if current.is_symlink() or updated.is_symlink() or not updated.is_file():
                raise ValueError("Unsafe receiver source")
            original = current.read_bytes()
            if hashlib.sha256(original).hexdigest() != fingerprints[name]:
                raise ValueError("Installed receiver changed")
            changes[current] = (original, updated.read_bytes())
        configuration_path = root / "configuration.json"
        configuration = json.loads(configuration_path.read_text())
        hostname = configuration["hostname"]
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", hostname):
            raise ValueError("Invalid hostname")
        configuration["installed_source_sha"] = revision
        configuration["ingress_mode"] = "external_tls"
        changes[configuration_path] = (
            configuration_path.read_bytes(),
            json.dumps(configuration, sort_keys=True).encode(),
        )
        settings_path = root / "runtime.env"
        settings = environment_file(settings_path)
        old_origin = settings["FILLABLE_PUBLIC_ORIGIN"]
        if old_origin not in {f"http://{hostname}:3200", f"https://{hostname}:3200"}:
            raise ValueError("Unexpected prior public origin")
        original = settings_path.read_bytes()
        if original.count(f"FILLABLE_PUBLIC_ORIGIN={old_origin}\n".encode()) != 1:
            raise ValueError("Unexpected public origin record")
        changes[settings_path] = (
            original,
            original.replace(
                f"FILLABLE_PUBLIC_ORIGIN={old_origin}\n".encode(),
                f"FILLABLE_PUBLIC_ORIGIN=https://{hostname}:3200\n".encode(),
            ),
        )
        fingerprint_path = root / "installed-files.json"
        new_fingerprints = {
            name: hashlib.sha256(changes[root / "ops" / name][1]).hexdigest()
            for name in FILES
        }
        changes[fingerprint_path] = (
            fingerprint_path.read_bytes(),
            json.dumps(new_fingerprints, sort_keys=True).encode(),
        )
        written = []

        def replace(path, data):
            temporary = path.with_name(path.name + ".upgrade-" + uuid4().hex)
            try:
                temporary.write_bytes(data)
                temporary.chmod(path.stat().st_mode & 0o777)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)

        try:
            for path, (previous, updated) in changes.items():
                if path.is_symlink() or path.read_bytes() != previous:
                    raise ValueError("Concurrent receiver change")
                replace(path, updated)
                written.append(path)
        except Exception:
            for path in reversed(written):
                if path.read_bytes() == changes[path][1]:
                    replace(path, changes[path][0])
            raise
    return {"upgraded": True, "source_sha": revision, "ingress": "external_tls"}


if __name__ == "__main__":
    os.umask(0o077)
    try:
        if len(sys.argv) == 4 and sys.argv[3] == "upgrade-https":
            result = upgrade_https(Path(sys.argv[1]), sys.argv[2])
        else:
            result = install(Path(sys.argv[1]), sys.argv[2], json.load(sys.stdin))
        print(json.dumps(result, sort_keys=True))
    except Exception:
        print("fillable_receiver_install_failed", file=sys.stderr)
        raise SystemExit(1) from None
