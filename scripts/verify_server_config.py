"""Check real Compose output and prove unsafe mutations fail closed."""

import copy
import json
import sys
from pathlib import Path

from fillable_runtime import validate_compose

configuration = json.loads(Path(sys.argv[1]).read_text())
images = json.loads(Path(sys.argv[2]).read_text())
root = Path("/fillable-runtime-proof")
validate_compose(configuration, root, images)
for service, key, value in (
    ("api", "build", {"context": "/unexpected"}),
    ("api", "privileged", True),
    ("api", "network_mode", "host"),
    ("api", "ports", [{"published": "8000", "target": 8000}]),
    ("api", "image", "unexpected:latest"),
    ("api", "mem_limit", 0),
    ("api", "logging", {}),
    (
        "api",
        "volumes",
        [{"type": "bind", "source": "/other-service", "target": "/data/documents"}],
    ),
    ("ingress", "ports", [{"host_ip": "0.0.0.0", "published": "80", "target": 3200}]),
):
    changed = copy.deepcopy(configuration)
    changed["services"][service][key] = value
    try:
        validate_compose(changed, root, images)
    except ValueError:
        continue
    raise AssertionError("Unsafe runtime mutation was accepted")
print(
    "Actual Compose scope, immutable images, private mounts and rejection probes: PASS"
)
