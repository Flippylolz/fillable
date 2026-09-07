"""Authentication failures and safe retries must not produce passing smoke evidence."""

import unittest
from unittest.mock import patch

import httpx
from public_release_smoke import checked, login


class PublicReleaseTests(unittest.TestCase):
    def test_login_requires_cookie_policy_and_distinguishes_missing_account(self):
        for status, cookie, expected in (
            (200, "session=x; HttpOnly; SameSite=Strict", True),
            (401, "", False),
            (200, "session=x; SameSite=Strict", AssertionError),
            (200, "session=x; HttpOnly; SameSite=Strict; Secure", AssertionError),
            (503, "", httpx.HTTPStatusError),
        ):
            with self.subTest(status=status, cookie=cookie):

                def handle(request):
                    if request.method == "GET":
                        return httpx.Response(200, json={"csrf_token": "anonymous"})
                    assert request.headers["X-CSRF-Token"] == "anonymous"
                    return httpx.Response(
                        status,
                        headers={"Set-Cookie": cookie},
                        json={"csrf_token": "signed", "user": {"email": "test"}},
                    )

                with httpx.Client(
                    base_url="http://test", transport=httpx.MockTransport(handle)
                ) as client:
                    if isinstance(expected, type):
                        with self.assertRaises(expected):
                            login(client, "test", "private-test-password")
                    else:
                        self.assertIs(login(client, "test", "password"), expected)

    def test_busy_retry_preserves_request_and_other_conflicts_fail(self):
        requests = []

        def handle(request):
            requests.append((request.headers["Idempotency-Key"], request.content))
            if len(requests) == 1:
                return httpx.Response(
                    409, json={"error": {"code": "operation_in_progress"}}
                )
            return httpx.Response(201, json={"saved": True})

        with (
            httpx.Client(
                base_url="http://test", transport=httpx.MockTransport(handle)
            ) as client,
            patch("public_release_smoke.time.sleep"),
        ):
            response = checked(
                client,
                "POST",
                "/save",
                json={"revision": "same"},
                headers={"Idempotency-Key": "same"},
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0], requests[1])
        for code in ("source_revision_changed", "operation_in_progress"):
            with httpx.Client(
                base_url="http://test",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(409, json={"error": {"code": code}})
                ),
            ) as client:
                with self.assertRaises(httpx.HTTPStatusError):
                    checked(client, "POST", "/save", json={})


if __name__ == "__main__":
    unittest.main()
