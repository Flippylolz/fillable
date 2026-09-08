"""Authentication failures and safe retries must not produce passing smoke evidence."""

import unittest
from unittest.mock import patch

import httpx
from public_release_readiness import readiness
from public_release_smoke import checked, login


class PublicReleaseTests(unittest.TestCase):
    def test_readiness_requires_session_cookie_and_auth_boundaries(self):
        for scenario in (
            "ok",
            "unready",
            "not_html",
            "no_app",
            "cached",
            "signed_in",
            "csrf",
            "cookie",
            "secure",
            "domain",
            "public_data",
            "origin",
            "logout",
        ):
            with self.subTest(scenario=scenario):

                def handle(request):
                    path = request.url.path
                    if path == "/api/ready":
                        return httpx.Response(503 if scenario == "unready" else 200)
                    if path == "/":
                        return httpx.Response(
                            200,
                            headers={
                                "content-type": "text/plain"
                                if scenario == "not_html"
                                else "text/html"
                            },
                            text="other app"
                            if scenario == "no_app"
                            else '<div id="root"></div>',
                        )
                    if path == "/api/auth/session":
                        cookie = (
                            "fillable_session_v1=x; HttpOnly; "
                            "SameSite=Strict; Secure; Path=/"
                        )
                        if scenario == "cookie":
                            cookie = cookie.replace("HttpOnly", "Other")
                        if scenario == "secure":
                            cookie = cookie.replace("; Secure", "")
                        if scenario == "domain":
                            cookie += "; Domain=test"
                        return httpx.Response(
                            200,
                            headers={
                                "set-cookie": cookie,
                                "cache-control": "public"
                                if scenario == "cached"
                                else "no-store",
                            },
                            json={
                                "user": {} if scenario == "signed_in" else None,
                                "csrf_token": "bad" if scenario == "csrf" else "a" * 64,
                            },
                        )
                    if path == "/api/storage/usage":
                        return httpx.Response(200 if scenario == "public_data" else 401)
                    assert path == "/api/auth/logout"
                    if (
                        request.headers["Origin"] != "https://test:3200"
                        or request.headers["X-CSRF-Token"] != "a" * 64
                    ):
                        return httpx.Response(200 if scenario == "origin" else 403)
                    return httpx.Response(
                        500 if scenario == "logout" else 200, json={"user": None}
                    )

                with httpx.Client(
                    base_url="https://test:3200",
                    headers={"Origin": "https://test:3200"},
                    transport=httpx.MockTransport(handle),
                ) as client:
                    if scenario == "ok":
                        self.assertEqual(
                            readiness(client, "b" * 40),
                            {
                                "source_sha": "b" * 40,
                                "status": "succeeded",
                                "authenticated_acceptance": "pending",
                            },
                        )
                    else:
                        with self.assertRaises(AssertionError):
                            readiness(client, "b" * 40)

    def test_login_requires_cookie_policy_and_distinguishes_missing_account(self):
        for status, cookie, expected in (
            (200, "session=x; HttpOnly; SameSite=Strict; Secure", True),
            (401, "", False),
            (200, "session=x; SameSite=Strict", AssertionError),
            (200, "session=x; HttpOnly; SameSite=Strict", AssertionError),
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
                        json={"csrf_token": "signed", "user": {"login": "test"}},
                    )

                with httpx.Client(
                    base_url="https://test", transport=httpx.MockTransport(handle)
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
                base_url="https://test", transport=httpx.MockTransport(handle)
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
                base_url="https://test",
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(409, json={"error": {"code": code}})
                ),
            ) as client:
                with self.assertRaises(httpx.HTTPStatusError):
                    checked(client, "POST", "/save", json={})


if __name__ == "__main__":
    unittest.main()
