"""Exercise source validation, SVG output and isolated Git publication."""

import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from coverage_provenance import record, snapshot
from render_coverage_badges import render


class CoverageBadgeTests(unittest.TestCase):
    def fixture(self, root):
        for scope, folder, filename in (
            ("backend", "app", "module.py"),
            ("frontend", "src", "module.ts"),
        ):
            source = root / scope / folder
            source.mkdir(parents=True)
            (source / filename).write_text("value = 1\n")
            reports = root / scope / "coverage"
            reports.mkdir()
            if scope == "backend":
                name = "coverage.json"
                payload = {"files": {"app/module.py": {}}, "totals": {
                    "covered_lines": 3, "num_statements": 3,
                    "covered_branches": 2, "num_branches": 2,
                }}
            else:
                name = "coverage-summary.json"
                payload = {"/app/src/module.ts": {}, "total": {
                    "lines": {"covered": 5, "total": 5},
                    "branches": {"covered": 0, "total": 0},
                }}
            (reports / name).write_text(json.dumps(payload))
            record(scope, root / scope, snapshot(scope, root / scope))

    def test_values_accessibility_and_audit_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            render(root, root / "badges", "abc123")
            for scope, branches in (("backend", "100%"), ("frontend", "n/a")):
                svg = ET.parse(root / "badges" / f"{scope}.svg").getroot()
                self.assertEqual(svg.attrib["role"], "img")
                self.assertEqual(svg.attrib["aria-label"], f"{scope} coverage: lines 100% | branches {branches}")
            data = json.loads((root / "badges/coverage.json").read_text())
            self.assertEqual(data["revision"], "abc123")
            self.assertEqual(data["coverage"]["backend"]["lines"], [3, 3])

    def test_missing_stale_and_below_gate_reports_never_publish_output(self):
        for failure in ("missing", "stale", "below"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root)
                report = root / "frontend/coverage/coverage-summary.json"
                if failure == "missing":
                    report.unlink()
                elif failure == "stale":
                    (root / "frontend/src/module.ts").write_text("changed = 2\n")
                else:
                    data = json.loads(report.read_text())
                    data["total"]["lines"]["covered"] = 4
                    report.write_text(json.dumps(data))
                    record("frontend", root / "frontend", snapshot("frontend", root / "frontend"))
                with self.assertRaises((ValueError, FileNotFoundError)):
                    render(root, root / "badges", "abc123")
                self.assertFalse((root / "badges").exists())


if __name__ == "__main__":
    unittest.main()
