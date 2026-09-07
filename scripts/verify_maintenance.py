"""Read-only proof that the actual Compose scheduler completes bounded work."""

import sys
import time

from app.infrastructure import database
from app.maintenance_schema import report

if sys.argv[1:] == ["identity"]:
    with database().connect() as connection:
        print(report(connection)["run_id"])
    raise SystemExit(0)

previous = sys.argv[1] if len(sys.argv) == 2 else None
for _ in range(40):
    with database().connect() as connection:
        assert connection.exec_driver_sql("SHOW statement_timeout").scalar_one() == "5s"
        assert connection.exec_driver_sql("SHOW lock_timeout").scalar_one() == "2s"
        result = report(connection)
    if result["last_success_at"] is not None and result["run_id"] != previous:
        assert result["status"] in ("succeeded", "running")
        print("PASS: scheduled maintenance completed with scoped SQL timeouts")
        break
    if result["status"] == "failed":
        raise SystemExit("FAIL: scheduled maintenance reported failure")
    time.sleep(1)
else:
    raise SystemExit("FAIL: scheduled maintenance did not complete in 40 seconds")
