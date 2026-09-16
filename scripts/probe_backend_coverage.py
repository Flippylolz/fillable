"""Negative verification runs only in a disposable backend test container."""

import subprocess
from pathlib import Path

from check_coverage import check
from coverage_provenance import record, snapshot

assert Path.cwd() == Path("/app")
probe = Path("app/coverage_probe.py")
assert not probe.exists()
# One unimported branch is enough to violate the exact 100% contract.
try:
    probe.write_text(
        "def untested(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n"
    )
    before = snapshot("backend", "/app")
    subprocess.run(
        [
            "pytest",
            "--cov=app",
            "--cov-branch",
            "--cov-report=json:coverage/coverage.json",
        ],
        check=True,
    )
    record("backend", "/app", before)
    try:
        check("backend", "/app")
    except ValueError as error:
        assert "below 100%" in str(error), error
        print(f"PASS: real unimported backend source blocked: {error}")
    else:
        raise AssertionError("Uncovered backend source did not block the gate")
finally:
    probe.unlink()
