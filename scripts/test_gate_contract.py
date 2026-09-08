import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from coverage_provenance import record, snapshot
from check_coverage import check

WORKFLOW = Path("/checks/ci.yml")


def workflow_required_jobs():
    """Read ci-required's aggregated needs from the checked-out workflow."""
    try:
        lines = WORKFLOW.read_text().splitlines()
    except OSError:
        raise AssertionError("Mount the checked-out workflow at /checks/ci.yml")
    try:
        start = lines.index("  ci-required:")
    except ValueError:
        raise AssertionError("ci-required job missing from workflow")
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        needs = re.fullmatch(r"    needs: \[(.+)\]", line)
        if needs:
            jobs = [job.strip() for job in needs.group(1).split(",")]
            assert len(jobs) > 1 and len(set(jobs)) == len(jobs), jobs
            return jobs
    raise AssertionError("ci-required needs list missing from workflow")


class GateContractTests(unittest.TestCase):
    def test_aggregator_rejects_every_non_success_state(self):
        script = str(Path(__file__).with_name("require-ci-success.sh"))
        jobs = workflow_required_jobs()
        self.assertEqual(
            subprocess.run([script, *(["success"] * len(jobs))]).returncode, 0
        )
        # Any position must fail every non-success state.
        states = ("", "failure", "skipped", "cancelled", "pending")
        for index in range(len(jobs)):
            for state in states:
                arguments = ["success"] * len(jobs)
                arguments[index] = state
                result = subprocess.run([script, *arguments]).returncode
                self.assertNotEqual(result, 0)
        # No results at all must fail closed instead of passing vacuously.
        self.assertNotEqual(subprocess.run([script]).returncode, 0)

    def test_each_scope_metric_and_missing_source(self):
        for scope in ("backend", "frontend"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / ("app" if scope == "backend" else "src")
                source.mkdir()
                filename = "module.py" if scope == "backend" else "module.ts"
                (source / filename).write_text("value = 1\n")
                reports = root / "coverage"
                reports.mkdir()
                path = reports / (
                    "coverage.json" if scope == "backend" else "coverage-summary.json"
                )
                with self.assertRaises(FileNotFoundError):
                    check(scope, root)
                for lines, branches, passes in [
                    (90, 90, True),
                    (89, 100, False),
                    (100, 89, False),
                ]:
                    if scope == "backend":
                        payload = {
                            "files": {"app/module.py": {}},
                            "totals": {
                                "covered_lines": lines,
                                "num_statements": 100,
                                "covered_branches": branches,
                                "num_branches": 100,
                            },
                        }
                    else:
                        payload = {
                            "/app/src/module.ts": {},
                            "total": {
                                "lines": {"covered": lines, "total": 100},
                                "branches": {"covered": branches, "total": 100},
                            },
                        }
                    path.write_text(json.dumps(payload))
                    record(scope, root, snapshot(scope, root))
                    if passes:
                        check(scope, root)
                    else:
                        with self.assertRaises(ValueError):
                            check(scope, root)
                (
                    source / ("extra.py" if scope == "backend" else "extra.ts")
                ).write_text("value = 2\n")
                with self.assertRaises(ValueError):
                    check(scope, root)
                path.write_text("{}")
                record(scope, root, snapshot(scope, root))
                with self.assertRaises((KeyError, ValueError)):
                    check(scope, root)


if __name__ == "__main__":
    unittest.main()
