import assert from 'node:assert/strict';
import fs from 'node:fs';
import { spawnSync } from 'node:child_process';

assert.equal(process.cwd(), '/app');
const probe = 'src/coverage_probe.ts';
assert.equal(fs.existsSync(probe), false);
try {
  fs.writeFileSync(probe, 'export function untested(value: number) {\n' + Array.from({ length: 30 }, (_, i) => `  if (value === ${i}) return ${i};\n`).join('') + '  return -1;\n}\n');
  const run = spawnSync('npm', ['test', '--', '--reporter=json', '--outputFile=/tmp/probe-results.json'], { encoding: 'utf8' });
  assert.equal(run.status, 1, run.stdout + run.stderr);
  const results = JSON.parse(fs.readFileSync('/tmp/probe-results.json'));
  assert.equal(results.numFailedTests, 0);
  assert.equal(results.numFailedTestSuites, 0);
  assert.equal(results.numPendingTests, 0);
  assert.ok(results.numPassedTests > 0);
  const report = JSON.parse(fs.readFileSync('coverage/coverage-summary.json'));
  assert.ok(Object.keys(report).some(key => key.endsWith('/src/coverage_probe.ts')));
  const { lines, branches } = report.total;
  assert.ok(lines.covered * 100 < lines.total * 90);
  assert.ok(branches.covered * 100 < branches.total * 90);
  console.log(`PASS: real unimported frontend source blocked: lines ${lines.covered}/${lines.total}, branches ${branches.covered}/${branches.total}; ${results.numPassedTests} tests passed`);
} finally {
  fs.unlinkSync(probe);
}
