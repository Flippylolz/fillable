"""Bind a successful coverage run to unchanged application source and report bytes."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def report_path(scope, root):
    names = {"backend": "coverage.json", "frontend": "coverage-summary.json"}
    if scope not in names:
        raise ValueError("Unknown scope")
    return Path(root) / "coverage" / names[scope]


def snapshot(scope, root):
    report_path(scope, root)  # Validate scope before choosing source paths.
    root = Path(root)
    source = root / ("app" if scope == "backend" else "src")
    suffixes = {".py"} if scope == "backend" else {".ts", ".tsx"}
    paths = [source, *source.rglob("*")]
    if any(path.is_symlink() for path in paths):
        raise ValueError("Symlink in coverage source")
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.is_file() and path.suffix in suffixes
    }
    if not files:
        raise ValueError("Empty coverage source")
    return files


def record(scope, root, before):
    if snapshot(scope, root) != before:
        raise ValueError("Source changed during coverage run")
    report = report_path(scope, root)
    payload = {
        "version": 1,
        "scope": scope,
        "sources": before,
        "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
    }
    report.with_name("provenance.json").write_text(json.dumps(payload, sort_keys=True))


def verify(scope, root):
    report = report_path(scope, root)
    # Read once: the checker parses these exact digest-verified bytes.
    data = report.read_bytes()
    payload = json.loads(report.with_name("provenance.json").read_text())
    expected = {
        "version": 1,
        "scope": scope,
        "sources": snapshot(scope, root),
        "report_sha256": hashlib.sha256(data).hexdigest(),
    }
    if (
        not isinstance(payload, dict)
        or type(payload.get("version")) is not int
        or payload != expected
    ):
        raise ValueError("Stale or invalid coverage provenance")
    return data


if __name__ == "__main__":
    scope, directory, *command = sys.argv[1:]
    report_path(scope, directory).with_name("provenance.json").unlink(missing_ok=True)
    report_path(scope, directory).unlink(missing_ok=True)
    before = snapshot(scope, directory)
    subprocess.run(command, cwd=directory, check=True)
    record(scope, directory, before)
