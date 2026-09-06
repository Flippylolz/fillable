# CI, coverage, and final deployment

Status: implementation contract. The user created [Flippylolz/fillable](https://github.com/Flippylolz/fillable), and local `origin` is configured. The repository was verified public and empty on 2026-09-06, with default branch `main`. No Actions workflow, application coverage configuration, push, or deployment has been performed in this task; repository protection is unverified.

Repository auto-merge was enabled on 2026-09-06. Each task is delivered through its own PR under [PR workflow](PR_WORKFLOW.md). Auto-merge availability is configured; coverage enforcement and required branch checks are still E01 work.

## Order of delivery

- E01 establishes Docker-based development and GitHub Actions CI with the coverage gate as soon as application code is scaffolded.
- E02–E06 deliver the MVP while keeping CI green.
- E07 verifies the complete MVP, coverage gate, and operations in local/CI Docker environments.
- **E08 is the final task: deployment through GitHub Actions to `<DEPLOY_USER>@<DEPLOY_HOST>`.** It requires all earlier epics to pass and server access, port allocation, and shared nginx integration to be verified.

Preparing and testing production images/Compose locally is foundation work. Connecting to the live server, configuring its deployment, and running the deployment workflow belong to E08. The target is now supplied; it has not been inspected or changed. See [Deployment target](DEPLOYMENT_TARGET.md), including the requirement to preserve existing services and investigate WEF as a possible nginx owner.

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

Planned workflow: `.github/workflows/ci.yml`. Tests and coverage use the same containerized commands locally and on Actions runners.

1. Run on pull requests and pushes to `main`; add merge-queue events if a merge queue is enabled later.
2. Check out the exact source revision and install/build from pinned dependencies and images.
3. Validate Compose, lint/type-check application code, validate migrations/contracts, run backend and frontend tests with coverage, and run the required Playwright flows against the Docker stack.
4. Produce separate backend/frontend coverage reports and test summaries as Actions artifacts for diagnosis, including on failed runs where reports exist.
5. Evaluate the coverage gates and produce a stable required check, proposed name `ci-required`, that succeeds only when every required job succeeded. Its aggregation must explicitly fail on missing, skipped, or cancelled prerequisites; a green summary must never mask a failed test job.
6. During E01, once the workflow exists and its check name is established, configure branch rules in `Flippylolz/fillable` to require PRs and `ci-required` for merges to `main`, with up-to-date checks or a verified merge-queue equivalent. Establish this before the first application PR merges. Workflow YAML alone does not enable merge protection. Record the actual configured check name and evidence; the repository already exists.

Keep required workflow scheduling reliable: do not skip the whole required check with path filters. Keep deployment credentials unavailable to untrusted pull-request jobs. Test reports must use synthetic fixtures and must not expose production documents or secrets.

Arm auto-merge on each ready task PR only after verifying these actual gates. Failing, skipped, cancelled, or missing required jobs must prevent auto-merge. Never use an administrator override, lower thresholds, or make checks optional to complete a task. Ordinary task merges must not trigger deployment ahead of E08.

Verify the gate with a controlled negative check: temporarily provide below-threshold coverage or introduce an uncovered branch in an isolated verification change, observe failure, then remove that change. Also verify missing-report and exactly-90% boundaries. Do not leave intentionally failing application code in the repository.

References: [GitHub Actions job dependencies](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs), [required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## E08 deployment workflow

Planned workflow: `.github/workflows/deploy.yml`, implemented in the final epic. The initial proposed trigger is manual `workflow_dispatch` for a commit on the protected default branch; automatic deployment on push is not assumed.

Before rollout, complete the shared-server preflight in [Deployment target](DEPLOYMENT_TARGET.md). The Actions deployment must use the supplied SSH target, isolated Fillable resources, a verified unused public HTTP port, a private app upstream, and the existing nginx owner's configuration/apply process. The public origin is `http://<DEPLOY_HOST>:<PORT>`. Local and production are the only persistent environments; no staging environment or backup system is required.

1. Select one exact commit and run/reuse the mandatory CI contract for that commit. A manual trigger cannot bypass tests or the 90% gates.
2. Build production images from that verified revision and identify the delivered images by immutable digest/commit metadata. Deploy those artifacts; do not pull an unrelated `latest` image or rebuild arbitrary source on the server.
3. Serialize deployments for the target environment and coordinate nginx changes with its shared configuration manager. Keep credentials in GitHub environment secrets and runtime application secrets on the server; do not embed them in images or commit them. Preserve SSH host-key verification.
4. Validate target capacity, configured persistent paths, runtime configuration, and the tested migration/compatibility plan before changing the running release. D018 explicitly excludes backups; do not create or require one for deployment. Use non-destructive migration steps and preserve existing data/volumes.
5. Quiesce only Fillable's incompatible writes/workers when necessary, apply reviewed migrations once, then update only its namespaced Compose services while preserving document/database/Redis volumes and all other workloads.
6. Check the private app upstream, stage the new public HTTP listener and focused shared-nginx route through its owner, validate the complete effective configuration, then activate it through the owner's established process. Perform an authenticated synthetic smoke flow at the exact public URL covering login cookies, upload, editing/save/download, and version history, then recheck existing service/route baselines. A running container alone is not deployment success.
7. Record commit, artifact digests, migration result, selected port, nginx configuration owner/diff, health/smoke checks including existing services, and release outcome in the workflow output.
8. On failure, stop and report it. Use the previous images only when compatible with the database schema; otherwise retain the data and apply a tested forward repair. Do not assume that switching an image reverses a migration, promise backup restoration, or delete persistent volumes as rollback. Data lost from the only production copy cannot be recovered by this workflow.

Image transport and runner connectivity will be chosen for the supplied server during E08. This must not introduce S3 or an external document store; user files and persistent application data stay on that server.

Rollback must also be scoped to Fillable's nginx change and resources. Never roll back a whole shared-config repository/tree over other edits, restart the Docker daemon, or stop unrelated applications.

## Inputs deferred until the final epic

- Verify access to the supplied `<DEPLOY_USER>@<DEPLOY_HOST>`, operating system, architecture, existing Docker setup, resource use, and disk capacity.
- Discover occupied/reserved ports, select the new application port, and identify shared nginx's topology and configuration owner, including the possible WEF repository.
- Deployment directory, document-storage path, exact unused public port for the supplied HTTP origin, and private gateway reachability. A new domain, certificate, and backup destination are not required inputs.
- Environment/secret configuration in the known GitHub repository `Flippylolz/fillable`, runner-to-server connectivity, and deployment identity.
- Image delivery mechanism and the final deployment trigger preference.

The server address/user are already supplied and should not be requested again. Remaining unknowns are E08 preflight dependencies; continue preceding epics without live-server changes.
