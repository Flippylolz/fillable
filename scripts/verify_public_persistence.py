"""Read-only retained-document comparisons after a scoped application restart."""

import hashlib
import json
import os
import sys
from pathlib import Path

import httpx
from public_release_smoke import checked, login


def digest(data):
    if not isinstance(data, bytes):
        data = json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    return hashlib.sha256(data).hexdigest()


def verify(client, report, version):
    assert report["version"] == version and version != "development"
    assert len(report["resources"]) == 2
    for item in report["resources"]:
        endpoint = "/api/documents/" + item["id"]
        current = checked(client, "GET", endpoint + "/content").json()
        assert current["resource"]["current_version_id"] == item["current_version_id"]
        assert digest(current["document"]) == item["model_sha256"]
        assert (
            digest(checked(client, "GET", endpoint + "/download").content)
            == item["sha256"]
        )
        history = checked(client, "GET", endpoint + "/versions").json()
        assert history["next_before"] is None
        assert [(entry["id"], entry["number"]) for entry in history["items"]] == [
            (entry["id"], entry["number"]) for entry in item["versions"]
        ]
        for entry in item["versions"]:
            selected = endpoint + "/versions/" + entry["id"]
            model = checked(client, "GET", selected + "/content").json()["document"]
            assert digest(model) == entry["model_sha256"]
            assert (
                digest(checked(client, "GET", selected + "/download").content)
                == entry["sha256"]
            )


def main():
    manifests = sorted(Path(sys.argv[1]).rglob("acceptance-state.json"))
    assert len(manifests) == 2
    origin = os.environ["FILLABLE_PUBLIC_ORIGIN"]
    with httpx.Client(
        base_url=origin, headers={"Origin": origin}, timeout=40, trust_env=False
    ) as client:
        assert login(
            client,
            os.environ["FILLABLE_INITIAL_EMAIL"],
            os.environ["FILLABLE_INITIAL_PASSWORD"],
        )
        for path in manifests:
            verify(
                client,
                json.loads(path.read_text()),
                os.environ["EXPECTED_APP_VERSION"],
            )
        checked(client, "POST", "/api/auth/logout")
    print("Public retained bytes, document models and full version history: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("public_persistence_verification_failed", file=sys.stderr)
        raise SystemExit(1) from None
