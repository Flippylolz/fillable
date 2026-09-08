"""Credential-free Actions readiness; authenticated acceptance remains private."""

import json
import os
import re
import sys
from http.cookies import SimpleCookie
from pathlib import Path

import httpx


def readiness(client, source):
    ready = client.get("/api/ready")
    assert ready.status_code == 200
    page = client.get("/")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert '<div id="root">' in page.text
    session = client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.headers["cache-control"] == "no-store"
    state = session.json()
    assert state["user"] is None and re.fullmatch("[0-9a-f]{64}", state["csrf_token"])
    cookies = SimpleCookie()
    cookies.load(session.headers["set-cookie"])
    assert set(cookies) == {"fillable_session_v1"}
    cookie = cookies["fillable_session_v1"]
    assert (
        cookie.value and cookie["httponly"] and cookie["samesite"].lower() == "strict"
    )
    assert cookie["secure"] and not cookie["domain"] and cookie["path"] == "/"
    client.headers["X-CSRF-Token"] = state["csrf_token"]
    assert client.get("/api/storage/usage").status_code == 401
    for headers in (
        {"Origin": "http://invalid.test:3200"},
        {"X-CSRF-Token": "invalid"},
    ):
        assert client.post("/api/auth/logout", headers=headers).status_code == 403
    signed_out = client.post("/api/auth/logout")
    assert signed_out.status_code == 200 and signed_out.json()["user"] is None
    return {
        "source_sha": source,
        "status": "succeeded",
        "authenticated_acceptance": "pending",
    }


def main():
    source, output = sys.argv[1:]
    assert re.fullmatch("[0-9a-f]{40}", source)
    origin = os.environ["FILLABLE_PUBLIC_ORIGIN"]
    assert re.fullmatch(r"https://[a-z0-9.-]+:3200", origin)
    with httpx.Client(
        base_url=origin, headers={"Origin": origin}, timeout=40, trust_env=False
    ) as client:
        result = readiness(client, source)
    Path(output).write_text(json.dumps(result, sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("public_release_readiness_failed", file=sys.stderr)
        raise SystemExit(1) from None
