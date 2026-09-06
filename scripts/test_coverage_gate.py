import json
import tempfile
import unittest
from pathlib import Path

from check_coverage import check, require_metric


class CoverageGateTests(unittest.TestCase):
    def test_raw_boundary_and_invalid_counts(self):
        for covered, total in [(90, 100), (0, 0), (100, 100)]:
            require_metric(covered, total)
        for covered, total in [(8999, 10000), (89, 100), (-1, 100), (101, 100), (90.0, 100), (True, 1)]:
            with self.assertRaises(ValueError):
                require_metric(covered, total)

    def test_missing_empty_invalid_and_unimported_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "app/main.py").write_text("value = 1\n")
            with self.assertRaises(FileNotFoundError):
                check("backend", root)
            (root / "coverage").mkdir()
            report = root / "coverage/coverage.json"
            report.write_text("invalid")
            with self.assertRaises(ValueError):
                check("backend", root)
            payload = {"files": {}, "totals": {"covered_lines": 90, "num_statements": 100, "covered_branches": 9, "num_branches": 10}}
            report.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                check("backend", root)
            payload["files"] = {"app/main.py": {}}
            report.write_text(json.dumps(payload))
            check("backend", root)
            payload["totals"]["covered_branches"] = 8
            report.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                check("backend", root)


if __name__ == "__main__":
    unittest.main()
