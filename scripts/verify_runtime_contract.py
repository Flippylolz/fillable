"""Check selected Docker inspect fields without reading container environments."""

import json
import sys
from os.path import normpath

LIMITS = {
    "api": (512, 1),
    "worker": (512, 1),
    "db": (512, 1),
    "redis": (256, 0.5),
    "dispatcher": (256, 0.5),
    "maintenance": (256, 0.5),
    "gateway": (128, 0.5),
    "storage-init": (128, 0.5),
    "migrate": (256, 0.5),
}
mode, project, storage = sys.argv[1:]
assert mode in ("dev", "prod") and project.startswith("fillable-verify-")
if mode == "dev":
    LIMITS["web"] = (768, 1)
rows = [json.loads(line) for line in sys.stdin if line.strip()]
assert len(rows) == len(LIMITS)
assert {row["service"] for row in rows} == set(LIMITS)
summary = {}
for row in rows:
    service = row["service"]
    memory, cpus = LIMITS[service]
    assert row["project"] == project
    assert row["memory"] == memory * 1024**2, service
    assert row["nano_cpus"] == int(cpus * 1_000_000_000), service
    assert row["logs"] == {
        "Type": "json-file",
        "Config": {"max-size": "10m", "max-file": "3"},
    }, service
    assert not row["oom"] and row["restarts"] == 0, service
    if service in ("migrate", "storage-init"):
        assert row["status"] == "exited" and row["exit_code"] == 0, service
    else:
        assert row["status"] == "running", service
    readonly = service in (
        "worker",
        "dispatcher",
        "maintenance",
        "gateway",
        "migrate",
        "storage-init",
    ) or (mode == "prod" and service == "api")
    assert row["readonly"] == readonly, service
    if service in ("api", "worker", "dispatcher", "maintenance", "migrate"):
        assert row["user"] == "app", service
    if service == "gateway":
        assert row["user"] == "nginx"
    if service == "web":
        assert row["user"] == "node"
    published = [
        binding
        for bindings in (row["ports"] or {}).values()
        for binding in (bindings or [])
    ]
    if service == "gateway":
        assert len(published) == 1 and published[0]["HostIp"] == "127.0.0.1"
        assert 1024 <= int(published[0]["HostPort"]) <= 65535
    else:
        assert not published, service
    for mount in row["mounts"]:
        assert mount["Destination"] != "/var/run/docker.sock"
        if mount["Destination"] == "/data/documents":
            assert (
                mount["Type"] == "bind"
                and normpath(mount["Source"]) == normpath(storage)
                and mount["RW"]
            )
        elif mount["Type"] == "volume":
            assert mount["Name"].startswith(project + "_"), service
    if service in ("api", "worker", "maintenance", "storage-init"):
        assert any(mount["Destination"] == "/data/documents" for mount in row["mounts"])
    summary[service] = {"memory_mib": memory, "cpus": cpus, "readonly": readonly}
print(json.dumps({"mode": mode, "services": summary}, sort_keys=True))
print(
    "PASS: actual runtime bounds, rotation, users, mounts, isolation "
    "and no reported container OOM/restarts"
)
