// Run the real frontend suite and bind its report to unchanged source bytes.
import { createHash } from 'node:crypto';
import { lstatSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
function snapshot(path = 'src', files = {}) {
  const stat = lstatSync(path);
  if (stat.isSymbolicLink()) throw new Error('Symlink in coverage source');
  if (stat.isDirectory()) {
    for (const name of readdirSync(path).sort()) snapshot(`${path}/${name}`, files);
  } else if (stat.isFile() && /\.(ts|tsx)$/.test(path)) {
    files[path] = digest(readFileSync(path));
  }
  return files;
}

rmSync('coverage/provenance.json', { force: true });
rmSync('coverage/coverage-summary.json', { force: true });
const before = snapshot();
if (!Object.keys(before).length) throw new Error('Empty coverage source');
const result = spawnSync('npm', ['test', ...process.argv.slice(2)], { stdio: 'inherit' });
if (result.error || result.status !== 0) process.exit(result.status || 1);
if (JSON.stringify(before) !== JSON.stringify(snapshot())) {
  throw new Error('Source changed during coverage run');
}
writeFileSync('coverage/provenance.json', JSON.stringify({
  version: 1,
  scope: 'frontend',
  sources: before,
  report_sha256: digest(readFileSync('coverage/coverage-summary.json')),
}));
