# E09.42 — Adversarial validation audit

Date: 2026-09-17. Scope: local synthetic API requests and frontend regressions.
No production accounts or user documents are used.

## Confirmed gaps and fixes

- A valid authenticated save accepted `NaN` in a field whose reviewed type was
  `number` (HTTP 201). Backend save validation now checks actual field text against
  the same number grammar and calendar rules as the frontend. Dates use ASCII
  digits, real Gregorian dates, ISO or the existing day-first formats. Empty fields
  remain allowed. Validation preserves the user's exact text, including decimal
  commas, grouping spaces and Ukrainian Unicode.
- Field values now have a backend save limit of 65,536 code points across all
  runs, including when review metadata is absent. Invalid XML characters fail before
  export. Splitting a value across runs cannot evade the limit.
- A NUL inside a profile display name or login reached database operations and
  returned HTTP 500. Both now fail at request validation with HTTP 422; frontend
  checks prevent submission and retain the draft with existing localized feedback.
- Title validation now checks UTF-8 encoding in the shared upload/copy/rename
  validator, extending the existing rename defense to all title entry points.

## Test method

`backend/tests/test_validation_monkey.py` sends requests directly through the real
FastAPI application with authenticated sessions, real PostgreSQL and isolated storage.
It bypasses frontend code. Fixed boundary probes cover wrong JSON types, empty and
oversized inputs, Unicode/NUL, language enums, credential lengths, typed values,
malformed document roots and 128 seeded nested-node mutations (seed 942).
Valid controls prove the same endpoint accepts a well-formed typed value.
Rejected saves must leave quota usage/reservations and the current resource unchanged.

`test_field_values.py` covers calendar/leap-year boundaries, number grammar, exact
ECMAScript whitespace behavior, XML characters, astral code-point lengths and values
split across runs. Matching frontend vectors exercise the same accepted/rejected
number and date examples. Existing suites cover body/content-length limits, DOCX
ZIP/XML admission, field labels/keys/anchors, strict booleans, revision and lease
fences, owner isolation, CSRF/origin, quotas, idempotency and failure cleanup.

Review types remain user-editable. Uploads and retained historical revisions preserve
source text even when a detector proposes a type incompatible with it; new saves
require valid values or an explicit type correction. Password confirmation is a
frontend-only duplicate-input check: the backend validates the submitted new password
and verifies the current credential. Search, zoom and highlighting are local UI state
and do not grant backend authority.

## Verification record

Targeted adversarial API regression passed after the fixes. Full backend/frontend
coverage, static checks and protected CI results are recorded in the E09.42 epic
entry and PR. This finite, reproducible test pass cannot prove every possible input
is safe; it establishes the tested boundaries and prevents the confirmed regressions.

Local final results: 594 backend tests, 4595/4595 executable lines and 1488/1488
branches; 439 frontend tests, 2001/2001 lines and 2282/2282 branches. Both raw
coverage gates passed. Ruff/mypy, ESLint, catalogs and production frontend build
passed. The user explicitly authorized publishing the verified changes; GitHub
required CI and protected merge evidence are recorded in the task PR.
