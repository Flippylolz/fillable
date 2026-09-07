"""Verify actual isolated gateway logs without retaining request content."""

import http.client
import json
import sys

MARKER = "SYNTHETIC_PRIVATE_LOG_MARKER"


def probe(development=False):
    requests = [
        ("GET", f"/api/health?token={MARKER}", {"Cookie": MARKER}, {200}),
        (
            "GET",
            f"/assets/{MARKER}.js?value={MARKER}",
            {},
            {200 if development else 404},
        ),
        (MARKER, "/api/health", {"Authorization": MARKER}, {400, 405, 501}),
        ("POST", f"/api/{MARKER}", {"Content-Length": str(25 * 1024 * 1024)}, {413}),
    ]
    for index, (method, path, headers, expected) in enumerate(requests):
        connection = http.client.HTTPConnection("gateway", 8080, timeout=5)
        try:
            connection.request(method, path, headers=headers)
            response = connection.getresponse()
            assert response.status in expected, (
                f"unexpected gateway probe {index}: {response.status}"
            )
            response.read()
        finally:
            connection.close()
    print("PASS: isolated gateway diagnostic requests completed")


def check(development=False):
    data = sys.stdin.read(1024 * 1024 + 1)
    assert len(data) <= 1024 * 1024, "gateway log evidence exceeds budget"
    assert MARKER not in data, "gateway logs contain synthetic private request data"
    records = [
        json.loads(line)
        for line in data.splitlines()
        if line.startswith('{"event":"gateway_request"')
    ]
    assert records, "gateway diagnostic events missing"
    for item in records:
        assert set(item) == {"event", "route", "method", "status", "bytes", "seconds"}
        assert item["route"] in {"page", "api", "asset"}
        assert item["method"] in {
            "GET",
            "HEAD",
            "POST",
            "PATCH",
            "DELETE",
            "OPTIONS",
            "other",
        }
        assert type(item["status"]) is int and type(item["bytes"]) is int
        assert isinstance(item["seconds"], (int, float))
    assert any(item["method"] == "other" for item in records)
    assert any(
        item["route"] == "asset" and item["status"] == (200 if development else 404)
        for item in records
    )
    assert any(item["route"] == "api" and item["status"] == 413 for item in records)
    print("PASS: gateway stdout/stderr contain only categorized request diagnostics")


if __name__ == "__main__":
    {"probe": probe, "check": check}[sys.argv[1]](
        development=len(sys.argv) == 3 and sys.argv[2] == "development"
    )
