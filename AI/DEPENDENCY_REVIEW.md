# Dependency review — 2026-10-20

Reviewed the Python, ingress nginx, PostgreSQL, GitHub Actions, Docker and npm
Dependabot updates. The five completed dependency merges below passed every
required job. This document accompanies the final Docker update in PR #178;
its own final CI and merge receipt is recorded in that PR after GitHub merges it.

## Merge evidence

| PR | Update | Merge commit | Successful exact-head CI |
| --- | --- | --- | --- |
| [#170](https://github.com/Flippylolz/fillable/pull/170) | Python direct pins and hash-locked requirements | [3fd16a9](https://github.com/Flippylolz/fillable/commit/3fd16a969635fef3b07614a4d529e9301ff81ddb) | [39447063684](https://github.com/Flippylolz/fillable/actions/runs/39447063684) |
| [#171](https://github.com/Flippylolz/fillable/pull/171) | Fillable ingress nginx 1.31.6 | [05f233e](https://github.com/Flippylolz/fillable/commit/05f233e3add181edd28ea8b9ad8b454769b5cdd1) | [39449282369](https://github.com/Flippylolz/fillable/actions/runs/39449282369) |
| [#172](https://github.com/Flippylolz/fillable/pull/172) | PostgreSQL 18.6 digest in runtime and tests; acceptance recovery | [d4ba592](https://github.com/Flippylolz/fillable/commit/d4ba592d175dc213e5b6d43d0056ae985bb63239) | [39455874090](https://github.com/Flippylolz/fillable/actions/runs/39455874090) |
| [#174](https://github.com/Flippylolz/fillable/pull/174) | upload-artifact v7.0.2 | [7a7e323](https://github.com/Flippylolz/fillable/commit/7a7e3233ea748aaa4799dc690e11fc4f44488e9f) | [39444961486](https://github.com/Flippylolz/fillable/actions/runs/39444961486) |
| [#179](https://github.com/Flippylolz/fillable/pull/179) | Locked npm updates and matching test containers | [39459af](https://github.com/Flippylolz/fillable/commit/39459afa5bfacb7d4ea9ba28f0facefcba6e7207) | [39440218433](https://github.com/Flippylolz/fillable/actions/runs/39440218433) |
| [#180](https://github.com/Flippylolz/fillable/pull/180) | E09.45 independent rendering prerequisite | [97af8ee](https://github.com/Flippylolz/fillable/commit/97af8ee5275cced4638b0705772786b39a13eb5c) | [39437778907](https://github.com/Flippylolz/fillable/actions/runs/39437778907) |
| [#182](https://github.com/Flippylolz/fillable/pull/182) | E09.48 settings echoes and pending copy replay | [e2f5129](https://github.com/Flippylolz/fillable/commit/e2f512906729f863746a00955be5547f055aa498) | [39460987038](https://github.com/Flippylolz/fillable/actions/runs/39460987038) |

PR [#182](https://github.com/Flippylolz/fillable/pull/182), E09.48, explicitly
checks controlled settings-toggle echoes and pending copy replay. Its complete
required CI passed, including development/independent rendering and all browser
scenarios. The final Docker update incorporates every prerequisite above.

GitHub protection was verified through its API: strict up-to-date `ci-required`
bound to Actions app 15368, zero mandatory human approvals, and squash auto-merge
available. GitHub refused superseded heads when main advanced. Every completed
merge used the protected gate, including both independent 100% executable-line
and branch checks. Coverage thresholds, source inclusion and required jobs remain
unchanged. Each PR body contains its final merge receipt.

## Compatibility and test repairs

- The Playwright 1.64.1 npm package and pinned browser image now ship together in
  #179. Browser, development and upgrade jobs launch their matching binaries.
- The upgraded Vitest filesystem module cache defaults into root-owned
  `node_modules`. `test.fsModuleCachePath` now points to writable
  `/tmp/fillable-vitest-cache` for the non-root runner; the existing Vite cache and
  coverage configuration remain intact. See the [cache configuration](https://main.vitest.dev/config/fsmodulecache).
- #180 refreshes the unavailable LibreOffice deb13u7 QA pin to deb13u8. The exact
  package pins and independent synthetic DOCX rendering assertions are retained.
- #182 explicitly dispatches native settings-toggle echoes and checks duplicate
  callbacks, real open/close requests and controlled reconciliation/remounts.
  This replaces incidental jsdom event delivery that once left 2307/2308 branch
  outcomes covered while all frontend tests passed. It also forces a pending
  template-copy replay after losing the committed response, preserving the form
  and one nonempty idempotency key through bounded real UI retries. The existing
  single-charge, field-snapshot and copy-independence assertions remain enforced.
- #172 forces one documented `operation_in_progress` content-read response, uses
  the real Retry opening UI with at most three retries, and requires successful
  content loading before the unchanged document/history assertions. A persistent
  conflict still fails. Its bilingual fixture restores Ukrainian before/after the
  test, including on failure, preventing language cascades. Maintenance and storage
  locking remain active; application behavior is unchanged.

## Final Docker integration

PR #178 retains exact image digests while updating Python to 3.14.8 in backend
and QA images, Node to 26.12.0 for frontend tooling, and the private gateway to
nginx 1.31.7. Its matching Playwright image is already integrated through #179.
The PostgreSQL major version, persistent volume contract, application storage
policy and owner-managed ingress configuration are preserved.

Local runtime validation passed 448 frontend tests, lint, catalogs, production
build and the source-provenance gate: 2010/2010 lines and 2308/2308 branches.
Python 3.14.8 Ruff/mypy checks passed; the production gateway builds and its nginx
configuration validates as the configured non-root user. The new QA image builds
and its LibreOffice/PDF tools execute as its non-root user. The matching Playwright
image launches Chromium and edits synthetic Ukrainian input.

The settings regression passed three local runs plus the full frontend suite.
The bilingual recovery journey passed on desktop/mobile in an isolated synthetic
stack with maintenance active. A temporary negative control injected four busy
responses, observed the intended failure after three retries, and verified through
a fresh login that Ukrainian cleanup still completed. Only task-owned services
were stopped; their test volumes were retained.

The full library journey also passed on desktop/mobile with the forced pending
copy replay and its single-key/single-charge checks. A temporary persistent-copy
variant failed at the intended 201 assertion after the bounded retries.

Retained #179 CI reports measure backend 4595/4595 lines and 1488/1488 branches,
frontend 2010/2010 lines and 2308/2308 branches. #180 used the earlier frontend
instrumentation counts (2006/2006 and 2296/2296). Final integrated Docker coverage
and required-check evidence are recorded in #178's receipt after its own full CI.
