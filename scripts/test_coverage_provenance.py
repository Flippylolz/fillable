"""Exercise stale-report and failed-run rejection with real subprocesses."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from check_coverage import check
from coverage_provenance import record, report_path, snapshot


class ProvenanceTests(unittest.TestCase):
    def test_changed_source_report_and_invalid_stamps_fail_both_scopes(self):
        for scope in ("backend", "frontend"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / (
                    "app/module.py" if scope == "backend" else "src/module.ts"
                )
                source.parent.mkdir()
                source.write_text("value = 1\n")
                report = report_path(scope, root)
                report.parent.mkdir()
                payload = (
                    {
                        "files": {"app/module.py": {}},
                        "totals": {
                            "covered_lines": 1,
                            "num_statements": 1,
                            "covered_branches": 0,
                            "num_branches": 0,
                        },
                    }
                    if scope == "backend"
                    else {
                        "/app/src/module.ts": {},
                        "total": {
                            "lines": {"covered": 1, "total": 1},
                            "branches": {"covered": 0, "total": 0},
                        },
                    }
                )
                report.write_text(json.dumps(payload))
                before = snapshot(scope, root)
                record(scope, root, before)
                check(scope, root)
                source.write_text("value = 2\n")
                with self.assertRaisesRegex(ValueError, "provenance"):
                    check(scope, root)
                with self.assertRaisesRegex(ValueError, "changed during"):
                    record(scope, root, before)
                source.write_text("value = 1\n")
                source.unlink()
                with self.assertRaises(ValueError):
                    check(scope, root)
                source.write_text("value = 1\n")
                report.write_text(json.dumps(payload) + " ")
                with self.assertRaisesRegex(ValueError, "provenance"):
                    check(scope, root)
                record(scope, root, before)
                stamp = report.with_name("provenance.json")
                valid = json.loads(stamp.read_text())
                for invalid in [
                    None,
                    {},
                    {**valid, "version": True},
                    {**valid, "version": 2},
                    {**valid, "scope": "other"},
                ]:
                    stamp.write_text(json.dumps(invalid))
                    with self.assertRaisesRegex(ValueError, "provenance"):
                        check(scope, root)
                stamp.unlink()
                with self.assertRaises(FileNotFoundError):
                    check(scope, root)
                report.unlink()
                with self.assertRaises(FileNotFoundError):
                    record(scope, root, before)
                source.with_name("linked" + source.suffix).symlink_to(source)
                with self.assertRaisesRegex(ValueError, "Symlink"):
                    snapshot(scope, root)

    def test_failed_run_invalidates_old_stamp_and_source_mutation_cannot_be_signed(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "app/module.py").write_text("value = 1\n")
            (root / "coverage").mkdir()
            report_path("backend", root).write_text("{}")
            stamp = root / "coverage/provenance.json"
            command = [
                sys.executable,
                str(Path(__file__).with_name("coverage_provenance.py")),
                "backend",
                directory,
                sys.executable,
                "-c",
            ]
            for script in [
                "raise SystemExit(1)",
                "from pathlib import Path; "
                "Path('app/module.py').write_text('value = 2')",
            ]:
                stamp.write_text("old successful stamp")
                result = subprocess.run([*command, script], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(stamp.exists())

    def test_real_coverage_report_cannot_be_reused_after_same_filename_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            source = root / "app/module.py"
            source.write_text("value = 1\n")
            command = [
                sys.executable,
                str(Path(__file__).with_name("coverage_provenance.py")),
                "backend", directory, sys.executable, "-c",
                "import coverage, runpy; "
                "c = coverage.Coverage(source=['app'], branch=True); c.start(); "
                "runpy.run_path('app/module.py'); c.stop(); "
                "c.json_report(outfile='coverage/coverage.json')",
            ]
            subprocess.run(command, check=True, capture_output=True)
            check("backend", root)
            source.write_text(
                "value = 1\ndef untested(x):\n    if x:\n        return x\n"
            )
            with self.assertRaisesRegex(ValueError, "provenance"):
                check("backend", root)


if __name__ == "__main__":
    unittest.main()
