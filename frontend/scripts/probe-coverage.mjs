import assert from 'node:assert/strict';
import fs from 'node:fs';
import { spawnSync } from 'node:child_process';

assert.equal(process.cwd(), '/app');
const probe = 'src/coverage_probe.ts';
assert.equal(fs.existsSync(probe), false);
// Scale the deliberately uncovered source with the application so growth cannot
// make this negative test pass the line gate while only failing the branch gate.
const sourceLines = fs.readdirSync('src', { recursive: true })
  .filter(path => /\.(ts|tsx)$/.test(path))
  .reduce((total, path) => total + fs.readFileSync(`src/${path}`, 'utf8').split('\n').length, 0);
try {
  fs.writeFileSync(probe, 'export function untested(value: number) {\n' + Array.from({ length: Math.max(30, sourceLines) }, (_, i) => `  if (value === ${i}) return ${i};\n`).join('') + '  return -1;\n}\n');
  fs.mkdirSync('coverage', { recursive: true });
  fs.writeFileSync('coverage/provenance.json', 'old successful stamp');
  const run = spawnSync(process.execPath, ['scripts/coverage-provenance.mjs', '--', '--reporter=json', '--outputFile=/tmp/probe-results.json'], { encoding: 'utf8' });
  assert.equal(run.status, 1, run.stdout + run.stderr);
  assert.equal(fs.existsSync('coverage/provenance.json'), false);
  const results = JSON.parse(fs.readFileSync('/tmp/probe-results.json'));
  const failures = results.testResults.flatMap(suite => suite.assertionResults
    .filter(test => test.status === 'failed')
    .map(test => `${test.fullName}\n${test.failureMessages.join('\n')}`)).join('\n');
  assert.equal(results.numFailedTests, 0, failures);
  assert.equal(results.numFailedTestSuites, 0, failures || run.stdout + run.stderr);
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
