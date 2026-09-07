"""Receiver authority, archive replay, shared edits and mutation coordination."""

import ast
import copy
import io
import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fillable_edge import (
    BLOCK,
    CONFIGS,
    SharedEdge,
    atomic,
    digest,
    extension,
    include,
    patched_manager,
)
from fillable_edge_lock import locked
from fillable_runtime import FILES, Runtime
from install_receiver import install
from release_artifact import pack
from release_receiver import parse_command, receive
from test_release_contract import SOURCE, fixture

MANAGER = '''"""Owner API fixture; real nginx lifecycle is checked separately."""
from __future__ import annotations
import json
from pathlib import Path

def read_active_config(release):
    return 'tls'

def validate_release_config(root, name, config, **kwargs):
    assert (root / 'releases' / name / (config + '.conf')).is_file()

def activate_release(root, name, config, reload_callback=None, **kwargs):
    link = root / 'current'
    previous = link.readlink()
    link.unlink()
    link.symlink_to('releases/' + name)
    try:
        if (root / 'inject-change').exists():
            path = root.parent / 'ops/infra/nginx/tls.conf.in'
            path.write_text(path.read_text() + '# concurrent owner edit\\n')
        reload_callback()
    except Exception:
        link.unlink()
        link.symlink_to(previous)
        raise
    (root / 'state/edge-state.json').write_text(json.dumps({'current_release': name}))

def rollback_release(root):
    raise RuntimeError('Generic rollback must not be used')
'''


def edge_fixture(root):
    owner = root / "edge"
    scripts = owner / "ops/scripts/deploy"
    templates = owner / "ops/infra/nginx"
    release = owner / "root/releases/original"
    for path in (scripts, templates, release, owner / "root/state"):
        path.mkdir(parents=True)
    (scripts / "shared_edge_release.py").write_text(MANAGER)
    text = (
        "# preserve owner configuration\nevents {}\nhttp {\n"
        "  server { listen 80; return 200; }\n}\n"
    )
    for name in CONFIGS:
        (templates / f"{name}.conf.in").write_text(text)
        (release / f"{name}.conf").write_text(text)
    (release / "deploy-hook.sh").write_text("# unchanged hook\n")
    (owner / "root/current").symlink_to("releases/original")
    (owner / "root/state/edge-state.json").write_text('{"current_release":"original"}')
    configuration = {
        "hostname": "fillable.test",
        "manager_sha256": digest(MANAGER.encode()),
        "templates_sha256": {name: digest(text.encode()) for name in CONFIGS},
    }
    return owner, text, configuration


def hold_lock(root, ready, release):
    with locked(root):
        ready.set()
        release.wait(5)


class RuntimeContracts(unittest.TestCase):
    def test_forced_command_cannot_select_shell_path_or_project(self):
        self.assertEqual(parse_command("check"), ("check",))
        digest_value = "b" * 64
        self.assertEqual(
            parse_command(f"apply {SOURCE} {digest_value}"),
            ("apply", SOURCE, digest_value),
        )
        for command in (
            "",
            "sh",
            "check\n",
            "check; id",
            f"apply ../escape {digest_value}",
            f"apply {SOURCE} {digest_value} extra",
            f"receive {SOURCE.upper()} {digest_value}",
            "docker compose down -v",
        ):
            with self.assertRaises(ValueError):
                parse_command(command)

    def test_real_receipt_replay_and_corruption_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / "build"
            build.mkdir()
            fixture(build)
            artifact = pack(build, SOURCE, 123)
            data = (build / "release.tar").read_bytes()
            with patch(
                "release_receiver.shutil.disk_usage",
                return_value=SimpleNamespace(free=100 * 1024**3),
            ):
                first = receive(root, SOURCE, artifact["sha256"], io.BytesIO(data))
                second = receive(root, SOURCE, artifact["sha256"], io.BytesIO(data))
                self.assertEqual(first, second)
                saved = (
                    root / "releases" / f"{SOURCE}-{artifact['sha256']}" / "release.tar"
                )
                self.assertEqual(saved.read_bytes(), data)
                with self.assertRaisesRegex(ValueError, "digest"):
                    receive(
                        root, SOURCE, artifact["sha256"], io.BytesIO(data + b"corrupt")
                    )
                self.assertEqual(saved.read_bytes(), data)
                with patch("release_receiver.MAX_ARCHIVE_BYTES", 5):
                    with self.assertRaisesRegex(ValueError, "bound"):
                        receive(root, SOURCE, artifact["sha256"], io.BytesIO(data))
            with patch(
                "release_receiver.shutil.disk_usage",
                return_value=SimpleNamespace(free=1),
            ):
                with self.assertRaisesRegex(ValueError, "headroom"):
                    receive(root, SOURCE, artifact["sha256"], io.BytesIO(data))

    def test_include_round_trip_preserves_non_fillable_bytes(self):
        original = "events {}\nhttp {\n  # another application\n}\n"
        changed = include(original, True)
        self.assertEqual(include(changed, True), changed)
        self.assertEqual(
            include(changed + "# concurrent\n", False), original + "# concurrent\n"
        )
        for value in (
            changed + BLOCK,
            changed.replace("  # END FILLABLE HTTP INGRESS\n", ""),
            "events {}\n",
        ):
            with self.assertRaises(ValueError):
                include(value, True)
        for hostname in ("a;return 200;", "host\n}", "../file", ""):
            with self.assertRaises(ValueError):
                extension(hostname)

    def test_source_guard_and_atomic_write_preserve_changed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "source"
            path.write_bytes(b"concurrent")
            with self.assertRaisesRegex(ValueError, "Concurrent"):
                atomic(path, b"ours", b"old")
            self.assertEqual(path.read_bytes(), b"concurrent")
            link = root / "link"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                atomic(link, b"ours", b"concurrent")
            owner, _, configuration = edge_fixture(root)
            configuration["manager_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "changed"):
                SharedEdge(owner, configuration).activate()
            self.assertEqual(
                (owner / "ops/scripts/deploy/shared_edge_release.py").read_text(),
                MANAGER,
            )
        patched = patched_manager(MANAGER)
        ast.parse(patched)
        self.assertEqual(patched_manager(patched), patched)

    def test_manager_activation_and_scoped_removal_keep_other_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            owner, original, configuration = edge_fixture(Path(directory))
            edge = SharedEdge(owner, configuration)
            self.assertTrue(edge.activate(reload_callback=lambda: None))
            self.assertFalse(edge.activate(reload_callback=lambda: None))
            active = (owner / "root/current").resolve()
            current = active / "tls.conf"
            current.write_text(current.read_text() + "# concurrent route\n")
            template = owner / "ops/infra/nginx/tls.conf.in"
            template.write_text(template.read_text() + "# concurrent template\n")
            self.assertTrue(edge.activate(enabled=False, reload_callback=lambda: None))
            current = (owner / "root/current").resolve() / "tls.conf"
            self.assertEqual(current.read_text(), original + "# concurrent route\n")
            self.assertEqual(template.read_text(), original + "# concurrent template\n")

    def test_concurrent_edit_aborts_reload_and_preserves_owner_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            owner, original, configuration = edge_fixture(Path(directory))
            (owner / "root/inject-change").touch()
            reloads = []
            with self.assertRaisesRegex(ValueError, "Concurrent"):
                SharedEdge(owner, configuration).activate(
                    reload_callback=lambda: reloads.append(True)
                )
            self.assertEqual(reloads, [])
            self.assertEqual(
                (owner / "root/current").readlink(), Path("releases/original")
            )
            self.assertEqual(
                (owner / "ops/infra/nginx/tls.conf.in").read_text(),
                original + "# concurrent owner edit\n",
            )

    def test_installation_preserves_other_keys_and_reuses_private_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            owner, _, configuration = edge_fixture(home)
            owner.rename(home / "wef-shared-edge")
            source = home / "source"
            for name in FILES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic installed file\n")
            ssh = home / ".ssh"
            ssh.mkdir()
            authorized = ssh / "authorized_keys"
            authorized.write_text("ssh-ed25519 KEEP unrelated-key\n")
            configuration["public_key"] = "ssh-ed25519 AAAA fillable-deploy"
            with patch("pathlib.Path.home", return_value=home):
                install(source, SOURCE, copy.deepcopy(configuration))
                private = (home / "fillable/runtime.env").read_bytes()
                keys = authorized.read_bytes()
                install(source, SOURCE, copy.deepcopy(configuration))
                self.assertEqual((home / "fillable/runtime.env").read_bytes(), private)
                self.assertEqual(authorized.read_bytes(), keys)
                self.assertTrue(keys.startswith(b"ssh-ed25519 KEEP unrelated-key\n"))
                self.assertIn(b'restrict,command="', keys)
                self.assertEqual(
                    (home / "fillable/ops/infra/nginx.relay.conf").stat().st_mode
                    & 0o777,
                    0o644,
                )
                self.assertNotIn(b"POSTGRES_PASSWORD=synthetic", private)
                wrong = copy.deepcopy(configuration)
                wrong["hostname"] = "other.test"
                with self.assertRaisesRegex(ValueError, "preserved"):
                    install(source, SOURCE, wrong)
                self.assertEqual((home / "fillable/runtime.env").read_bytes(), private)

    def test_failed_attempt_does_not_replace_successful_release_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = b'{"source_sha":"previous-success"}'
            (root / "state.json").write_bytes(previous)
            runtime = object.__new__(Runtime)
            runtime.root = root

            def fail(source, digest):
                runtime.progress("verify_schema")
                raise ValueError("Incompatible schema")

            runtime._apply = fail
            with self.assertRaises(ValueError):
                runtime.apply(SOURCE, "b" * 64)
            self.assertEqual((root / "state.json").read_bytes(), previous)
            self.assertEqual(
                json.loads((root / "attempt.json").read_text()),
                {"source_sha": SOURCE, "phase": "verify_schema", "status": "failed"},
            )

    def test_lock_blocks_competing_process_and_allows_nested_manager_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "state").mkdir()
            context = multiprocessing.get_context("fork")
            ready, release = context.Event(), context.Event()
            child = context.Process(target=hold_lock, args=(root, ready, release))
            child.start()
            try:
                self.assertTrue(ready.wait(3))
                with self.assertRaises(TimeoutError):
                    with locked(root, timeout=0.2):
                        self.fail("Competing mutation acquired the lock")
            finally:
                release.set()
                child.join(3)
            self.assertEqual(child.exitcode, 0)
            with locked(root):
                with locked(root):
                    pass


if __name__ == "__main__":
    unittest.main()
