# CI, coverage, and final deployment

Status: E01 implements the Docker/coverage/browser foundation below. The actual `main` protection requires up-to-date `ci-required`, including administrators; task PRs have merged through this gate. See the execution ledger and task checkpoints for measured evidence. No live deployment has occurred.

Repository auto-merge was enabled on 2026-09-06. Each task is delivered through its own PR under [PR workflow](PR_WORKFLOW.md). Coverage enforcement and required checks are active; E01.7 audits the completed foundation gate.

## Order of delivery

- E01 establishes Docker-based development and GitHub Actions CI with the coverage gate as soon as application code is scaffolded.
- E02–E06 deliver the MVP while keeping CI green.
- E07 verifies the complete MVP, coverage gate, and operations in local/CI Docker environments.
- **E08 is the final task: deployment through GitHub Actions to `<DEPLOY_USER>@<DEPLOY_HOST>`.** It requires all earlier epics to pass and server access, port allocation, and shared nginx integration to be verified.

Preparing and testing production images/Compose locally is foundation work. Connecting to the live server, configuring its deployment, and running the deployment workflow belong to E08. The target was inspected during E08.1; only isolated temporary port probes have run. See [Deployment target](DEPLOYMENT_TARGET.md), including the requirement to preserve existing services and investigate WEF as a possible nginx owner.

## Mandatory coverage gate

The user requires at least **90% test coverage as a CI blocker**. The implementation default is to apply this independently to backend and frontend, with both executable-line and branch coverage checked separately:

| Scope | Line coverage | Branch coverage | Planned tooling |
| --- | --- | --- | --- |
| First-party Python backend, workers, and maintenance commands | >= 90% | >= 90% | pytest, pytest-cov, coverage.py |
| First-party React/TypeScript application and editor adapter | >= 90% | >= 90% | Vitest with coverage provider |

- Neither a high frontend score nor a high line score may compensate for a failing backend or branch score. Do not average independent gates.
- Check raw counts: `100 * covered >= 90 * total`. Display rounding must not turn a value below 90% into a pass. A valid source set with no branches reports branch coverage as not applicable; missing source/coverage data is an error.
- Measure all eligible application source files, including files no test imports. Do not measure only changed or executed files.
- Limit exclusions to tests, fixtures, dependencies, build artifacts, and genuinely generated code with an explicit documented path list. Do not exclude authored logic, workers, editor integration, or difficult error paths to reach the target.
- Schema migrations also need migration/upgrade checks; their measurement treatment must be explicit and documented during E01.
- Backend unit/integration coverage may be combined for the same source revision. Instrument and combine subprocess/worker execution when it contributes to the measured suite.
- Configure Python branch collection and separately evaluate line/branch counts from its machine-readable report; one combined `fail_under` percentage alone does not enforce both metrics.
- Configure Vitest to include the whole application source set and enforce line/branch thresholds. Verify the gate uses the agreed unrounded counts.
- Missing, empty, invalid, stale, or incompletely combined reports fail CI. Failing tests remain failures even if coverage exceeds 90%.
- The gate starts with the first scaffolded application code. Do not use temporary reduced thresholds, `continue-on-error`, blanket ignore pragmas, or a placeholder passing job.

Coverage supports the behavioral checks in the epics. Browser tests for editing, quotas, template copies, and history restoration remain required even if the numeric thresholds pass.

References: [coverage.py configuration](https://coverage.readthedocs.io/en/latest/config.html), [Vitest coverage configuration](https://vitest.dev/config/coverage.html).

## GitHub Actions CI contract

Implemented workflow: `.github/workflows/ci.yml`. Tests and coverage use the same containerized commands locally and on Actions runners.

1. Run on pull requests and pushes to `main`; add merge-queue events if a merge queue is enabled later.
2. Check out the exact source revision and install/build from pinned dependencies and images.
3. Validate Compose, lint/type-check application code, validate migrations/contracts and Ukrainian/English catalogs, run backend and frontend tests with coverage, and run the required Playwright flows against the Docker stack.
4. Produce separate backend/frontend coverage reports and test summaries as Actions artifacts for diagnosis, including on failed runs where reports exist.
5. Evaluate the coverage gates and produce a stable required check, proposed name `ci-required`, that succeeds only when every required job succeeded. Its aggregation must explicitly fail on missing, skipped, or cancelled prerequisites; a green summary must never mask a failed test job.
6. During E01, once the workflow exists and its check name is established, configure branch rules in `Flippylolz/fillable` to require PRs and `ci-required` for merges to `main`, with up-to-date checks or a verified merge-queue equivalent. Establish this before the first application PR merges. Workflow YAML alone does not enable merge protection. Record the actual configured check name and evidence; the repository already exists.

Keep required workflow scheduling reliable: do not skip the whole required check with path filters. Keep deployment credentials unavailable to untrusted pull-request jobs. Test reports must use synthetic fixtures and must not expose production documents or secrets.

Localization is required under D021 and [Localization](I18N.md). E01 includes catalog validation and checks against hardcoded application copy in required CI: logical message-key parity, nonempty translations, interpolation-parameter parity, and valid language-specific plurals. Keep any nontranslatable literals explicitly documented and narrowly allowed; user data is not catalog copy. Missing English translations fail even if runtime Ukrainian fallback displays text. As pages arrive, required browser coverage includes both languages, profile preference persistence/failure, and preservation of drafts and document content when switching. These checks supplement the independent 90% coverage gates; they are not implemented at this planning stage.

Arm auto-merge on each ready task PR only after verifying these actual gates. Failing, skipped, cancelled, or missing required jobs must prevent auto-merge. Never use an administrator override, lower thresholds, or make checks optional to complete a task. Ordinary task merges must not trigger deployment ahead of E08.

Verify the gate with a controlled negative check: temporarily provide below-threshold coverage or introduce an uncovered branch in an isolated verification change, observe failure, then remove that change. Also verify missing-report and exactly-90% boundaries. Do not leave intentionally failing application code in the repository.

References: [GitHub Actions job dependencies](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs), [required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## E08 deployment workflow

Implemented E08.2 workflow: `.github/workflows/deploy.yml`; rollout remains pending E08.3–E08.5. See [release artifacts](RELEASE_ARTIFACTS.md) for the exact gate and transport contract. Since E09.6 the user requested automatic deployment on merges to the protected default branch: `.github/workflows/deploy-main.yml` waits for that exact commit's successful required CI and then dispatches the unchanged `workflow_dispatch` release, which still verifies the dispatched current-main revision and its green `ci-required` before building and shipping. Manual `workflow_dispatch` remains available; a commit whose required CI fails or is missing is never deployed, and a newer merge always supersedes an older queued release.

Before rollout, complete the shared-server preflight in [Deployment target](DEPLOYMENT_TARGET.md). The Actions deployment must use the supplied SSH target, isolated Fillable resources, the verified Fillable-owned TCP relay port 3200, a private app upstream, and the existing owner-managed TLS listener. The public origin is `https://<DEPLOY_HOST>:3200` under D024. Local and production are the only persistent environments; no staging environment or backup system is required.

1. Select one exact commit and run/reuse the mandatory CI contract for that commit. A manual trigger cannot bypass tests or the 90% gates.
2. Build production images from that verified revision and identify the delivered images by immutable digest/commit metadata. Pass the full source commit through Docker into the frontend build for the [Version badge](VERSION_BADGE.md); use the checked-out release revision, including for manual selection, and ensure build caching respects it. Deploy those artifacts; do not pull an unrelated `latest` image or rebuild arbitrary source on the server.
3. Serialize deployments for the target environment and coordinate nginx changes with its shared configuration manager. Keep dedicated transport credentials in GitHub environment secrets and runtime application secrets on the server; initial account credentials stay with the private operator and are never uploaded to GitHub; do not embed them in images or commit them. Preserve SSH host-key verification.
4. Validate target capacity, configured persistent paths, runtime configuration, and the tested migration/compatibility plan before changing the running release. D018 explicitly excludes backups; do not create or require one for deployment. Use non-destructive migration steps and preserve existing data/volumes.
5. Quiesce only Fillable's incompatible writes/workers when necessary, apply reviewed migrations once, then update only its namespaced Compose services while preserving document/database/Redis volumes and all other workloads.
6. Check the private app upstream and the already configured shared TLS listener with normal certificate/hostname verification, then start only Fillable’s relay. Do not edit or reload shared nginx; coordinate with its owner before any ingress change. Perform an authenticated synthetic smoke flow at the exact public URL covering login cookies, upload, editing/save/download, and version history, then recheck existing service/route baselines. A running container alone is not deployment success.
7. Verify the served version badge matches the deployed artifact's first seven source-commit characters; a controlled release showing `development` or another revision fails the smoke check. Record commit, artifact digests, migration result, selected port, nginx configuration owner/diff, health/smoke checks including existing services, and release outcome in the workflow output.
8. On failure, stop and report it. Use the previous images only when compatible with the database schema; otherwise retain the data and apply a tested forward repair. Do not assume that switching an image reverses a migration, promise backup restoration, or delete persistent volumes as rollback. Data lost from the only production copy cannot be recovered by this workflow.

Image transport and runner connectivity will be chosen for the supplied server during E08. This must not introduce S3 or an external document store; user files and persistent application data stay on that server.

Rollback must also be scoped to Fillable's nginx change and resources. Never roll back a whole shared-config repository/tree over other edits, restart the Docker daemon, or stop unrelated applications.

## Inputs deferred until the final epic

- Verify access to the supplied `<DEPLOY_USER>@<DEPLOY_HOST>`, operating system, architecture, existing Docker setup, resource use, and disk capacity.
- Discover occupied/reserved ports, select the new application port, and identify shared nginx's topology and configuration owner, including the possible WEF repository.
- Deployment directory, document-storage path, exact relay port 3200 for the supplied HTTPS origin, and private gateway reachability. A new domain, certificate, and backup destination are not required inputs.
- Environment/secret configuration in the known GitHub repository `Flippylolz/fillable`, runner-to-server connectivity, and deployment identity.
- Image delivery mechanism and the final deployment trigger preference.

The server address/user are already supplied and should not be requested again. E08.1 records verified access, topology and resource baselines in the deployment-target runbook; later E08 tasks deliver and verify the rollout.

## E01.1 gate implementation (2026-09-06)

`.github/workflows/ci.yml` now runs Docker-based backend lint/tests, frontend
catalog validation/type checking/build/tests, and independent raw line/branch
coverage checks. Reports are collected as artifacts; collection tolerates a
missing container only for diagnostics, while test and gate steps fail closed.
`ci-required` uses `always()` and explicitly accepts only a successful `checks`
job. No path filters or deployment trigger are present.

Source measurement is `backend/app/**/*.py` and `frontend/src/**/*.{ts,tsx}`,
including unimported modules and the React entry point. There are no authored
application exclusions. Tests, fixture data, build/configuration/check tooling,
JSON catalogs, and dependencies are outside these application roots. Check tooling
has controlled boundary/negative tests. Migrations do not exist yet; E01.3 must
explicitly add their coverage and upgrade checks when introduced.

The actual GitHub `main` protection API was configured and reread: PRs required,
strict/up-to-date `ci-required` bound to GitHub Actions app 15368, administrator
enforcement enabled, zero mandatory human approvals, linear history, no force
pushes or branch deletion. Repository auto-merge remains enabled. This protection
was established before the first code PR; E01.7 will audit the completed foundation.

E01.5 expands the initial copy checker beyond JSX text/accessibility literals,
adds full lint/browser checks and localization negative fixtures; the present
catalog checker already checks logical keys, nonempty strings, interpolation,
and locale plural categories. No product pages or profile persistence exist yet.

## E01.3 migration and worker measurement

All authored Alembic Python files live under `backend/app/migrations` and are
included in the application source gate. Tests execute online upgrade, repeat
upgrade, baseline downgrade/re-upgrade, and offline SQL generation. The initial
migration establishes Alembic's version table only; domain tables arrive in E02.
The Mako scaffold is configuration tooling, not an excluded application migration.
The RQ config module is also measured; real Redis tests enqueue a JSON-serialized
synthetic job and run the same RQ CLI/config as production in burst mode. No
application job code is hidden in an uninstrumented subprocess; future authored
jobs must contribute worker execution coverage when necessary.

Always use `-p fillable-checks` for the disposable test stack, independently of
`.env`'s runtime `COMPOSE_PROJECT_NAME`. Production-image CI uses `-p fillable-ci`.
Neither namespace contains production user data. Tests use temporary PostgreSQL
storage; runtime PostgreSQL/Redis use named persistent volumes.

## E01.5 complete foundation check commands

Required Docker checks now include Ruff, mypy, TypeScript/ESLint, catalog and AST
copy validation with negative cases, application unit/integration coverage, generated
contract drift and Playwright production-image smoke flows. The browser runner is a
separate non-root, digest-pinned Playwright 1.63.0 image with matching npm package;
it is not a production service. Desktop/mobile tests exercise real same-origin
health/readiness and recovery after a browser network failure. Test screenshots and
failure traces join coverage artifacts. Browser errors fail the required job.

Copy checks reject JSX text and literal expressions, referenced string constants,
conditional literal branches, accessible/title/placeholder attributes, static page
titles and browser dialog strings. Catalog tests reject missing/empty translations,
interpolation mismatches/malformed braces and invalid/incomplete locale plurals.
Original user data remains renderable. Profile switching and full four-page browser
flows are added when those features exist; this foundation does not claim them.

## E01.7 gate audit

The repository protection API confirms PR-only merging with strict, up-to-date
`ci-required` bound to GitHub Actions app 15368 and administrator enforcement.
PR #6's initial failing check also failed the aggregator and blocked its merge;
its corrected run subsequently merged through the required check.

`scripts/require-ci-success.sh` is the actual aggregator entry point. Its contract
tests reject absent, empty, failed, skipped, cancelled and unknown results. The
coverage contract tests exercise each language's raw line/branch boundary separately,
missing/invalid reports and eligible source absent from reports. Exactly 90% passes.
Every required CI run also adds an unimported file in each disposable test container,
runs the real suite, verifies all application tests passed but coverage rejected the
file, then removes it. Probe reports cannot overwrite the normal report containers.

The downloaded artifact from Actions run 34022095669 was inspected: backend JSON,
frontend detailed/summary JSON and both browser screenshots are present. Raw results
were backend 99/99 lines and 6/6 branches, frontend 35/35 lines and 19/19 branches.
The negative probes produced backend 99/161 lines, frontend 35/66 lines and 19/79
branches, correctly failing. Run them locally after building the test images:

```sh
docker compose -p fillable-checks -f compose.test.yaml run --rm backend-test python /checks/test_gate_contract.py
docker compose -p fillable-checks -f compose.test.yaml run --rm backend-test python /checks/probe_backend_coverage.py
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps frontend-test node scripts/probe-coverage.mjs
```

Checkout and artifact upload use immutable upstream v7.0.1 pins and their Node 24
runtime. No required job is optional and diagnostic collection is the only place
where a missing container is tolerated. No deployment workflow exists before E08.

E02.1 auth browser checks use the explicit private origin `http://gateway:8080`
through the whole CI job, so dependency recreation cannot silently switch the API
back to the local example origin. Isolated test databases receive a synthetic
account through the real private-stdin operator CLI; normal app startup and the
future deployment workflow must never provision that fixture. Required browser
checks cover failed/successful login, cookie rotation, restored account locale,
refresh, origin rejection and logout on desktop/mobile. Fresh-checkout production
screenshots/traces and HTML reports are retained alongside editor QA artifacts.

E07.4 adds mandatory `upgrade-checks` for the [previous-image upgrade and full-stack
crash proof](APPLICATION_RECOVERY.md). The `ci-required` aggregator requires both
`checks` and `upgrade-checks` to succeed; each job keeps a 20-minute timeout. The
upgrade job fetches the pinned baseline history and publishes synthetic recovery
evidence. The independent backend/frontend raw 90% gates remain in `checks`.

E07.5's fresh verifier captures a single staged tree and runs an immutable driver.
Its runtime evidence checks effective CPU/memory/logging settings, users, mounts,
loopback publications and absence of OOM/container restarts before and after flows.
The sanitized reports and point-in-time Docker samples are included in the existing
browser artifacts; no container environment or shared-daemon configuration is logged.


## E07.6 coverage provenance and final gate audit

The Docker test commands now capture SHA-256 fingerprints of every eligible source
file before running pytest or Vitest, verify the same bytes afterward, and record
`coverage/provenance.json` only after the test command succeeds. Old reports and
stamps are removed before execution. Python checks both languages' manifests against
current source bytes and the exact report bytes before checking inclusion and raw
independent line/branch counts. Missing stamps, wrong scopes/versions, changed source,
changed report bytes, symlinks and empty application roots fail closed. File paths
are relative, so copying a report from its container does not weaken verification.

Application measurement remains all `backend/app/**/*.py` (including workers,
maintenance and authored Alembic migrations) and `frontend/src/**/*.{ts,tsx}`. There
are no added exclusions. Python has branch measurement and empty `exclude_lines`;
Vitest includes unimported source and requires both 90% metrics. Test, fixture,
build/configuration and verification tooling remains outside application roots;
controlled tooling contract tests and actual uncovered-file probes exercise the gate.
This provenance binds application/report bytes; the required workflow supplies the
trusted execution, pinned dependencies and exact checked-out revision. A digest is
not an attestation against malicious rewriting of the producer and its manifest.

`checks` builds fresh test containers, runs suites through their producer wrappers,
and checks backend counts there. It copies both normal report directories (including
manifests) into the coverage artifact and independently checks frontend counts
against the checkout. Separate disposable negative-probe containers cannot overwrite
normal reports. The backend probe binds its real report before expecting a below-90
error. The frontend probe requires all tests to pass and Vitest to reject actual
below-90 line and branch counts with an included unimported file. It also runs the
real producer wrapper and verifies an old stamp is removed on coverage failure.

Required contract tests also reproduce a real stale coverage.py report, failed-run
stamp invalidation, source mutation during execution, tampering, missing reports,
exactly-90 boundaries and source-set mismatches. `ci-required` requires successful
`checks` AND `upgrade-checks`; all 36 success/non-success result combinations are
checked. Neither missing diagnostic artifacts nor a high coverage score can make a
failed test job pass. Actual `main` protection was reread during this task: strict
up-to-date `ci-required`, GitHub Actions app 15368, administrator enforcement.

No deployment workflow exists at this audit: there is no pipeline route from a
failing coverage result to a rollout. E08 must introduce only a path bound to an
exact successful required-CI revision and immutable artifacts, then verify its
rejection behavior before production use. Current measured counts and final PR/CI
evidence are recorded in [Epics](EPICS.md), without claiming deployment complete.


E08.3 adds mandatory receiver/runtime contracts and actual server Compose authority
checks to the existing checks job. The [server runtime](SERVER_RUNTIME.md) consumes
only verified artifacts through a fixed installed configuration. Application coverage
roots, independent raw 90% gates and the three required CI job identities are unchanged.

The full sequential `checks` job has a 30-minute timeout. Run 34194979359 hit its
former 20-minute limit during the final negative frontend coverage probe after
both browser suites, rendering, and application tests passed. Keep all positive
and negative coverage checks mandatory; cancellation still fails `ci-required`.

E08.7 public Actions readiness deliberately leaves authenticated acceptance pending.
The operator privately provisions the requested account and runs authenticated smoke
and E08.5 browser/persistence checks. A successful workflow alone does not close E08.
See [Server runtime](SERVER_RUNTIME.md) for private inputs and required evidence.

## E09.6 automated main deployment

The user requested deployment on every merge to `main`. `.github/workflows/deploy-main.yml`
runs only for pushes to the protected default branch, polls the exact pushed commit's
`ci.yml` run until it completes, fails without dispatching anything if `ci-required` did
not succeed, and otherwise dispatches `deploy.yml` with that source SHA. The release
workflow and its `release_gate.py` contract are unchanged: they still require a
`workflow_dispatch` of the current protected `main` revision whose latest exact-main CI
attempt has every required job successful. A newer merge therefore supersedes an older
queued release because the older SHA stops being current main, and a failed-CI commit is
never shipped. `scripts/test_deploy_dispatch_contract.py` (required in the `checks` job)
pins the contract: the gated release stays manual-dispatch-only, the dispatcher only
targets pushes to `main`, must await a successful exact-main CI before dispatching, and
cannot invoke build/ship/verify scripts directly. The production environment allows only
`main` and has no required reviewers, so dispatched releases proceed without manual
approval.
