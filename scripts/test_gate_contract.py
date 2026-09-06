import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from check_coverage import check


class GateContractTests(unittest.TestCase):
    def test_aggregator_rejects_every_non_success_state(self):
        script = str(Path(__file__).with_name('require-ci-success.sh'))
        for arguments in [[], [''], ['failure'], ['skipped'], ['cancelled'],
                          ['pending'], ['success', 'failure']]:
            self.assertNotEqual(subprocess.run([script, *arguments]).returncode, 0)
        self.assertEqual(subprocess.run([script, 'success', 'success']).returncode, 0)

    def test_each_scope_metric_and_missing_source(self):
        for scope in ('backend', 'frontend'):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / ('app' if scope == 'backend' else 'src')
                source.mkdir()
                filename = 'module.py' if scope == 'backend' else 'module.ts'
                (source / filename).write_text('value = 1\n')
                reports = root / 'coverage'
                reports.mkdir()
                path = reports / ('coverage.json' if scope == 'backend' else 'coverage-summary.json')
                with self.assertRaises(FileNotFoundError):
                    check(scope, root)
                for lines, branches, passes in [(90, 90, True), (89, 100, False),
                                                 (100, 89, False)]:
                    if scope == 'backend':
                        payload = {'files': {'app/module.py': {}}, 'totals': {
                            'covered_lines': lines, 'num_statements': 100,
                            'covered_branches': branches, 'num_branches': 100}}
                    else:
                        payload = {'/app/src/module.ts': {}, 'total': {
                            'lines': {'covered': lines, 'total': 100},
                            'branches': {'covered': branches, 'total': 100}}}
                    path.write_text(json.dumps(payload))
                    if passes:
                        check(scope, root)
                    else:
                        with self.assertRaises(ValueError):
                            check(scope, root)
                (source / ('extra.py' if scope == 'backend' else 'extra.ts')).write_text('value = 2\n')
                with self.assertRaises(ValueError):
                    check(scope, root)
                path.write_text('{}')
                with self.assertRaises((KeyError, ValueError)):
                    check(scope, root)


if __name__ == '__main__':
    unittest.main()
