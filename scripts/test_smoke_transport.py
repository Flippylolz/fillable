"""Exercise the shell's provisioning decision with synthetic executables only."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

SOURCE = "a" * 40
DIGEST = "b" * 64
with tempfile.TemporaryDirectory(prefix="fillable-smoke-transport.") as directory:
    root = Path(directory)
    (root / "docker").write_text(
        """#!/bin/sh
printf '%s\n' "$*" >> "$PROOF_CALLS"
case " $* " in
*' login '*)
  case "$PROOF_MODE" in
    existing) exit 0 ;;
    unavailable) exit 1 ;;
    *) exit 3 ;;
  esac ;;
*' smoke '*)
  test "$PROOF_MODE" != smoke_failed || exit 1
  printf '{"status":"succeeded"}' > "$PROOF_OUTPUT/public-smoke.json" ;;
*) exit 1 ;;
esac
"""
    )
    (root / "ssh").write_text(
        """#!/bin/sh
for command do :; done
printf '%s\n' "$command" >> "$PROOF_CALLS"
cat > "$PROOF_OUTPUT/private-input.json"
test "$PROOF_MODE" != provision_failed || exit 1
if test "$PROOF_MODE" = bad_receipt; then printf '{}';
else printf '{"source_sha":"%s","provisioned":true}' "$PROOF_SHA"; fi
"""
    )
    for executable in ("docker", "ssh"):
        (root / executable).chmod(0o700)
    for mode in (
        "existing",
        "new",
        "unavailable",
        "provision_failed",
        "bad_receipt",
        "smoke_failed",
    ):
        output = root / mode
        output.mkdir()
        (output / "artifact.json").write_text(
            json.dumps({"source_sha": SOURCE, "sha256": DIGEST})
        )
        (output / "manifest.json").write_text(
            json.dumps({"images": {"backend": {"id": "sha256:" + DIGEST}}})
        )
        (output / "public-smoke.json").write_text('{"status":"stale"}')
        environment = {
            **os.environ,
            "PATH": str(root) + ":" + os.environ["PATH"],
            "FILLABLE_DEPLOY_HOST": "synthetic.invalid",
            "FILLABLE_DEPLOY_USER": "synthetic",
            "FILLABLE_DEPLOY_KEY": "synthetic-key",
            "FILLABLE_KNOWN_HOSTS": "synthetic-host-key",
            "FILLABLE_INITIAL_EMAIL": "synthetic@example.test",
            "FILLABLE_INITIAL_PASSWORD": "private-synthetic-password",
            "PROOF_MODE": mode,
            "PROOF_CALLS": str(output / "calls"),
            "PROOF_OUTPUT": str(output),
            "PROOF_SHA": SOURCE,
        }
        result = subprocess.run(
            ["sh", "scripts/smoke-release.sh", SOURCE, str(output)],
            env=environment,
            capture_output=True,
        )
        assert (result.returncode == 0) == (mode in {"existing", "new"}), mode
        calls = (output / "calls").read_text()
        assert "private-synthetic-password" not in calls
        assert b"private-synthetic-password" not in result.stdout + result.stderr
        if mode in {"existing", "unavailable"}:
            assert "provision " not in calls
        else:
            assert json.loads((output / "private-input.json").read_text()) == {
                "email": environment["FILLABLE_INITIAL_EMAIL"],
                "password": environment["FILLABLE_INITIAL_PASSWORD"],
            }
        assert (output / "public-smoke.json").exists() == (result.returncode == 0)
        print(mode + ": PASS")
