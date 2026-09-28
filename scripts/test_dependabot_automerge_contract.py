"""Execute the actual trusted workflow against GitHub API fixtures."""

import copy
import os
import runpy
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else Path(__file__).resolve().parent.parent
)
WORKFLOW = (ROOT / ".github/workflows/dependabot-automerge.yml").read_text()
CODE = textwrap.dedent(WORKFLOW.split("        run: |\n", 1)[1])
# Keep an actual Python source file available for coverage's line/branch report.
SOURCE = Path(tempfile.gettempdir()) / "fillable_dependabot_workflow.py"
SOURCE.write_text(CODE)
REPO = "Flippylolz/fillable"


def pull(head="old", **changes):
    value = {
        "number": 1,
        "state": "open",
        "draft": False,
        "user": {"login": "dependabot[bot]"},
        "auto_merge": None,
        "head": {
            "sha": head,
            "ref": "dependabot/npm/update",
            "repo": {"full_name": REPO},
        },
        "base": {"ref": "main", "repo": {"full_name": REPO}},
    }
    value.update(changes)
    return value


def run(head="old", conclusion="action_required", **changes):
    value = {
        "id": 10,
        "event": "pull_request",
        "path": ".github/workflows/ci.yml",
        "head_sha": head,
        "head_repository": {"full_name": REPO},
        "pull_requests": [{"number": 1, "head": {"sha": head}}],
        "conclusion": conclusion,
    }
    value.update(changes)
    return value


class DependabotAutomergeTests(unittest.TestCase):
    def setUp(self):
        self.module = types.ModuleType("workflow")
        with patch.dict(os.environ, REPO=REPO):
            exec(compile(CODE, str(SOURCE), "exec"), self.module.__dict__)
        self.pr = pull()
        self.behind = 0
        self.runs = [run()]
        self.pages = [[self.pr]]
        self.module.api = Mock(side_effect=self.api)
        self.process = patch.object(self.module.subprocess, "run").start()
        self.sleep = patch.object(self.module.time, "sleep").start()
        self.addCleanup(patch.stopall)

    def api(self, path, method="GET", fields=None, pages=False):
        if path == "pulls/1":
            return copy.deepcopy(self.pr)
        if path.startswith("compare/"):
            return {"behind_by": self.behind}
        if path.endswith("/update-branch"):
            self.assertEqual(fields, {"expected_head_sha": "old"})
            self.pr["head"]["sha"] = "new"
            return {}
        if path.startswith("actions/workflows/ci.yml/runs?"):
            self.assertTrue(pages)
            return [{"workflow_runs": self.runs}]
        if path.endswith("/approve"):
            self.assertEqual(method, "POST")
            return {}
        if path.startswith("pulls?"):
            return self.pages
        self.fail(f"Unexpected API operation: {path}")

    def approvals(self):
        return [
            call.args[0]
            for call in self.module.api.call_args_list
            if call.args[0].endswith("/approve")
        ]

    def test_up_to_date_held_run_is_approved_then_exact_head_merge_is_armed(self):
        self.module.reconcile(1)
        self.assertEqual(self.approvals(), ["actions/runs/10/approve"])
        self.process.assert_called_once_with(
            [
                "gh",
                "pr",
                "merge",
                "--repo",
                REPO,
                "--auto",
                "--squash",
                "--match-head-commit",
                "old",
                "1",
            ],
            check=True,
        )

    def test_branch_update_uses_new_head_not_old_held_run(self):
        self.behind = 1
        self.runs = [run(), run("new", id=11)]
        self.module.reconcile(1)
        self.assertEqual(self.approvals(), ["actions/runs/11/approve"])
        self.assertIn("new", self.process.call_args.args[0])
        self.assertTrue(
            any(
                "head_sha=new" in call.args[0]
                for call in self.module.api.call_args_list
            )
        )

    def test_asynchronous_branch_update_waits_for_new_head(self):
        self.behind = 1
        original = self.api
        reads = 0

        def delayed(path, *args, **kwargs):
            nonlocal reads
            if path == "pulls/1":
                reads += 1
                if reads == 2:
                    return pull()
            return original(path, *args, **kwargs)

        self.module.api.side_effect = delayed
        self.module.reconcile(1)
        self.sleep.assert_called_once_with(2)

    def test_pending_update_timeout_never_approves_old_runs(self):
        self.behind = 1
        original = self.api
        self.module.api.side_effect = lambda path, *args, **kwargs: (
            {} if path.endswith("update-branch") else original(path, *args, **kwargs)
        )
        with self.assertRaisesRegex(RuntimeError, "still pending"):
            self.module.reconcile(1)
        self.assertEqual(self.sleep.call_count, 10)
        self.assertEqual(self.approvals(), [])
        self.process.assert_not_called()

    def test_closed_pr_during_update_is_not_processed(self):
        self.behind = 1
        original = self.api

        def close(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path.endswith("update-branch"):
                self.pr["state"] = "closed"
            return result

        self.module.api.side_effect = close
        with self.assertRaisesRegex(RuntimeError, "no longer eligible"):
            self.module.reconcile(1)
        self.assertEqual(self.approvals(), [])

    def test_late_run_is_recovered_on_next_reconciliation(self):
        self.runs = []
        self.module.reconcile(1)
        self.assertEqual(self.approvals(), [])
        self.pr["auto_merge"] = {"merge_method": "squash"}
        self.runs = [run()]
        self.module.reconcile(1)
        self.assertEqual(self.approvals(), ["actions/runs/10/approve"])
        self.assertEqual(self.process.call_count, 1)

    def test_only_latest_matching_ci_run_is_used(self):
        self.runs = [run(), run(conclusion="success", id=11)]
        self.module.reconcile(1)
        self.assertEqual(self.approvals(), [])
        self.process.assert_called_once()

    def test_foreign_stale_and_non_ci_runs_are_never_approved(self):
        self.runs = [
            run("stale"),
            run(event="push"),
            run(path=".github/workflows/other.yml"),
            run(head_repository={"full_name": "someone/fillable"}),
            run(pull_requests=[]),
            run(pull_requests=[{"number": 2, "head": {"sha": "old"}}]),
            run(pull_requests=[{"number": 1, "head": {"sha": "stale"}}]),
        ]
        self.module.reconcile(1)
        self.assertEqual(self.approvals(), [])

    def test_failed_ci_is_not_retried_or_armed(self):
        for conclusion in self.module.FAILED:
            with self.subTest(conclusion=conclusion):
                self.runs = [run(conclusion=conclusion)]
                self.module.reconcile(1)
        self.process.assert_not_called()
        self.assertEqual(self.approvals(), [])

    def test_in_progress_ci_can_wait_behind_the_merge_gate(self):
        self.runs = [run(conclusion=None)]
        self.module.reconcile(1)
        self.process.assert_called_once()
        self.assertEqual(self.approvals(), [])

    def test_changed_head_or_eligibility_blocks_approval(self):
        original = self.api
        for replacement in (pull("changed"), pull(state="closed")):
            with self.subTest(replacement=replacement):
                reads = 0

                def changed(path, *args, **kwargs):
                    nonlocal reads
                    if path == "pulls/1":
                        reads += 1
                        if reads > 1:
                            return replacement
                    return original(path, *args, **kwargs)

                self.module.api.side_effect = changed
                with self.assertRaisesRegex(
                    RuntimeError, "changed during reconciliation"
                ):
                    self.module.reconcile(1)
        self.assertEqual(self.approvals(), [])
        self.process.assert_not_called()

    def test_human_fork_draft_closed_and_wrong_base_prs_are_ignored(self):
        candidates = [
            pull(user={"login": "human"}),
            pull(draft=True),
            pull(state="closed"),
        ]
        for section, key, value in (
            ("head", "repo", None),
            ("head", "repo", {"full_name": "fork/repo"}),
            ("head", "ref", "feature/change"),
            ("base", "ref", "dev"),
            ("base", "repo", {"full_name": "fork/repo"}),
        ):
            candidate = pull()
            candidate[section][key] = value
            candidates.append(candidate)
        for candidate in candidates:
            self.pr = candidate
            self.module.reconcile(1)
        self.assertEqual(self.approvals(), [])
        self.process.assert_not_called()

    def test_api_failures_are_not_silently_treated_as_up_to_date(self):
        original = self.api

        def denied(path, *args, **kwargs):
            if path.startswith("compare/") or path.endswith("/approve"):
                raise RuntimeError("API denied")
            return original(path, *args, **kwargs)

        self.module.api.side_effect = denied
        with self.assertRaisesRegex(RuntimeError, "API denied"):
            self.module.reconcile(1)
        self.process.assert_not_called()

    def test_main_processes_all_pages_and_reports_approval_failure(self):
        self.pages = [[pull(user={"login": "human"})], [pull(), pull(number=2)]]
        original = self.api

        def denied(path, *args, **kwargs):
            if path.endswith("/approve"):
                raise RuntimeError("Approval denied")
            if path == "pulls/2":
                return pull(number=2, user={"login": "human"})
            return original(path, *args, **kwargs)

        self.module.api.side_effect = denied
        with self.assertRaisesRegex(RuntimeError, "Reconciliation failed for PRs"):
            self.module.main()
        self.assertTrue(
            any(call.args[0] == "pulls/2" for call in self.module.api.call_args_list)
        )

    def test_main_success_and_unexpected_repository(self):
        self.module.main()
        self.module.REPO = "wrong/repository"
        with self.assertRaisesRegex(RuntimeError, "Unexpected repository"):
            self.module.main()

    def test_api_transport_handles_pagination_fields_and_empty_response(self):
        fresh = types.ModuleType("fresh")
        with patch.dict(os.environ, REPO=REPO):
            exec(compile(CODE, str(SOURCE), "exec"), fresh.__dict__)
        with patch.object(
            fresh.subprocess, "check_output", return_value='[{"ok": true}]'
        ) as request:
            self.assertEqual(
                fresh.api("path", "PUT", {"expected_head_sha": "abc"}, pages=True),
                [{"ok": True}],
            )
            request.assert_called_once_with(
                [
                    "gh",
                    "api",
                    "--method",
                    "PUT",
                    f"repos/{REPO}/path",
                    "--paginate",
                    "--slurp",
                    "-f",
                    "expected_head_sha=abc",
                ],
                text=True,
            )
            request.return_value = ""
            self.assertIsNone(fresh.api("path", "POST"))

    def test_workflow_entrypoint_runs_without_loading_pr_code(self):
        with patch.dict(os.environ, REPO=REPO), patch(
            "subprocess.check_output", return_value="[]"
        ):
            runpy.run_path(str(SOURCE), run_name="__main__")

    def test_workflow_permissions_triggers_and_trust_boundaries(self):
        for required in (
            "pull_request_target:",
            "push:",
            "workflow_run:",
            "workflow_dispatch:",
            "workflows: [CI]",
            "types: [completed]",
            'cron: "13,43 * * * *"',
            "actions: write",
            "pull-requests: write",
            "contents: write",
            "github.repository == 'Flippylolz/fillable'",
            "cancel-in-progress: false",
        ):
            self.assertIn(required, WORKFLOW)
        for forbidden in (
            "actions/checkout",
            "--admin",
            "ship-release.sh",
            "workflow run",
            "continue-on-error",
        ):
            self.assertNotIn(forbidden, WORKFLOW)
        self.assertNotIn("secrets.", WORKFLOW.replace("secrets.GITHUB_TOKEN", ""))
        self.assertIn(
            "test_dependabot_automerge_contract.py",
            (ROOT / ".github/workflows/ci.yml").read_text(),
        )


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
