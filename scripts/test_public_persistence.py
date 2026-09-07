"""Public persistence proof rejects altered bytes, models, history and versions."""

import copy
import unittest

import httpx
from verify_public_persistence import digest, verify


class PersistenceTests(unittest.TestCase):
    def test_retained_snapshot_rejects_each_material_change(self):
        document = {"type": "doc", "content": [{"text": "Ґанна Їжак"}]}
        item = {
            "id": "synthetic",
            "current_version_id": "revision",
            "sha256": digest(b"synthetic-docx"),
            "model_sha256": digest(document),
            "versions": [
                {
                    "id": "revision",
                    "number": 1,
                    "sha256": digest(b"synthetic-docx"),
                    "model_sha256": digest(document),
                }
            ],
        }
        report = {"version": "abcdef0", "resources": [item, copy.deepcopy(item)]}
        for change in (None, "bytes", "model", "history", "current", "badge"):
            with self.subTest(change=change):

                def handle(request):
                    path = request.url.path
                    if path.endswith("/download"):
                        return httpx.Response(
                            200,
                            content=b"changed"
                            if change == "bytes"
                            else b"synthetic-docx",
                        )
                    if path.endswith("/versions"):
                        return httpx.Response(
                            200,
                            json={
                                "next_before": None,
                                "items": []
                                if change == "history"
                                else [{"id": "revision", "number": 1}],
                            },
                        )
                    return httpx.Response(
                        200,
                        json={
                            "document": {} if change == "model" else document,
                            "resource": {
                                "current_version_id": "changed"
                                if change == "current"
                                else "revision"
                            },
                        },
                    )

                with httpx.Client(
                    base_url="http://test", transport=httpx.MockTransport(handle)
                ) as client:
                    if change is None:
                        verify(client, report, "abcdef0")
                    else:
                        with self.assertRaises(AssertionError):
                            verify(
                                client,
                                report,
                                "1234567" if change == "badge" else "abcdef0",
                            )


if __name__ == "__main__":
    unittest.main()
