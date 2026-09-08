"""The main-merge dispatcher may only await exact-main CI and dispatch the gated release."""

import sys
import unittest
from pathlib import Path
from unittest import TestCase

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
DISPATCHER = (ROOT / ".github" / "workflows" / "deploy-main.yml").read_text()
RELEASE = (ROOT / ".github" / "workflows" / "deploy.yml").read_text()
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text()


class DeployDispatchContractTests(TestCase):
    def test_release_remains_the_manual_exact_sha_gate(self):
        self.assertIn("workflow_dispatch:", RELEASE)
        self.assertIn("source_sha:", RELEASE)
        self.assertIn("required: true", RELEASE)
        self.assertNotIn("push:", RELEASE.split("jobs:", 1)[0])
        self.assertIn("verify-release-ci.sh", RELEASE)
        self.assertIn("needs: verify", RELEASE)
        self.assertIn("fillable-production-deployment", RELEASE)

    def test_dispatcher_only_runs_for_pushes_to_main(self):
        self.assertIn("push:", DISPATCHER)
        self.assertIn("branches: [main]", DISPATCHER)
        trigger = DISPATCHER.split("jobs:", 1)[0]
        self.assertNotIn("workflow_dispatch", trigger)
        self.assertNotIn("pull_request", trigger)

    def test_dispatcher_waits_for_successful_exact_ci_before_dispatching(self):
        self.assertIn('select(.path == ".github/workflows/ci.yml")', DISPATCHER)
        self.assertIn("head_sha=$SOURCE_SHA", DISPATCHER)
        self.assertIn('"$status" = "completed"', DISPATCHER)
        self.assertIn('"$conclusion" != "success"', DISPATCHER)
        dispatch = DISPATCHER.index("gh workflow run deploy.yml")
        self.assertGreater(
            dispatch, DISPATCHER.index('"$conclusion" != "success"'),
            "The release may only be dispatched after the CI gate passed",
        )
        self.assertIn('-f source_sha="$SOURCE_SHA"', DISPATCHER)
        self.assertIn("exit 1", DISPATCHER[DISPATCHER.index('"$conclusion" != "success"'):dispatch])

    def test_dispatcher_cannot_release_or_ship_directly(self):
        for banned in ("ship-release.sh", "build-release.sh", "verify-release-ci.sh", "check-public-release.sh"):
            self.assertNotIn(banned, DISPATCHER)

    def test_ci_required_check_stays_bound_to_the_contract(self):
        self.assertIn("ci-required", CI)
        self.assertNotIn("deploy-main.yml", CI)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
