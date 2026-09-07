"""Add or remove only Fillable's extension through the installed nginx manager."""

import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from uuid import uuid4

from fillable_edge_lock import locked

BEGIN = "  # BEGIN FILLABLE HTTP INGRESS\n"
END = "  # END FILLABLE HTTP INGRESS\n"
BLOCK = BEGIN + "  include /etc/nginx-edge/extensions/fillable.conf;\n" + END
MARKER = "# Fillable coordinated mutations v1\n"
CONFIGS = ("bootstrap", "tls", "tls-redirect")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected owned regular configuration file")
    return path.read_bytes()


def atomic(path, data, expected):
    if path.is_symlink():
        raise ValueError("Unsafe configuration path")
    if path.exists() and regular(path) != expected:
        raise ValueError("Concurrent configuration change")
    if not path.exists() and expected is not None:
        raise ValueError("Configuration disappeared")
    temporary = path.with_name(path.name + ".fillable-" + uuid4().hex)
    with temporary.open("xb") as stream:
        stream.write(data)
    temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
    # Recheck immediately before replacing only this owned change.
    if (regular(path) if path.exists() else None) != expected:
        raise ValueError("Concurrent configuration change")
    temporary.replace(path)


def include(text, enabled):
    if BEGIN in text or END in text:
        if text.count(BLOCK) != 1 or text.count(BEGIN) != 1 or text.count(END) != 1:
            raise ValueError("Unexpected Fillable include edit")
        return text if enabled else text.replace(BLOCK, "", 1)
    if not enabled:
        return text
    matches = list(re.finditer(r"(?m)^http\s*\{\s*\n", text))
    if len(matches) != 1:
        raise ValueError("Expected one HTTP configuration context")
    position = matches[0].end()
    return text[:position] + BLOCK + text[position:]


def patched_manager(source):
    if MARKER in source:
        if source.count("@fillable_edge_lock.serialize\n") != 2:
            raise ValueError("Unexpected shared manager lock edit")
        return source
    future = "from __future__ import annotations\n"
    if source.count(future) != 1:
        raise ValueError("Unrecognized manager import boundary")
    result = source.replace(
        future, future + "\n" + MARKER + "import fillable_edge_lock\n", 1
    )
    for name in ("activate_release", "rollback_release"):
        declaration = f"def {name}("
        if result.count(declaration) != 1:
            raise ValueError("Unrecognized manager mutation boundary")
        result = result.replace(
            declaration, "@fillable_edge_lock.serialize\n" + declaration, 1
        )
    return result


def extension(hostname):
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", hostname):
        raise ValueError("Invalid configured hostname")
    return f"""server {{
  listen 3200;
  server_name {hostname};
  access_log off;
  error_log /dev/null;
  client_max_body_size 50m;
  client_body_timeout 30s;
  resolver 127.0.0.11 valid=10s ipv6=off;
  location / {{
    set $fillable_upstream fillable-gateway:8080;
    proxy_pass http://$fillable_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_connect_timeout 5s;
    proxy_read_timeout 120s;
  }}
}}
""".encode()


class SharedEdge:
    def __init__(self, owner_root, configuration):
        self.owner = Path(owner_root)
        self.root = self.owner / "root"
        self.scripts = self.owner / "ops/scripts/deploy"
        self.templates = self.owner / "ops/infra/nginx"
        self.configuration = configuration

    def install_lock(self):
        path = self.scripts / "shared_edge_release.py"
        source = regular(path)
        if (
            MARKER.encode() not in source
            and digest(source) != self.configuration["manager_sha256"]
        ):
            raise ValueError("Shared manager changed since preflight")
        helper = self.scripts / "fillable_edge_lock.py"
        expected = Path(__file__).with_name("fillable_edge_lock.py").read_bytes()
        if helper.exists():
            if regular(helper) != expected:
                raise ValueError("Shared lock helper changed")
        else:
            atomic(helper, expected, None)
        updated = patched_manager(source.decode()).encode()
        if updated != source:
            atomic(path, updated, source)
        # Use this process's same reentrant lock module for the installed manager.
        spec = importlib.util.spec_from_file_location(
            "fillable_installed_edge_manager", path
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def activate(self, *, enabled=True, reload_callback=None, network="wef-edge"):
        with locked(self.root):
            manager = self.install_lock()
            current = (self.root / "current").resolve()
            if current.parent != (self.root / "releases").resolve():
                raise ValueError("Unexpected shared release location")
            state = regular(self.root / "state/edge-state.json")
            original = {name: regular(current / f"{name}.conf") for name in CONFIGS}
            template_changes = {}
            for name in CONFIGS:
                path = self.templates / f"{name}.conf.in"
                before = regular(path)
                if (
                    BLOCK.encode() not in before
                    and enabled
                    and digest(before) != self.configuration["templates_sha256"][name]
                ):
                    raise ValueError("Shared template changed since preflight")
                template_changes[path] = (
                    before,
                    include(before.decode(), enabled).encode(),
                )
            fragment = self.root / "extensions/fillable.conf"
            fragment.parent.mkdir(exist_ok=True)
            content = extension(self.configuration["hostname"])
            if fragment.exists():
                if regular(fragment) != content:
                    raise ValueError("Fillable extension changed")
            elif enabled:
                atomic(fragment, content, None)
            updated = {
                name: include(data.decode(), enabled).encode()
                for name, data in original.items()
            }
            if updated == original and all(
                a == b for a, b in template_changes.values()
            ):
                manager.validate_release_config(
                    self.root,
                    current.name,
                    manager.read_active_config(current),
                    upstream_network=network,
                )
                return False
            release_name = "f-fillable-" + uuid4().hex
            candidate = self.root / "releases" / release_name
            candidate.mkdir()
            for name, data in updated.items():
                (candidate / f"{name}.conf").write_bytes(data)
            for name in ("deploy-hook.sh", "certbot-issuance.txt"):
                if (current / name).exists():
                    (candidate / name).write_bytes(regular(current / name))
            config = manager.read_active_config(current)
            manager.validate_release_config(
                self.root, release_name, config, upstream_network=network
            )

            def reload_checked():
                if regular(self.root / "state/edge-state.json") != state or any(
                    regular(current / f"{name}.conf") != data
                    for name, data in original.items()
                ):
                    raise ValueError("Concurrent shared release change")
                if any(
                    regular(path) != after
                    for path, (_, after) in template_changes.items()
                ):
                    raise ValueError("Concurrent shared template change")
                if reload_callback is not None:
                    reload_callback()
                else:
                    manager.graceful_reload()

            try:
                for path, (before, after) in template_changes.items():
                    if before != after:
                        atomic(path, after, before)
                manager.activate_release(
                    self.root,
                    release_name,
                    config,
                    upstream_network=network,
                    reload_callback=reload_checked,
                )
            except Exception:
                # Undo our marker without discarding intervening unrelated edits.
                for path, (before, after) in template_changes.items():
                    if before != after:
                        current_bytes = regular(path)
                        if current_bytes == after:
                            atomic(path, before, after)
                        elif (
                            BLOCK.encode() not in before
                            and current_bytes.count(BLOCK.encode()) == 1
                        ):
                            atomic(
                                path,
                                current_bytes.replace(BLOCK.encode(), b"", 1),
                                current_bytes,
                            )
                raise
            return True
