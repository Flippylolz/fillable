"""The Dependabot automerge workflow arms gated merges and keeps branches up to date."""

import sys
import unittest
from pathlib import Path
from unittest import TestCase

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
AUTOMERGE = (ROOT / ".github" / "workflows" / "dependabot-automerge.yml").read_text()
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

TRIGGERS = AUTOMERGE.split("permissions:", 1)[0]
EVENT_STEP = AUTOMERGE[
    AUTOMERGE.index("Enable squash auto-merge"):
    AUTOMERGE.index("Reconcile open Dependabot pull requests")
]
SCHEDULE_STEP = AUTOMERGE[AUTOMERGE.index("Reconcile open Dependabot pull requests"):]
FAILED_CONCLUSIONS = "FAILURE|CANCELLED|TIMED_OUT|ACTION_REQUIRED|STARTUP_FAILURE"
# Join shell line continuations so logical commands can be asserted per line.
LINES = AUTOMERGE.replace("\\\n", " ").splitlines()


class DependabotAutomergeContractTests(TestCase):
    def test_triggers_cover_dependabot_events_main_pushes_and_a_fallback_schedule(self):
        self.assertIn("pull_request_target:", TRIGGERS)
        self.assertIn("types: [opened, reopened, synchronize]", TRIGGERS)
        self.assertIn("push:", TRIGGERS)
        self.assertIn("branches: [main]", TRIGGERS)
        self.assertIn("schedule:", TRIGGERS)
        self.assertRegex(TRIGGERS, r'cron: ".*\* \* \* \*"')
        self.assertNotIn("pull_request:", TRIGGERS)

    def test_permissions_stay_minimal_and_no_pull_request_code_is_checked_out(self):
        self.assertIn("contents: write", AUTOMERGE)
        self.assertIn("pull-requests: write", AUTOMERGE)
        self.assertNotIn("secrets.", AUTOMERGE.replace("secrets.GITHUB_TOKEN", ""))
        self.assertNotIn("actions/checkout", AUTOMERGE)
        self.assertNotIn("head.ref", AUTOMERGE)

    def test_job_is_guarded_to_dependabot_and_main_pushes_in_this_repository(self):
        self.assertIn("github.repository == 'Flippylolz/fillable'", AUTOMERGE)
        self.assertIn("github.event.pull_request.user.login == 'dependabot[bot]'", AUTOMERGE)
        guard = AUTOMERGE[AUTOMERGE.index("if: >-"):AUTOMERGE.index("runs-on:")]
        self.assertIn("github.event_name == 'schedule'", guard)
        self.assertIn("github.event_name == 'push'", guard)
        self.assertIn("github.ref == 'refs/heads/main'", guard)
        self.assertIn("||", guard, "Push and scheduled reconciliation share the guard")

    def test_every_merge_arming_is_auto_squash_at_an_exact_head(self):
        arming_lines = [line for line in LINES if "gh pr merge" in line]
        self.assertGreaterEqual(len(arming_lines), 2)
        for line in arming_lines:
            self.assertIn("--auto", line)
            self.assertIn("--squash", line)
            self.assertIn("--match-head-commit", line)

    def test_event_runs_refresh_a_branch_that_is_behind_main(self):
        self.assertIn("if: github.event_name == 'pull_request_target'", EVENT_STEP)
        self.assertIn('[ "$state" = "BEHIND" ]', EVENT_STEP)
        self.assertIn("update-branch", EVENT_STEP)
        self.assertIn('-f expected_head_sha="$HEAD_SHA"', EVENT_STEP)
        self.assertIn("exit 0", EVENT_STEP[EVENT_STEP.index("update-branch"):])

    def test_reconciliation_runs_for_main_pushes_and_the_fallback_schedule(self):
        self.assertIn("if: github.event_name != 'pull_request_target'", SCHEDULE_STEP)
        # The author filter is applied client-side: Dependabot's login differs
        # between REST and GraphQL and --author is unreliable under
        # GITHUB_TOKEN (the first push run matched nothing).
        list_line = next(line for line in SCHEDULE_STEP.splitlines() if "gh pr list" in line)
        self.assertNotIn("--author", list_line)
        self.assertIn('.author.login == "app/dependabot"', SCHEDULE_STEP)
        self.assertIn('.author.login == "dependabot[bot]"', SCHEDULE_STEP)
        # mergeStateStatus caches stale values right after merges, so
        # behind-ness comes from the compare API instead.
        self.assertIn("compare/main...${head_sha}", SCHEDULE_STEP)
        self.assertIn(".behind_by", SCHEDULE_STEP)
        self.assertIn('[ "$behind" -gt 0 ]', SCHEDULE_STEP)
        self.assertIn('-f expected_head_sha="$head_sha"', SCHEDULE_STEP)

    def test_reconciliation_arms_only_healthy_unarmed_pull_requests(self):
        self.assertIn('[ "$armed" = "false" ]', SCHEDULE_STEP)
        failed_guard = SCHEDULE_STEP.index(FAILED_CONCLUSIONS)
        for line in SCHEDULE_STEP.splitlines():
            if "gh pr merge" in line:
                self.assertLess(
                    failed_guard, SCHEDULE_STEP.index(line),
                    "Arming must follow the failed-check guard",
                )

    def test_reconciliation_approves_the_pull_request_runs_its_updates_held(self):
        # GITHUB_TOKEN branch updates create the PR's pull_request runs as
        # action_required; the reconciliation approves exactly those held runs
        # for the head it just updated and reports anything it cannot approve.
        self.assertIn("status=action_required", SCHEDULE_STEP)
        self.assertIn('select(.head_sha == "$head_sha")', SCHEDULE_STEP.replace('\\"', '"'))
        approve = SCHEDULE_STEP.index("/approve")
        self.assertGreater(approve, SCHEDULE_STEP.index("update-branch"))
        self.assertIn("needs manual maintainer approval", SCHEDULE_STEP)

    def test_automerge_never_bypasses_the_gate_or_releases_directly(self):
        self.assertNotIn("--admin", AUTOMERGE)
        for banned in ("ship-release.sh", "build-release.sh", "deploy.yml", "workflow run"):
            self.assertNotIn(banned, AUTOMERGE)

    def test_contracts_job_keeps_enforcing_this_contract(self):
        self.assertIn("test_dependabot_automerge_contract.py", CI)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
