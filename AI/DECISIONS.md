# Decisions

Recorded: 2026-09-06. Status distinguishes agreed direction from implementation choices and unresolved questions.

## D001 — Editable document and synchronized field sidebar

Status: **Accepted — explicit user requirement.**

Embed an editable DOCX canvas. Extract or suggest fields in a sidebar. Edits in either view update the other, and field selection navigates between them. A read-only preview with an external form does not satisfy this requirement.

Consequence: choose and test an editor with document-field APIs before implementing the full editing experience.

## D002 — Python backend and React frontend

Status: **Accepted — revised stack agreed by the user.**

- Frontend: React, TypeScript, Vite, Tailwind, and shadcn/ui.
- Backend: Python, FastAPI, Pydantic, SQLAlchemy, and Alembic.
- Database: PostgreSQL.
- Jobs: Python RQ workers and Redis.
- Tests: pytest, Vitest, and Playwright.
- Reverse proxy and static asset serving: nginx gateway; production uses the server's existing shared nginx for HTTP ingress on a new public port (D015/D019 supersede the earlier Caddy/TLS assumptions).

Application APIs, persistence, quotas, and background business logic run in Python. Node is used for frontend build, development, and browser-test tooling. The production application has no Node backend service.

Exact supported runtime and dependency versions will be checked, pinned, and recorded during E01. Lockfiles must be committed.

References: [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/), [Alembic](https://alembic.sqlalchemy.org/en/latest/), [RQ](https://python-rq.org/), [Vite](https://vite.dev/guide/).

## D003 — Local server storage

Status: **Accepted — explicit user requirement.**

Store document binaries on the server filesystem under a configurable storage root. Store metadata in the local PostgreSQL service. Persist database and queue data on server volumes. Access files through authenticated application routes.

S3 and S3-compatible services are excluded. Do not introduce MinIO as a substitute for the requested filesystem storage.

Consequences: API and worker containers share the storage mount. D018 excludes backups from MVP; persistent volumes and document version history remain required. Initial deployment is one server; multi-server storage is a future decision.

## D004 — Configurable storage allowances

Status: **Accepted — explicit user requirement.**

Provide a default per-user allowance and administrator-controlled individual overrides. Enforce quotas for uploads, saved versions, and retained generated files. Show users their current usage and limit.

For the four-page MVP in D011, operators configure quotas through containerized maintenance commands. A dedicated administrator UI is deferred.

[Storage quotas](STORAGE_QUOTAS.md) defines the initial accounting and concurrency design. A numeric default is an operator setting, not a hardcoded product limit.

## D005 — Docker for development and deployment

Status: **Accepted — explicit user requirement.**

Docker Compose is the standard local development environment as well as the server deployment mechanism. Frontend development, backend execution, workers, databases, migrations, and tests run in containers. Host Node, Python, PostgreSQL, and Redis are not prerequisites.

Use a shared base Compose definition and explicit development and production overrides. Preserve application data across ordinary rebuilds and shutdowns.

Production deployment itself is the final task and is orchestrated through GitHub Actions on the user's supplied server, as recorded in D013. Local production-image/configuration checks can be prepared earlier.

Reference: [Docker Compose](https://docs.docker.com/compose/).

## D006 — Project knowledge in AI/

Status: **Accepted — explicit user requirement.**

Keep requirements, architecture, epics, decisions, agent rules, and handoff notes inside `AI/`. The root README and AGENTS.md are short discovery links.

## D007 — Field identity and detection

Status: **Proposed implementation approach.**

Use tagged Word content controls as durable field occurrences when the selected editor supports reliable import, mutation, and export. A logical application field can map to several occurrences. Plain string replacement and screen coordinates are not durable field identities.

Discover existing controls deterministically. Use rules for explicit placeholders and likely blanks, with user review and manual field creation for missed locations. AI and LLM inference are outside MVP under D009.

E00 must verify this approach, including undo/redo and exported DOCX reopening, against a free solution or a project-owned implementation. No editor integration has been tested in this repository.

Reference: [Word content controls](https://learn.microsoft.com/en-us/office/client-developer/word/content-controls-in-word).

## D008 — Embedded editor

Status: **Free-only constraint accepted; implementation choice open.**

The user permits only solutions with no required license/subscription fees for MVP development and production. Trials and paid-required integration APIs do not qualify. Building the necessary integration or a scoped editor ourselves is allowed if no suitable free solution exists. Prefer permissively licensed components; the project's own license is still undecided and a public repository alone does not settle it.

The previous paid SuperDoc/ONLYOFFICE Developer proposal is superseded. E00 evaluates demonstrably free end-to-end options, including import/export and the actual sidebar APIs, then a project-owned implementation using open components if needed. Do not infer that an open-source editor makes every associated DOCX component free or unrestricted. Record version-specific terms and required runtime services before adoption.

Full editing, synchronized fields, and downloadable DOCX remain required. A custom implementation needs a tested support matrix and preservation of untouched document parts; a preview-only viewer or lossy text-to-DOCX conversion does not meet D001. See [Editor feasibility](EDITOR_FEASIBILITY.md) for research and proof requirements. No editor has been selected or implemented.

## D009 — LLM provider and document-data processing

Status: **AI excluded from MVP — explicit user decision.**

MVP detection uses existing Word controls, rule-based placeholders/blanks, user review, and manual field creation. Do not implement local or external model calls, provider adapters, API-key settings, AI toggles, or AI usage UI for MVP. There is no AI-provider or document-data permission blocker for MVP.

Possible later work: evaluate Groq and show users the available free allowance and usage. This is a future direction, not a provider commitment or a claim about current limits. Verify its then-current plans, model limits, data handling, and usage reporting before defining that feature.

## D010 — Initial application scope and technical defaults

Status: **Proposed implementation defaults.**

- Single-server deployment and one active editing session per document.
- Local accounts with user and administrator roles; no external identity provider dependency for v1.
- Account provisioning and quota administration use containerized operator commands for MVP. Public signup and administrator screens are deferred by D011.
- PostgreSQL-backed server sessions, HttpOnly host-only cookies with SameSite protection, and CSRF/exact-origin checks for browser mutations. D019 specifies the explicit HTTP cookie configuration and its transport limitation.
- Saved DOCX versions are immutable; the current version points to a complete file-and-field snapshot.
- Version-history UI remains in MVP under D011, inside the document workspace. Restoration creates a new revision.
- Stored previews and retained outputs count toward usage; temporary processing files have separate bounded capacity.
- DOCX export is required; PDF export and real-time collaboration are deferred.

Agents may resolve routine details within these defaults and document the result. Changes to accepted decisions must follow the user's instructions rather than silently replacing the agreed architecture.

## D011 — Four-page MVP with version history

Status: **Accepted — explicit user scope and follow-up, recorded 2026-09-06.**

The MVP consists of:

1. Login.
2. A document library with upload, templates, processed documents, and download links.
3. A simple profile.
4. A document workspace with rendering, editing, settings, and a synchronized field sidebar.

The user explicitly retained **version-history UI** in MVP. Place it in the workspace rather than creating another top-level page. The initial design includes revision listing, read-only preview, download, and restoration as a new revision; advanced diffs and branching are deferred.

[Product](PRODUCT.md) is the canonical page specification. Standalone administrator screens and a trash browser are deferred. Necessary backend authorization, quota configuration, persistence, history, and cleanup remain in scope. Keep settings and review controls within the four pages.

## D012 — Templates and individual documents

Status: **Template/result distinction accepted; detailed behavior is a proposed MVP default.**

Use private, owner-managed templates as reusable saved DOCX sources with field definitions. Use template creates an independent document from one saved template revision; direct uploads may also create one-off documents. The same workspace and history UI support either resource type with a clear template/document label.

Changes to, restoration of, or deletion of a template must not change or remove documents already created from it. Copies and restored revisions consume quota through the same storage service. A shared template catalogue, bulk generation, and publishing workflow are deferred.

## D013 — GitHub Actions deployment is the final task

Status: **Accepted — explicit user requirement, recorded 2026-09-06.**

Deploy through GitHub Actions to the supplied target `<DEPLOY_USER>@<DEPLOY_HOST>`. E08 is the final implementation epic, after all earlier epics and their acceptance checks pass. The target is recorded; access and server configuration are not yet verified. Earlier development does not depend on live-server access.

Docker Compose remains the server runtime. CI and local production-build validation begin in E01; live-server setup and the deployment workflow belong to E08. The deployment trigger and connectivity details remain implementation decisions for the supplied environment. The proposed first trigger is a manual workflow dispatch for a verified default-branch commit.

## D014 — Minimum 90% coverage blocks CI

Status: **90% minimum and blocking CI accepted — explicit user requirement. Metric details below are implementation defaults.**

Require at least 90% coverage from the first application scaffold. Apply the threshold independently to backend and frontend and to line and branch coverage; do not average them together. Measure the complete eligible source set and fail on missing reports or failing tests.

GitHub Actions must fail below the threshold, the CI check must be required for merging once its workflow/check is established during E01 in the repository recorded in D016, and deployment must depend on passing CI for the same source revision. Agents must not weaken thresholds or expand exclusions merely to make a check pass.

[CI and deployment](CI_CD.md) defines measurement, exclusions, merge blocking, and deployment sequencing. These are recorded requirements; CI and repository rules are not configured yet.

## D015 — Shared server, new port, existing nginx

Status: **Accepted — explicit user deployment constraints, recorded 2026-09-06.**

Deploy using `ssh <DEPLOY_USER>@<DEPLOY_HOST>`. Preserve the other services running there, select a new unused application port, and integrate with the existing shared nginx. The user indicated nginx may be managed in a repository named WEF; this is a discovery lead, not a verified fact.

This supersedes D002's original Caddy choice. Use a project-owned nginx gateway locally and behind the existing production ingress. D019 specifies a new shared-nginx public HTTP listener; existing public listeners and TLS configuration remain untouched. Keep production upstream access private according to the actual host/container network topology.

During E08, inspect services, port allocations, and the nginx configuration owner before making changes. If WEF manages the configuration, use its source and established apply process. Validate effective nginx configuration, reload gracefully, and verify existing services before and after. Changes and rollback must be scoped to Fillable.

[Deployment target](DEPLOYMENT_TARGET.md) records the host and detailed constraints. D019 fixes the public origin's hostname and HTTP scheme; the numeric port, WEF location/ownership, deployment paths, and access remain to be verified. Supplying the host does not change deployment's position as the final task.

## D016 — GitHub repository

Status: **Accepted — repository supplied by the user, recorded 2026-09-06.**

Use [Flippylolz/fillable](https://github.com/Flippylolz/fillable). Local `origin` is `https://github.com/Flippylolz/fillable.git`. GitHub metadata and remote refs were checked: visibility is public, default branch is `main`, and no remote refs existed at inspection.

The original remote connection did not publish task files. P00 subsequently established empty base commit `3820bff` so the planning documents can arrive through their own PR. E01 will implement CI and required-check configuration; classic protection and rulesets were inspected and absent before P00. Do not create a duplicate repository or move deployment ahead of E08.

## D017 — One task per PR and auto-merge

Status: **Accepted — explicit user requirement; repository auto-merge enabled on 2026-09-06.**

Each individual task (for example, E02.3) gets its own branch and PR, including necessary tests and documentation. Do not bundle entire epics or unrelated tasks into one PR, and do not push task implementation directly to `main`.

The repository setting `allow_auto_merge` was changed from false to true and verified through GitHub's API. Existing merge methods and unrelated repository settings were preserved. Auto-merge still needs to be enabled on each ready PR; squash is the default task workflow, subject to repository policy.

E01 must establish PR-only merging and the mandatory `ci-required`/90% coverage gate before the first application PR merges. Auto-merge must honor all actual required checks and any configured review rules. The user authorizes the routine task PR/auto-merge workflow; a task is delivered only after its PR is verified merged.

[PR workflow](PR_WORKFLOW.md) defines the operational process. No PR or CI gate was created by enabling this setting. Deployment remains E08 and is not triggered merely by merging ordinary tasks.

## D018 — Local and production environments; no MVP backups

Status: **Accepted — explicit user decision.**

Maintain local development and one production environment, with isolated data/configuration. CI uses disposable test environments; there is no persistent staging environment. Do not implement backup jobs, destinations, snapshots, replication, or backup/restore drills, and do not require a backup before MVP deployment.

Persistent volumes, safe writes, crash reconciliation, restart/upgrade checks, and the requested document version-history UI remain in scope. Versions on the same server are not backups and cannot recover a lost disk/database. Deployment rollback may reuse compatible images and revert the scoped nginx change; it must not promise data recovery without backups. Test non-destructive migrations and preserve existing volumes.

## D019 — Public HTTP address on a new port

Status: **Accepted — explicit user address, numeric port pending inspection.**

The production origin is `http://<DEPLOY_HOST>:<PORT>`. Keep the existing shared-nginx requirement: nginx listens on the newly allocated public port and proxies to Fillable's private gateway. Distinguish `FILLABLE_PUBLIC_PORT` from the gateway's `FILLABLE_UPSTREAM_PORT` when a host binding is needed. Neither port is selected yet. Existing ports 80/443, routes, and TLS services remain owned by their current applications.

Configure the exact origin, including the port, in `APP_PUBLIC_URL`. For this explicit HTTP deployment, the application session cookie cannot use `Secure`; use a Fillable-specific cookie name, HttpOnly, SameSite, CSRF tokens, and exact allowed-origin checks. Cookies are not isolated by port, so do not rely on a new port as session isolation from other applications on this hostname. Use `Secure` when an HTTPS origin is configured later; never downgrade it by inferring arbitrary forwarded headers.

HTTP does not encrypt credentials, cookies, or documents in transit. Record that limitation without introducing an HTTPS purchase or approval prerequisite. No certificate or new domain is needed for the accepted MVP route. See [Deployment target](DEPLOYMENT_TARGET.md).

Reference: [Browser cookie attributes and port behavior](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie).
