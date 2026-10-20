# Dependency review — 2026-10-20

Reviewed pending Dependabot PRs #170 (Python), #171 (ingress nginx), #172
(PostgreSQL digest), #174 (upload-artifact), #178 (Docker) and #179 (npm).
GitHub requires an up-to-date `ci-required` from Actions app 15368, with no
mandatory human approvals; repository squash auto-merge is enabled. No gate or
coverage threshold is relaxed.

## npm compatibility fixes in PR #179

The Playwright 1.64.1 npm update must ship with its matching pinned browser image.
The previous image contains different browser revisions, so browser, development
and upgrade CI fail before exercising application behavior. Use the exact image
and digest already proposed by Docker PR #178.

Vitest 5.0.5 enables filesystem module caching by default. The frontend image runs
tests as `node`, while npm installs `node_modules` as root; writing its default
`.vitest-cache` there fails with EACCES. Set `test.fsModuleCachePath` to a dedicated
writable `/tmp` directory, retaining the existing Vite cache and full test/coverage
configuration. See [upstream cache configuration](https://main.vitest.dev/config/fsmodulecache).

## Shared independent rendering prerequisite

PR #180 (E09.45) refreshes the unavailable LibreOffice deb13u7 QA pin to deb13u8.
This is a shared development-CI failure, independent of the dependency changes.
The pinned image builds locally and its tools run as the configured unprivileged
user. Required CI must verify the existing synthetic rendering assertions.

## Review evidence

- #170 retains hash-locked installation and updates its direct pins and compiled
  requirements together. Required tests cover the FastAPI/SQLAlchemy behavior,
  real PostgreSQL, migration/upgrade persistence, lint and generated API drift.
- #171 changes only Fillable's ingress image pin; no shared nginx configuration
  changes. #172 changes only the same PostgreSQL image digest in both runtime and
  tests, retaining major version 18 and the persistent volume contract.
- #174 updates every upload-artifact use to the exact upstream v7.0.2 tag commit
  `cf430e030ddbb5b0abf93d22962f4752f3646cd9`; permissions and required jobs remain
  unchanged. Upstream release notes describe retry handling and an artifact
  library update.
- #178 retains exact Python/Node/nginx/browser image pins. Its Playwright image
  must match #179 before merging; its QA base still needs E09.45's package fix.
- #179 retains exact direct dependency versions and lockfile integrity, including
  matching React/React DOM and Vitest/coverage versions. Editor notices are still
  generated and checked in the production build.

Local Docker verification for #179 passed all 448 frontend tests, ESLint,
Ukrainian/English catalogs and the production build. The source-provenance coverage
gate passed 2010/2010 lines and 2308/2308 branch outcomes. The matching browser
image launches Chromium as `pwuser` and edits a synthetic Ukrainian input. Full
application browser/upgrade checks and backend coverage remain delegated to CI.

All six PRs are queued for exact-head squash auto-merge behind the actual strict
required gate. Final CI coverage and merge evidence remain pending.
