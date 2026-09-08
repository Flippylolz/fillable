"""Receiver authority, archive replay, shared edits and mutation coordination."""

import ast
import copy
import io
import json
import multiprocessing
import os
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
from fillable_runtime import FILES, Runtime, tls_status
from install_receiver import install, upgrade_https
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

    def test_idle_https_upgrade_preserves_credentials_keys_and_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            owner, _, configuration = edge_fixture(home)
            owner.rename(home / "wef-shared-edge")
            source = home / "source"
            for name in FILES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("old reviewed receiver\n")
            configuration["public_key"] = "ssh-ed25519 AAAA fillable-deploy"
            with (
                patch("pathlib.Path.home", return_value=home),
                patch("install_receiver.execute", return_value="") as docker,
            ):
                install(source, SOURCE, configuration)
                root = home / "fillable"
                env = root / "runtime.env"
                env.write_text(env.read_text().replace("https://", "http://"))
                previous_env = env.read_bytes()
                keys = (home / ".ssh/authorized_keys").read_bytes()
                shared = {
                    p: p.read_bytes()
                    for p in (home / "wef-shared-edge").rglob("*")
                    if p.is_file()
                }
                for name in FILES:
                    (source / name).write_text("new reviewed receiver\n")
                original_files = {
                    p: p.read_bytes() for p in root.rglob("*") if p.is_file()
                }
                original_replace = Path.replace

                def fail_once(path, target):
                    if target == env:
                        raise OSError("synthetic write failure")
                    return original_replace(path, target)

                with patch("pathlib.Path.replace", new=fail_once):
                    with self.assertRaisesRegex(OSError, "synthetic"):
                        upgrade_https(source, "c" * 40)
                self.assertEqual(
                    {p: p.read_bytes() for p in original_files}, original_files
                )
                result = upgrade_https(source, "c" * 40)
                self.assertTrue(result["upgraded"])
                self.assertEqual(
                    env.read_bytes(), previous_env.replace(b"http://", b"https://")
                )
                self.assertEqual((home / ".ssh/authorized_keys").read_bytes(), keys)
                self.assertEqual({p: p.read_bytes() for p in shared}, shared)
                self.assertEqual(
                    json.loads((root / "configuration.json").read_text())[
                        "ingress_mode"
                    ],
                    "external_tls",
                )
                self.assertEqual(
                    (root / "ops/infra/nginx.relay.conf").stat().st_mode & 0o777, 0o644
                )
                docker.return_value = "existing-app"
                with self.assertRaisesRegex(ValueError, "undeployed"):
                    upgrade_https(source, SOURCE)
                docker.return_value = ""
                (root / "ops" / FILES[0]).write_text("concurrent change")
                with self.assertRaisesRegex(ValueError, "changed"):
                    upgrade_https(source, SOURCE)
                self.assertEqual(
                    env.read_bytes(), previous_env.replace(b"http://", b"https://")
                )

    def test_relay_failure_stops_only_fillable_and_never_changes_shared_ingress(self):
        runtime = object.__new__(Runtime)
        runtime.configuration = {"hostname": "ingress"}
        runtime.command = Mock()
        runtime.progress = Mock()
        runtime.baselines = Mock(return_value={"existing": 200})
        before = {"other": {"started": "unchanged"}}
        with (
            patch("fillable_runtime.snapshot", return_value=before) as state,
            patch("fillable_runtime.tls_status", return_value=200) as tls,
            patch("fillable_edge.SharedEdge.activate") as activate,
        ):
            runtime.start_relay(before, {"existing": 200})
            self.assertEqual(runtime.command.call_count, 1)
            tls.return_value = 502
            with self.assertRaisesRegex(ValueError, "not ready"):
                runtime.start_relay(before, {"existing": 200})
            self.assertEqual(runtime.command.call_args.args, ("stop", "ingress"))
            tls.side_effect = ssl.SSLCertVerificationError("untrusted")
            with self.assertRaises(ssl.SSLCertVerificationError):
                runtime.start_relay(before, {"existing": 200})
            self.assertEqual(runtime.command.call_args.args, ("stop", "ingress"))
            tls.side_effect = None
            tls.return_value = 200
            state.return_value = {"other": {"started": "changed"}}
            with self.assertRaisesRegex(ValueError, "baseline"):
                runtime.start_relay(before, {"existing": 200})
            activate.assert_not_called()
            self.assertTrue(
                all(
                    call.args[-1] == "ingress"
                    for call in runtime.command.call_args_list
                )
            )

    def test_real_tls_checks_trust_hostname_and_http_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cert, key = root / "cert.pem", root / "key.pem"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-days",
                    "1",
                    "-subj",
                    "/CN=ingress",
                    "-addext",
                    "subjectAltName=DNS:ingress",
                    "-keyout",
                    str(key),
                    "-out",
                    str(cert),
                ],
                check=True,
                capture_output=True,
            )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(("127.0.0.1", 3200))
                listener.listen()
                listener.settimeout(10)
                requests = []

                def serve():
                    for _ in range(3):
                        connection, _ = listener.accept()
                        try:
                            with context.wrap_socket(
                                connection, server_side=True
                            ) as secured:
                                requests.append(secured.recv(4096))
                                secured.sendall(
                                    b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n"
                                    b"Connection: close\r\n\r\n"
                                )
                        except ssl.SSLError:
                            connection.close()

                server = threading.Thread(target=serve, daemon=True)
                server.start()
                with patch.dict(os.environ, {"SSL_CERT_FILE": str(cert)}):
                    self.assertEqual(tls_status("ingress", "127.0.0.1"), 200)
                    with self.assertRaises(ssl.SSLCertVerificationError):
                        tls_status("wrong-name", "127.0.0.1")
                with patch.dict(os.environ, {"SSL_CERT_FILE": str(root / "absent-ca")}):
                    with self.assertRaises(ssl.SSLCertVerificationError):
                        tls_status("ingress", "127.0.0.1")
                server.join(10)
                self.assertFalse(server.is_alive())
                self.assertEqual(len(requests), 1)
                self.assertIn(b"Host: ingress:3200", requests[0])

    @patch("fillable_runtime.execute", return_value="sha256:" + "0" * 64)
    def test_initial_account_is_source_bound_and_cannot_replace_existing_users(
        self, execute_mock
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {
                "source_sha": SOURCE,
                "sha256": "b" * 64,
                "status": "succeeded",
                "images": {
                    role: {"id": "sha256:" + "0" * 64}
                    for role in ("backend", "gateway")
                },
            }
            (root / "state.json").write_text(json.dumps(state))
            runtime = object.__new__(Runtime)
            runtime.root = root
            runtime.environment = {}
            runtime.command = Mock(side_effect=["container", "0", "completed"])
            account = {
                "email": "owner@example.test",
                "password": "Synthetic-private-initial-password",
            }
            runtime.provision(SOURCE, "b" * 64, account)
            call = runtime.command.call_args
            self.assertEqual(call.kwargs, {"input": account["password"] + "\n"})
            self.assertNotIn(account["password"], call.args)
            self.assertIn("provision", call.args)
            runtime.command = Mock(return_value="1")
            with self.assertRaisesRegex(ValueError, "preserved"):
                runtime.provision(SOURCE, "b" * 64, account)
            self.assertEqual(runtime.command.call_count, 2)
            runtime.command.reset_mock()
            with self.assertRaisesRegex(ValueError, "active"):
                runtime.provision("c" * 40, "b" * 64, account)
            runtime.command.assert_not_called()
            execute_mock.return_value = "sha256:" + "1" * 64
            with self.assertRaisesRegex(ValueError, "differs"):
                runtime.provision(SOURCE, "b" * 64, account)
            self.assertEqual(runtime.command.call_count, 1)

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
