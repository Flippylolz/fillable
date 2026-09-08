"""Private smoke and credential-free readiness fail closed without provisioning."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

SOURCE = "a" * 40
DIGEST = "b" * 64
with tempfile.TemporaryDirectory(prefix="fillable-smoke-transport.") as directory:
    root = Path(directory)
    (root / "docker").write_text("""#!/bin/sh
printf '%s\n' "$*" >> "$PROOF_CALLS"
if test "$PROOF_KIND" = public; then
  test -z "${FILLABLE_INITIAL_PASSWORD:-}" || exit 99
  file=public-readiness.json
  receipt='"authenticated_acceptance":"pending"'
else
  file=public-smoke.json
  receipt='"versions_verified":2'
fi
case "$PROOF_MODE" in
  unavailable|invalid_login) exit 3 ;;
  bad_receipt) printf '{}' > "$PROOF_OUTPUT/$file" ;;
  *) printf '{"source_sha":"%s","status":"succeeded",%s}' "$PROOF_SHA" "$receipt" > "$PROOF_OUTPUT/$file" ;;
esac
test "$PROOF_MODE" != failed_after_write
""")
    (root / "ssh").write_text("""#!/bin/sh
printf 'unexpected_ssh\n' >> "$PROOF_CALLS"
exit 99
""")
    for executable in ("docker", "ssh"):
        (root / executable).chmod(0o700)
    for kind in ("private", "public"):
        for mode in (
            "ok",
            "unavailable",
            "invalid_login",
            "bad_receipt",
            "failed_after_write",
            "wrong_source",
            "wrong_image",
            "unapplied",
        ):
            output = root / (kind + "-" + mode)
            output.mkdir()
            (output / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_sha": "c" * 40 if mode == "wrong_source" else SOURCE,
                        "images": {
                            "backend": {
                                "revision": SOURCE,
                                "id": "tag:latest"
                                if mode == "wrong_image"
                                else "sha256:" + DIGEST,
                            }
                        },
                    }
                )
            )
            (output / "deployment.json").write_text(
                json.dumps(
                    {
                        "source_sha": SOURCE,
                        "status": "failed" if mode == "unapplied" else "succeeded",
                    }
                )
            )
            receipt = output / (
                "public-readiness.json" if kind == "public" else "public-smoke.json"
            )
            receipt.write_text('{"status":"stale"}')
            environment = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("FILLABLE_")
            }
            environment.update(
                {
                    "PATH": str(root) + ":" + os.environ["PATH"],
                    "FILLABLE_DEPLOY_HOST": "synthetic.invalid",
                    "PROOF_KIND": kind,
                    "PROOF_MODE": mode,
                    "PROOF_CALLS": str(output / "calls"),
                    "PROOF_OUTPUT": str(output),
                    "PROOF_SHA": SOURCE,
                }
            )
            if kind == "private":
                environment.update(
                    {
                        "FILLABLE_PUBLIC_ORIGIN": "https://synthetic.invalid:3200",
                        "FILLABLE_INITIAL_LOGIN": "Synthetic-user",
                        "FILLABLE_INITIAL_PASSWORD": "private-synthetic-password",
                    }
                )
            script = (
                "check-public-release.sh" if kind == "public" else "smoke-release.sh"
            )
            result = subprocess.run(
                ["sh", "scripts/" + script, SOURCE, str(output)],
                env=environment,
                capture_output=True,
            )
            success = mode == "ok"
            assert (result.returncode == 0) == success, (kind, mode, result.stderr)
            calls = (
                (output / "calls").read_text() if (output / "calls").exists() else ""
            )
            assert "unexpected_ssh" not in calls and "provision " not in calls
            assert "private-synthetic-password" not in calls
            assert b"private-synthetic-password" not in result.stdout + result.stderr
            if kind == "public":
                assert "FILLABLE_INITIAL" not in calls
            assert receipt.exists() == success, (kind, mode)
            print(kind + " " + mode + ": PASS")
