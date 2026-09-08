"""Apply verified images through a fixed, namespaced server runtime."""

import hashlib
import http.client
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from release_artifact import unpack

PROJECT = "fillable-production"
FILES = (
    "compose.yaml",
    "compose.prod.yaml",
    "compose.server.yaml",
    "infra/nginx.relay.conf",
    "scripts/release_artifact.py",
    "scripts/release_receiver.py",
    "scripts/fillable_runtime.py",
    "scripts/fillable_edge.py",
    "scripts/fillable_edge_lock.py",
)
SCHEMA = "0013_maintenance_state"
BACKEND_SERVICES = {
    "api",
    "worker",
    "dispatcher",
    "maintenance",
    "migrate",
    "storage-init",
}
IMAGE_FORMAT = (
    '{"id":"{{.Id}}","os":"{{.Os}}","architecture":"{{.Architecture}}",'
    '"revision":"{{index .Config.Labels "org.opencontainers.image.revision"}}"}'
)
STATE_FORMAT = (
    '{"id":"{{.Id}}",'
    '"project":"{{index .Config.Labels "com.docker.compose.project"}}",'
    '"status":"{{.State.Status}}","started":"{{.State.StartedAt}}",'
    '"restarts":{{.RestartCount}},'
    '"health":"{{with index .State "Health"}}{{.Status}}{{end}}"}'
)


def execute(arguments, *, environment=None, input=None):
    result = subprocess.run(
        arguments,
        env=environment,
        input=input,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode:
        # Docker/Compose errors can contain private paths and runtime configuration.
        raise RuntimeError("Scoped runtime command failed")
    return result.stdout.strip()


def environment_file(path):
    if path.is_symlink():
        raise ValueError("Runtime environment must be a regular file")
    result = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key in result or not re.fullmatch(r"[A-Z_]+", key):
            raise ValueError("Invalid runtime environment")
        result[key] = value
    return result


def snapshot():
    identifiers = execute(["docker", "ps", "-aq"]).splitlines()
    if not identifiers:
        return {}
    rows = execute(["docker", "inspect", "--format", STATE_FORMAT, *identifiers])
    return {
        row["id"]: row
        for row in map(json.loads, rows.splitlines())
        if row["project"] != PROJECT
    }


def route_status(url, *, hostname=None, method="HEAD"):
    headers = {"Host": hostname} if hostname else {}
    try:
        with urlopen(
            Request(url, headers=headers, method=method), timeout=10
        ) as response:
            return response.status, response.headers.get("Strict-Transport-Security")
    except HTTPError as response:
        return response.code, response.headers.get("Strict-Transport-Security")


def tls_status(hostname, address, path="/api/ready"):
    # Connect to the inspected edge/loopback address while verifying the real SNI.
    ipaddress.ip_address(address)
    context = ssl.create_default_context()
    with socket.create_connection((address, 3200), timeout=10) as connection:
        with context.wrap_socket(connection, server_hostname=hostname) as secured:
            secured.sendall(
                (
                    f"GET {path} HTTP/1.1\r\nHost: {hostname}:3200\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
            )
            response = http.client.HTTPResponse(secured)
            response.begin()
            return response.status


def validate_compose(configuration, root, images):
    if configuration.get("name") != PROJECT:
        raise ValueError("Unexpected runtime project")
    for name in ("postgres-data", "redis-data"):
        if configuration["volumes"][name] != {"name": f"{PROJECT}_{name}"}:
            raise ValueError("Unexpected persistent volume")
    services = configuration["services"]
    if set(services) != BACKEND_SERVICES | {"db", "redis", "gateway", "ingress"}:
        raise ValueError("Unexpected runtime service")
    for name, service in services.items():
        if (
            service.get("build")
            or service.get("privileged")
            or service.get("network_mode") == "host"
        ):
            raise ValueError("Unsafe runtime authority")
        if name != "ingress" and service.get("ports"):
            raise ValueError("Only the ingress may publish a port")
        if not service.get("mem_limit") or not float(service.get("cpus", 0)):
            raise ValueError("Missing runtime limits")
        if service.get("logging", {}).get("options") != {
            "max-size": "10m",
            "max-file": "3",
        }:
            raise ValueError("Missing bounded logging")
        if name in BACKEND_SERVICES and service["image"] != images["backend"]["id"]:
            raise ValueError("Wrong backend image")
        if name == "gateway" and service["image"] != images["gateway"]["id"]:
            raise ValueError("Wrong gateway image")
        for volume in service.get("volumes", []):
            if volume["type"] == "bind":
                source = Path(volume["source"]).resolve()
                expected = (
                    root / "documents"
                    if name != "ingress"
                    else root / "ops/infra/nginx.relay.conf"
                )
                if source != expected or expected.resolve() != expected:
                    raise ValueError("Runtime bind escapes Fillable")
            elif volume["type"] != "volume" or name not in {"db", "redis"}:
                raise ValueError("Unexpected persistent mount")
    ports = services["ingress"]["ports"]
    if (
        len(ports) != 1
        or ports[0].get("host_ip") != "0.0.0.0"
        or str(ports[0].get("published")) != "3200"
        or ports[0].get("target") != 3200
    ):
        raise ValueError("Unexpected ingress publication")
    shared_network = dict(configuration["networks"]["shared-edge"])
    if shared_network.pop("ipam", {}) or shared_network != {
        "name": "wef-edge",
        "external": True,
    }:
        raise ValueError("Unexpected shared network")


class Runtime:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.configuration = json.loads((self.root / "configuration.json").read_text())
        if self.configuration.get("ingress_mode") != "external_tls":
            raise ValueError("Receiver requires externally managed TLS ingress")
        self.settings = environment_file(self.root / "runtime.env")
        hostname = self.configuration["hostname"]
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", hostname):
            raise ValueError("Invalid private hostname")
        if self.settings.get(
            "FILLABLE_PUBLIC_ORIGIN"
        ) != f"https://{hostname}:3200" or self.settings.get(
            "DOCUMENTS_HOST_PATH"
        ) != str(self.root / "documents"):
            raise ValueError("Runtime origin or storage mismatch")
        if not re.fullmatch(
            r"[A-Za-z0-9_-]{32,128}", self.settings.get("POSTGRES_PASSWORD", "")
        ):
            raise ValueError("Invalid private database credential")
        self.environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(Path.home()),
            "FILLABLE_RUNTIME_ROOT": str(self.root / "ops"),
        }
        self.compose = [
            "docker",
            "compose",
            "--project-directory",
            str(self.root / "ops"),
            "--env-file",
            str(self.root / "runtime.env"),
            "-p",
            PROJECT,
        ]
        for name in ("compose.yaml", "compose.prod.yaml", "compose.server.yaml"):
            self.compose += ["-f", str(self.root / "ops" / name)]

    def command(self, *arguments, input=None):
        return execute(
            [*self.compose, *arguments], environment=self.environment, input=input
        )

    def provision(self, source, digest, account):
        state = json.loads((self.root / "state.json").read_text())
        if (
            state.get("source_sha") != source
            or state.get("sha256") != digest
            or state.get("status") != "succeeded"
        ):
            raise ValueError("Initial account requires the active verified release")
        if set(account) != {"email", "password"} or any(
            not isinstance(value, str) for value in account.values()
        ):
            raise ValueError("Invalid initial account input")
        for role in ("backend", "gateway"):
            self.environment[f"FILLABLE_{role.upper()}_IMAGE"] = state["images"][role][
                "id"
            ]
        active = self.command("ps", "-q", "api")
        if (
            execute(["docker", "inspect", "--format", "{{.Image}}", active])
            != state["images"]["backend"]["id"]
        ):
            raise ValueError("Running application differs from the verified release")
        count = self.command(
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "fillable",
            "-d",
            "fillable",
            "-Atqc",
            "SELECT count(*) FROM users",
        )
        if count != "0":
            raise ValueError("Existing accounts must be preserved")
        self.command(
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "app.accounts.cli",
            "provision",
            "--email",
            account["email"],
            "--display-name",
            "Адміністратор Fillable",
            "--role",
            "admin",
            "--language",
            "uk",
            "--password-stdin",
            input=account["password"] + "\n",
        )

    def preflight(self):
        fingerprints = json.loads((self.root / "installed-files.json").read_text())
        if set(fingerprints) != set(FILES):
            raise ValueError("Incomplete installed runtime")
        for name, expected in fingerprints.items():
            path = self.root / "ops" / name
            if (
                path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError("Installed runtime changed")
        if execute(
            ["docker", "info", "--format", "{{.OSType}} {{.Architecture}}"]
        ) not in {"linux x86_64", "linux amd64"}:
            raise ValueError("Unsupported server platform")
        execute(["docker", "network", "inspect", "wef-edge", "--format", "{{.Name}}"])
        shared = execute(
            [
                "docker",
                "ps",
                "-q",
                "--filter",
                "label=com.docker.compose.project=wef-shared-edge",
                "--filter",
                "label=com.docker.compose.service=nginx",
            ]
        ).splitlines()
        if len(shared) != 1:
            raise ValueError("Shared nginx owner is ambiguous")
        ports = json.loads(
            execute(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .NetworkSettings.Ports}}",
                    shared[0],
                ]
            )
        )
        if any(
            binding.get("HostPort") == "3200"
            for bindings in ports.values()
            if bindings
            for binding in bindings
        ):
            raise ValueError("Shared nginx must not publish Fillable's relay port")
        address = execute(
            [
                "docker",
                "inspect",
                "--format",
                '{{(index .NetworkSettings.Networks "wef-edge").IPAddress}}',
                shared[0],
            ]
        )
        if tls_status(self.configuration["hostname"], address) not in {200, 502}:
            raise ValueError("Externally managed TLS listener is unavailable")
        execute(
            [
                "docker",
                "exec",
                shared[0],
                "nginx",
                "-t",
                "-c",
                "/etc/nginx-edge/current/active.conf",
            ]
        )
        if shutil.disk_usage(self.root).free < 8 * 1024**3:
            raise ValueError("Insufficient deployment headroom")
        memory = re.search(
            r"(?m)^MemAvailable:\s+(\d+) kB$", Path("/proc/meminfo").read_text()
        )
        running = execute(
            [
                "docker",
                "ps",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
            ]
        )
        required_kib = (1 if running else 3) * 1024**2
        if memory is None or int(memory.group(1)) < required_kib:
            raise ValueError("Insufficient available runtime memory")
        own = execute(
            [
                "docker",
                "ps",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
                "--filter",
                "label=com.docker.compose.service=ingress",
            ]
        )
        if not own:
            with socket.socket() as probe:
                probe.bind(("0.0.0.0", 3200))

    def baselines(self):
        urls = [f"http://127.0.0.1:{port}/" for port in (80, 3000, 3100, 8080, 13100)]
        urls.append(f"https://{self.configuration['hostname']}/")
        return {url: route_status(url) for url in urls}

    def schema(self):
        present = self.command(
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "fillable",
            "-d",
            "fillable",
            "-Atqc",
            "SELECT to_regclass('public.alembic_version') IS NOT NULL",
        )
        if present == "f":
            return None
        if present != "t":
            raise ValueError("Unknown schema state")
        return self.command(
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "fillable",
            "-d",
            "fillable",
            "-Atqc",
            "SELECT version_num FROM alembic_version ORDER BY version_num",
        )

    def apply(self, source, digest):
        self.attempt_source = source
        self.progress("verify_artifact")
        try:
            self._apply(source, digest)
        except Exception:
            self.progress(self.phase, status="failed")
            raise
        self.progress("complete", status="succeeded")

    def progress(self, phase, *, status="running"):
        self.phase = phase
        path = self.root / ("attempt-" + uuid4().hex + ".json")
        path.write_text(
            json.dumps(
                {"source_sha": self.attempt_source, "phase": phase, "status": status}
            )
        )
        path.replace(self.root / "attempt.json")

    def _apply(self, source, digest):
        release = self.root / "releases" / f"{source}-{digest}"
        if release.is_symlink():
            raise ValueError("Unsafe release path")
        verified = self.root / "incoming" / ("apply-" + uuid4().hex)
        manifest = unpack(release / "release.tar", source, digest, verified)
        before, routes = snapshot(), self.baselines()
        self.progress("load_images")
        execute(["docker", "load", "--input", str(verified / "images.tar.gz")])
        for role, expected in manifest["images"].items():
            actual = json.loads(
                execute(
                    [
                        "docker",
                        "image",
                        "inspect",
                        "--format",
                        IMAGE_FORMAT,
                        expected["id"],
                    ]
                )
            )
            if actual != expected:
                raise ValueError("Loaded image identity mismatch")
            self.environment[f"FILLABLE_{role.upper()}_IMAGE"] = expected["id"]
        images = manifest["images"]
        configuration = json.loads(self.command("config", "--format", "json"))
        validate_compose(configuration, self.root, images)
        self.progress("verify_schema")
        head = execute(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp",
                "--memory",
                "256m",
                "--cpus",
                "0.5",
                images["backend"]["id"],
                "python",
                "-c",
                "from alembic.config import Config; "
                "from alembic.script import ScriptDirectory; "
                "print(','.join(ScriptDirectory.from_config("
                "Config('alembic.ini')).get_heads()))",
            ]
        )
        if head != SCHEMA:
            raise ValueError("Release schema needs a reviewed forward plan")
        self.command(
            "up", "-d", "--no-build", "--wait", "--wait-timeout", "120", "db", "redis"
        )
        if self.schema() not in {None, SCHEMA}:
            raise ValueError(
                "Database schema is incompatible; preserve data for forward repair"
            )
        self.progress("start_private_application")
        self.command(
            "up",
            "-d",
            "--no-build",
            "--wait",
            "--wait-timeout",
            "180",
            "gateway",
            "worker",
            "dispatcher",
            "maintenance",
        )
        if self.schema() != SCHEMA:
            raise ValueError("Migration did not reach the reviewed schema")
        self.start_relay(before, routes)
        result = {
            "source_sha": source,
            "sha256": digest,
            "schema": SCHEMA,
            "status": "succeeded",
            "existing_services_preserved": True,
            "images": images,
        }
        path = self.root / "state.json"
        temporary = path.with_name("state-" + uuid4().hex + ".json")
        temporary.write_text(json.dumps(result, sort_keys=True) + "\n")
        temporary.replace(path)

    def start_relay(self, before, routes):
        try:
            self.progress("start_tls_relay")
            self.command(
                "up", "-d", "--no-build", "--wait", "--wait-timeout", "120", "ingress"
            )
            if tls_status(self.configuration["hostname"], "127.0.0.1") != 200:
                raise ValueError("New ingress is not ready")
            self.progress("verify_existing_services")
            after = snapshot()
            if (
                any(after.get(key) != value for key, value in before.items())
                or self.baselines() != routes
            ):
                raise ValueError("Existing service baseline changed")
        except Exception:
            self.command("stop", "ingress")
            raise
