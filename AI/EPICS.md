# Implementation epics

Status vocabulary: `ready`, `waiting`, `in_progress`, `in_review`, `done`. Waiting means dependencies or a recorded product decision are outstanding. A task awaiting PR merge is `in_review`; an epic remains open until all required tasks and acceptance criteria are delivered. No implementation epic is complete yet.

Scope: the four pages in [Product](PRODUCT.md), including version-history UI inside the workspace. Ukrainian/English UI localization and the saved profile language switcher are MVP requirements under [Localization](I18N.md). Every user-facing task supplies both translations. Epics describe implementation boundaries, not additional product pages. Administrator screens, a trash browser, advanced diffs, and public registration are outside MVP.

Delivery rule: each individual task ID below gets its own branch and PR, with auto-merge enabled when ready and actually protected by required checks. Follow [PR workflow](PR_WORKFLOW.md); record PR URLs and merge commits rather than marking an open PR done.

## Roadmap

Planning task P00: consolidate the accepted MVP decisions, architecture, epics, and agent rules in one documentation PR (`task/p00-mvp-plan`). Acceptance: linked documents agree on free-only editor components, deterministic detection without AI, local/production environments without backups, HTTP on a new shared-nginx port, and the existing four-page/history/coverage/PR requirements. Validate Markdown links and consistency; no application coverage is claimed for this documentation task. A separate empty Git-history bootstrap establishes `main` before opening the PR and contains no task files.

Planning task P01: add the accepted UI localization requirement in one documentation PR (`task/p01-ui-localization`). Acceptance: product, decisions, architecture, epics, CI plan, and agent rules agree on Ukrainian as the default UI language, English as secondary, all application copy in i18n catalogs, and a profile language switcher whose preference persists across sessions. Specify translation completeness checks and preservation of document content when switching UI language. Validate Markdown links and consistency; application implementation and coverage are outside this documentation task.

Planning task P02: record the user's version badge design and behavior in one documentation PR (`task/p02-version-badge`). Acceptance: preserve the supplied CSS, seven-character deployed-commit display, `development` fallback, fixed desktop/mobile placement, theme-independent colors, monospace value, and noninteractive click-through behavior. Link the build/deployment metadata contract and future implementation/verification tasks, keeping labels in i18n. The user explicitly chose specification-only delivery; validate documentation without adding application code or claiming runtime/coverage checks.

Planning task P03: prepare a reusable autonomous implementation prompt in one documentation PR (`task/p03-autonomous-agent-prompt`). Acceptance: direct the next agent to execute the roadmap, maintain one task per PR and required CI/coverage, continue after each merge, preserve accepted product/deployment constraints, and ask the user only for an unavoidable dependency it cannot safely resolve. Continue independent work while awaiting input and stop all work only when no useful authorized progress remains. Include resumption evidence and a concrete completion definition. Creating this prompt does not launch another agent, start implementation, or schedule background work; validate documentation links and consistency.

| Epic | Outcome | Dependencies | Status |
| --- | --- | --- | --- |
| E00 | Free editor feasibility and selection | Zero-fee end-to-end components or project-owned implementation | in_progress: E00.1 baseline; editor proof still pending |
| E01 | Docker foundation and application skeleton | Accepted stack | in_progress: E01.1–E01.5 merged; E01.6 verification underway |
| E02 | Login/profile, accounts, local storage, and quotas | E01 | waiting |
| E03 | Upload, templates, and processed-document library | E02 | waiting |
| E04 | Field discovery and review model | E03; editor mapping work needs E00 | waiting |
| E05 | Workspace editor, settings, and synchronized sidebar | E00, E03, E04 field contract | waiting |
| E06 | Safe saves, version-history UI, restoration, and DOCX export | E02, E05 | waiting |
| E07 | MVP acceptance and CI verification | E03–E06 | waiting |
| E08 | Final deployment through GitHub Actions | All E00–E07 done; supplied target access/nginx/port verified | waiting |

E01 can start without selecting an editor. E04 uses deterministic detection only; there is no AI provider/key decision to wait for. E00 must finish before editor-dependent implementation is considered ready. Local and production are the only persistent environments, and backups are outside MVP under D018.

Page ownership: E02 delivers login/profile; E03 delivers the library; E04–E06 deliver the document workspace. E01 and E07 support all four pages.

CI and the 90% coverage blocker start in E01. **E08 is the final task**; live deployment waits for all earlier acceptance criteria and preflight of the supplied target `<DEPLOY_USER>@<DEPLOY_HOST>`. Production Docker configuration can be built and tested locally before then. [CI and deployment](CI_CD.md) and [Deployment target](DEPLOYMENT_TARGET.md) define the shared nginx, new-port, and service-isolation requirements.

## E00 — Prove the editor integration

Outcome: choose a free editor or prove a project-owned implementation using evidence from our required workflow and document corpus. Read [Editor feasibility](EDITOR_FEASIBILITY.md).

Work:

- E00.1: Build the initial Ukrainian synthetic DOCX baseline with an external answer key: tables, headers/footers, numbered lists, split-run Cyrillic placeholders, repeated names, native controls, long values, Ukrainian characters/apostrophes, and negative cases. Use [Test corpus](TEST_CORPUS.md); keep v1 and add reviewed samples when the user's real document becomes available.
- E00.2: Compare free end-to-end options, field APIs, import/export, license obligations, Python-backend compatibility, Ukrainian/English UI localization hooks, and total deployment needs. Record evidence in D008 and the feasibility notes; paid APIs and expiring trials do not qualify.
- E00.3: Demonstrate field creation, sidebar-to-document updates, document-to-sidebar updates, and focus navigation using a qualifying free solution. If none fits, prototype a project-owned editor/adapter using open components and source-package preservation; do not silently reduce the editing requirement.
- E00.4: Test direct surrounding edits, deletion of controls, undo/redo, repeated occurrences, export, and reopen.
- E00.5: Record the chosen editor, version, support matrix, limitations, and go/no-go evidence in `AI/`. Supersede D008 only after the choice is settled.

Acceptance:

- Both directions of synchronization and a complete DOCX save/reopen path work on the corpus.
- Required formatting is checked visually, including in Word when available. Distinguish editor self-reopening from independent Word compatibility evidence.
- Known unsupported features produce an explicit supported scope; do not adopt a vendor's fidelity claim as a test result.
- Required development/production components carry no required license/subscription fees. Record exact versions and obligations; no paid solution or trial is adopted.
- Exposed editor UI can use Ukrainian and English, including supplied custom translations where needed. Verify locale switching preserves document/editor state; record localization gaps before adopting an editor.
- A custom implementation, if needed, preserves untouched DOCX structures and demonstrates direct edits as well as field edits. Unsupported structures are explicit; a viewer-only or lossy HTML/text conversion does not pass.

## E01 — Docker foundation

Outcome: a fresh checkout runs the app skeleton and checks entirely through Docker.

Work:

- E01.1: Scaffold React/Vite and FastAPI with the planned repository layout and pinned dependencies, including Ukrainian/English catalogs, a shared translation/formatting entry point, and the minimum Docker test/coverage workflow needed to enforce 90% on the first application PR. Establish Ukrainian as default and baseline localization checks with the first UI copy. Later foundation tasks expand this baseline; do not merge application code before its gate exists.
- E01.2: Add base, development, and production Compose files; a project-owned nginx gateway; persistent volumes; source reload; and readiness checks. Production exposes a configurable private upstream for shared nginx, without binding public host ports 80/443.
- E01.3: Add PostgreSQL, Redis, RQ worker bootstrap, and an ordered Alembic migration step.
- E01.4: Define OpenAPI contracts and a reproducible generated TypeScript client, including stable error/status codes and typed parameters for localized presentation. Document generation and check for drift.
- E01.5: Add container commands for linting, type checking, pytest/coverage.py, Vitest coverage, and a Playwright smoke test; wire them into GitHub Actions CI with independent >=90% line/branch gates for backend and frontend. Include required catalog key/interpolation/plural validation and checks against hardcoded application copy.
- E01.6: Verify startup, hot reload, restart persistence, and production asset serving. Replace planned commands in the development guide with verified commands.
- E01.7: Verify the stable required-check aggregator, coverage-report artifacts, and negative gate checks in `Flippylolz/fillable`. Establish PR-only merging and the required CI check before the first application PR merges, then record their evidence in this task's PR; track the external settings explicitly until verified.
- E01.8: Implement the shared [Git version badge](VERSION_BADGE.md) with the supplied CSS, catalog-based messages, seven-character commit/fallback resolution, and Docker frontend build metadata. Verify desktop/mobile, theme independence, monospace value, and click-through behavior. Depends on the E01.1 app/i18n foundation, E01.2 Docker build path, and working required CI; deliver as its own PR. Live-release wiring and verification stay in E08.

Acceptance:

- Git and Docker are sufficient on the host; no host Python, Node, PostgreSQL, or Redis setup is required.
- Browser loads the frontend and reaches an API health/readiness endpoint through the same origin.
- Frontend and backend changes are visible through the development workflow.
- Containers restart without losing persistent state; ordinary shutdown does not remove data.
- CI and local checks use reproducible dependencies and documented commands.
- Ukrainian is the unconfigured UI default; both shipped catalogs cover every application message key. Missing/invalid translations and prohibited hardcoded copy fail required CI, and interface formatting/page language follow the selected locale.
- Below-90% coverage, missing reports, and failing/skipped required jobs fail CI. Exactly 90% passes without rounding up a lower value; no temporary relaxed threshold is allowed.
- Required source coverage includes backend workers/commands and the frontend editor adapter. Gate evidence covers each codebase and metric separately.
- Merge protection is verified on `Flippylolz/fillable` once CI is established; do not describe it as enabled from workflow YAML alone.
- Every foundation task is represented by its own PR. Auto-merge honors the real required gates, and merged PR URLs/commits are recorded before dependent tasks are marked ready.
- The shared version badge matches D022 with known/missing build metadata, remains fixed at the requested safe-area-aware offsets on desktop/mobile, and allows interaction with underlying controls. Its future page integrations preserve this behavior.

## E02 — Login, profile, storage service, and quotas

Outcome: users can sign in, manage a simple profile, and own local files whose retained writes respect their allowance.

Work:

- E02.1: Implement local accounts, server sessions, user/admin authorization, and the login/logout flow. Include a validated user `ui_language` (`uk`/`en`, default `uk`) and read it on authentication. Add containerized account provisioning and credential-reset commands without public default credentials.
- E02.2: Model global quota settings, per-user overrides, storage accounts, reservations, and file lifecycle states.
- E02.3: Implement the shared local storage service with streaming allocation, atomic reservation, idempotency, safe paths, and crash recovery.
- E02.4: Add deletion, temporary-file cleanup, job reconciliation, and disk-capacity checks.
- E02.5: Expose current-user usage and provide privileged containerized commands for default/override quota changes with audit records. Reuse the service layer; no administrator screen is needed.
- E02.6: Build the profile page with account email, editable display name, current-password-verified password change, logout, and read-only storage usage/allowance.
- E02.7: Add the profile language selector (Українська / English), authorized preference update, immediate application after successful save, and restoration across refresh/login/browser sessions. Handle invalid values, failed saves, and stale browser preferences under [Localization](I18N.md). Depends on E02.1 and E02.6; deliver through its own PR.

Acceptance:

- All cases in [Storage quotas](STORAGE_QUOTAS.md) pass meaningful integration checks.
- Concurrent requests cannot over-allocate user capacity or charge a retry twice.
- Lowered limits preserve existing files and block new allocations appropriately.
- API and worker paths share quota enforcement; user-isolation checks cover reads and writes.
- Invalid credentials, successful login, session expiry, and logout behave correctly across protected pages.
- Login works for the explicit HTTP origin in D019 with HttpOnly/SameSite, Secure=false, CSRF, and exact-origin checks including the port. An HTTPS configuration enables Secure. Do not assume cookies are isolated from other apps by port.
- Profile updates persist, password changes require the current credential, and users cannot update their own quota or role.
- New accounts default to Ukrainian. The profile language switcher persists English or Ukrainian across sessions; save failures retain the prior language. A user's saved preference overrides stale browser state and cannot be changed by another user. Language switching preserves active state and document data.
- Account and quota maintenance run through Docker without direct database edits or a separate administration page.

## E03 — Upload, templates, and document library

Outcome: one library page separates reusable templates from individual working/processed documents and provides upload, open, use-template, download, and delete actions.

Work:

- E03.1: Build Templates and Documents tabs, the upload flow with template/document choice, quota meter, and processing/save/error states.
- E03.2: Validate DOCX structure and supported formats with compressed/expanded-size and parser limits.
- E03.3: Preserve originals and persist resource kind, initial saved revision, ownership, and metadata through the storage service.
- E03.4: Add authorized latest-saved downloads, open/edit actions, and deletion with confirmation. Keep file cleanup backend-managed; no trash browser is required.
- E03.5: Submit processing jobs and show durable status through a polling API initially.
- E03.6: Implement Use template as an idempotent, quota-checked copy of one saved template revision and its field schema. Open the new independent document in the workspace.

Acceptance:

- Valid DOCX uploads survive restart and download without modification to the original.
- Invalid, encrypted, over-limit, and unauthorized requests fail clearly without leaked files or reservations.
- One user cannot access another user's documents by guessing IDs or paths.
- Quota usage updates after successful writes and confirmed deletion.
- Templates and processed documents appear in the correct tabs. Direct uploads can create one-off documents without creating templates.
- Use template leaves the source unchanged; subsequent edits, restoration, or deletion of the template do not alter or remove the created document.
- Download links identify the saved file and never return partial output or imply inclusion of unsaved edits.

## E04 — Field discovery and review

Outcome: documents produce useful, correctable field candidates tied to their source version.

Work:

- E04.1: Define field, occurrence, candidate, and review schemas, starting with text.
- E04.2: Extract existing Word controls and explicit placeholders, including text split across runs.
- E04.3: Add rules for likely blank lines and table cells with nearby labels.
- E04.4: Implement deterministic fixtures and labeled expected candidates. Report false positives and misses separately by detector.
- E04.5: Add review actions within the workspace sidebar for labels, types, dismissals, and repeated-field grouping. Connect accepted locations to editor controls once E00 is resolved.

The previously proposed E04.6 inference adapter is removed from MVP under D009. No local/external model, provider interface, AI credentials, or AI usage UI is a prerequisite. Possible Groq/free-allowance work is deferred beyond this roadmap.

Acceptance:

- Existing controls and explicit fixtures produce reproducible results.
- Every inferred candidate has a valid location and supporting context; ambiguous results are reviewable.
- Stale results cannot be applied to a changed document without revalidation.
- Users can reject suggestions without mutating document content.
- Record measured accuracy on the labeled corpus; do not invent a universal accuracy guarantee.
- Accepted template fields are copied with the saved template revision. A derived document need not rerun detection unless the user requests it or its content invalidates the existing mapping.

## E05 — Workspace, editor, settings, and synchronized sidebar

Outcome: the user edits the DOCX and sidebar as one coherent workspace.

Work:

- E05.1: Integrate the selected editor behind a narrow adapter with load/export and field operations. Connect Ukrainian/English localization for its exposed controls without remounting document state on a locale change. Reuse one workspace for templates and individual documents, clearly labeled.
- E05.2: Build sidebar fields with validation, navigation, active-field indication, and review states.
- E05.3: Apply sidebar values through editor transactions and read direct document changes back into the sidebar.
- E05.4: Allow manual field creation from a selection and handle moved/deleted controls explicitly.
- E05.5: Handle repeated occurrences, undo/redo, keyboard navigation, focus, input composition, and event-loop prevention.
- E05.6: Add back navigation, title, save/download/history entry points, and save status. Keep rename, zoom, and field-highlighting settings inside this page.

Acceptance:

- Browser tests demonstrate both directions of value synchronization and navigation.
- Direct text editing remains available throughout the document's supported editable regions.
- Surrounding edits do not redirect fields; missing locations and conflicting repeated values require review.
- Undo/redo does not leave sidebar and document values inconsistent.
- Check long text, Unicode, table fields, and the chosen editor's supported field types.
- Workspace settings and field review fit within the page. Navigation and expired sessions do not silently discard unsaved work.
- Ukrainian and English cover workspace/editor/settings/sidebar controls, errors, and accessible names. Extracted/custom field labels and values remain original data; locale changes preserve draft content, selection, and undo state without triggering document saves or revisions.

## E06 — Safe saves, version-history UI, and DOCX export

Outcome: users can resume work, browse and restore previous versions in the workspace, and download current or historical DOCX files.

Work:

- E06.1: Enforce a single active editing lease with expiry and an explicit stale-session flow.
- E06.2: Implement revision-checked saves with a matching document/field snapshot and idempotent retries.
- E06.3: Build a version-history panel for templates and documents with revision timestamps, current-version marker, read-only preview, historical download, and restore action.
- E06.4: Export/download current and historical DOCX files and verify them by reopening. Route retained outputs and restored copies through quota enforcement.
- E06.5: Implement configurable operator retention before automatic history pruning, communicate it in the history panel, and handle quota/disk/save errors recoverably.
- E06.6: Restore the selected DOCX and matching field schema as a new current revision, preserving later retained revisions and restored-from provenance. Check the base revision and handle unsaved work explicitly.
- E06.7: Add autosave/saved/error status and reopen behavior. Historical preview must never autosave itself into the live current document; coordinate retention with active historical reads and restores.

Acceptance:

- Refresh and reopen restore saved content and fields from the same revision.
- Concurrent or stale saves cannot overwrite newer versions silently.
- A failed save never shows success, loses the previous saved version, or hides the editable draft.
- Versions and retained outputs consume the correct allowance, including failure/retry scenarios.
- Corpus exports preserve tested content, metadata, and supported formatting.
- The history panel lists retained versions of either resource type and opens/downloads the exact selected revision.
- Restore creates a new revision with matching fields and preserves later retained versions. It does not mutate other documents derived from a restored template.
- Unsaved-work handling, stale restore requests, quota failure, and duplicate retries cannot lose the current document or double-charge storage.
- Advanced diffing and branching are not required to finish this epic.

## E07 — MVP acceptance and CI verification

Outcome: the four-page MVP passes its acceptance criteria in local/CI Docker, including the 90% coverage blocker, before any live-server deployment.

Work:

- E07.1: Verify login, library, profile, and workspace navigation and states in Ukrainian and English, including the history panel, localized errors/accessibility text, and long Ukrainian labels. Verify default language, profile preference persistence/failure, and unchanged document data/drafts when switching. Check account/quota operator commands and user-facing storage meters. Confirm the version badge appears once on each page without blocking controls on desktop/mobile or changing its specified colors with theme.
- E07.2: Add content-free job/capacity diagnostics and audit events through logs or operator commands. Do not create a diagnostics dashboard for MVP.
- E07.3: Implement scheduled cleanup/reconciliation with bounded retries and clear failure state.
- E07.4: Verify full-application restart, non-destructive upgrade, and crash reconciliation using synthetic data in local/CI Docker. Check matching PostgreSQL/files state and retained version history. Do not implement backups or a backup/restore drill.
- E07.5: Verify fresh Docker installation, upgrade/migration, representative document flows, isolation, and bounded resource use in local/CI environments.
- E07.6: Audit measured backend/frontend coverage, report inclusion, required job aggregation, and GitHub required-check configuration. Demonstrate a below-threshold result blocks the pipeline and cannot reach a deployment path.

Acceptance:

- An operator changes defaults and overrides through Docker commands and sees enforcement take effect in library/profile usage and actual allocations.
- After restart and tested non-destructive upgrade/reconciliation, documents reopen with matching ownership, versions, and quota usage. This verifies persistence and crash handling, not recovery from disk/data loss.
- The full login → upload template → detect/review → use template → edit/sidebar → save → download → reopen flow passes on the supported corpus; direct document upload also passes.
- History preview, historical download, and restoration pass without altering later retained revisions or the source/derived document relationship.
- Profile changes persist and the UI stays within four main pages.
- Both locales pass the product flows, Ukrainian is the initial default, and the profile language survives refresh and a new login/browser session. Catalog completeness checks block missing translations; localized layout and formatting are verified without changing document text, metadata, field labels/values, or saved bytes.
- Docker development and production instructions match tested commands.
- Known compatibility limits and unresolved issues are recorded without overstating release readiness.
- Backend and frontend each pass >=90% line and branch coverage, with reports and all required CI jobs passing for the release candidate. Merge-blocking repository rules are verified before this epic is done.
- No supplied-server deployment occurs in this epic; record readiness and hand off to E08.

## E08 — Final deployment through GitHub Actions

Outcome: the verified MVP runs on the server supplied by the user, deployed and checked through GitHub Actions. This is the final implementation epic.

Dependencies: E00–E07 complete, access and deployment configuration for the supplied target verified, and required GitHub repository/environment configuration available. The hostname/user are known; remaining preflight inputs do not block earlier epics.

Work:

- E08.1: Inspect `<DEPLOY_USER>@<DEPLOY_HOST>` read-only first: existing services, port allocations, capacity, Docker setup, and nginx ownership/networking. Investigate WEF as the possible configuration repository. Record baselines, select a new unused port and isolated Compose namespace, and prepare scoped paths/access without disrupting other workloads.
- E08.2: Implement the GitHub Actions deployment workflow with serialized runs, an explicit source commit, immutable artifacts, and mandatory CI/coverage dependencies. Inject the verified source commit into the frontend build for the version badge, including manually selected revisions. Default proposal: manual dispatch for a protected default-branch commit.
- E08.3: Configure only Fillable's persistent volumes, private upstream, resource limits, and schema-compatible release rollback procedure. No backups or staging environment are required. Prepare the new public HTTP listener for `http://<DEPLOY_HOST>:<PORT>` in the authoritative nginx configuration, using WEF's process if it is the owner. Preserve local document storage, quotas, and existing workloads.
- E08.4: Run the workflow: validate capacity and persistence configuration, apply tested non-destructive migrations, update Fillable services, check private/public ports, validate effective nginx configuration, and apply the route with the owner's established process. Perform app smoke checks at the exact HTTP URL and recheck existing services/routes; do not require a backup.
- E08.5: Verify save/download, template independence, profile, history restoration, and data persistence on the deployed application. Confirm the served version badge matches the first seven characters of the artifact's source commit; a wrong hash or `development` fails a controlled production-release check. Record release commit, artifact digests, results, and the schema-aware rollback/recovery procedure in `AI/`.

Acceptance:

- Deployment ran through GitHub Actions on the user-provided server after all preceding epics passed.
- Failed tests, coverage below 90%, or missing required checks for that source revision prevent rollout, including manually dispatched runs.
- The running application corresponds to the verified commit/artifacts; user files, database state, and quota configuration persist on the local server.
- Health and synthetic MVP smoke checks pass; secrets and private documents are absent from repository/workflow logs.
- Failed rollout reports failure and preserves persistent data; recovery does not assume database migrations reverse with an image change.
- Actual deployment and operator commands, release evidence, and recovery instructions are documented. Do not mark done based only on workflow creation.
- New nonconflicting public/private port allocations are recorded as applicable, and the app is reachable at the supplied HTTP hostname and selected public port through existing shared nginx. The nginx owner and WEF's role are verified rather than assumed; no competing ingress/TLS manager was installed. No backup destination, certificate, or new domain is a release prerequisite.
- Existing services pass the recorded before/after checks. Proxy validation/reload and rollback preserve unrelated routes, containers, volumes, and concurrent configuration changes.

## Execution record

When work begins, update the relevant status and append a concise record here: date, task ID, branch, PR URL, changes, checks actually run and outcomes, coverage where applicable, remaining blockers, and next actionable task. Record the confirmed merge commit before marking a task done. Never mark an epic done while required acceptance criteria remain unverified.

2026-09-06: planning documents created. No implementation checks or editor evaluation have been run.

2026-09-06: refined the plan to the user's four-page MVP; added reusable template/processed-document semantics and the simple profile. The user explicitly retained version-history UI, now scoped to the workspace with read-only preview, download, and restoration as a new revision. Administrator screens and a trash browser are deferred. Application implementation remains unstarted; editor selection is still open. Next actionable implementation work remains E01 and the nonrestricted portions of E00.

2026-09-06: added D013/D014 and the CI contract. Deployment is now final epic E08 through GitHub Actions, waiting for the user's server after E00–E07 pass. E01 establishes the blocking 90% coverage requirement; E07 verifies the completed MVP and CI gates before deployment. No workflow, coverage run, branch protection, or deployment has been implemented yet.

2026-09-06: recorded the supplied SSH target, requirement to preserve other services, new-port allocation, and shared nginx integration in D015 and the deployment-target runbook. WEF is a possible nginx configuration owner pending inspection. Replaced the Caddy plan with project-owned nginx routing behind existing ingress. Deployment remains E08; no SSH connection, server inspection, port reservation, or server change was performed.

2026-09-06: verified the user-created public GitHub repository `Flippylolz/fillable` has default branch `main` and no refs, then configured it as local `origin`. Updated D016 and the CI prerequisite notes. No commit, push, workflow, repository-protection change, or deployment was performed; application implementation remains unstarted.

2026-09-06: enabled repository-level auto-merge (`allow_auto_merge: true`) through GitHub's API, preserving other merge settings. Added D017 and the one-task-per-PR workflow, including per-PR activation and merged-state verification. No task PR, commit, push, CI gate, or deployment was created in this configuration step; planning files remain local.

2026-09-06: P00 incorporates the user's free-only/editor-build fallback decision, excludes all AI from MVP, records a possible later Groq/free-allowance feature, and removes backups and persistent staging from scope. D019 records the HTTP hostname/port origin and distinguishes shared-nginx public ingress from the private app upstream. Updated feasibility work, persistence/migration checks, cookie configuration, and agent rules. Representative user documents remain useful for E00 acceptance; numeric deployment ports remain unassigned. No editor proof or server access has occurred.

2026-09-06: P00 history bootstrap created and pushed empty base commit `3820bff` on `main`, containing no files, after verifying that the remote had no refs. Planning delivery uses branch `task/p00-mvp-plan`. The documentation check passed for 14 Markdown files and 51 local links, whitespace, and code fences. Application tests/coverage do not exist yet; classic branch protection and rulesets were inspected and absent. No live-server action or application code is part of P00.

2026-09-06: automatic approval review rejected the first P00 branch-push attempt because tracked documents contained the supplied deployment hostname/account. The branch was not published. Moved those values into ignored `AI/DEPLOYMENT.local.md` and replaced public references with placeholders before replacing the unpublished planning commit and retrying. Actual connection values remain available locally for E08.

2026-09-06: P00 submitted as [PR #1](https://github.com/Flippylolz/fillable/pull/1), branch `task/p00-mvp-plan`, status at submission `in_review`. The redacted push succeeded after checks passed for 14 tracked Markdown files, 51 local links, whitespace/fences, and all reachable commits for the excluded deployment identity. This PR is documentation only; application CI/coverage remains E01. Record confirmed merge evidence in this PR's body and carry it into the ledger in the next task PR, per [PR workflow](PR_WORKFLOW.md). Next implementation work: E00 free-editor proof and E01 foundation.

2026-09-06: P00 confirmed `done`, merged through [PR #1](https://github.com/Flippylolz/fillable/pull/1) at `ab3606a634b4d57e2cf7bd15f70e7977871f2a08`. Local main was synchronized before E00.1 began.

2026-09-06: E00.1 generated `client-intake-uk-v1.docx` and its external expected-outcomes JSON on branch `task/e00-1-synthetic-docx`. Incorporated the user's Ukrainian-language priority as D020. The user-selected Legal Memorandum template was adapted to a fictional client intake form. Verified 19 logical fields, 27 stored occurrences (22 explicit and five review candidates), five native controls, six negative cases, Unicode/run structure, ZIP/XML/relationships, and 14 unchanged template parts. Final three-page LibreOffice render inspected completely; Microsoft Word and browser-editor behavior remain untested. See [Test corpus](TEST_CORPUS.md). This fixture/data task adds no application source or coverage claim; E00.2–E00.5 and E01 remain outstanding. PR/merge evidence follows the established task workflow.

2026-09-06: E00.1 submitted as [PR #2](https://github.com/Flippylolz/fillable/pull/2), status at submission `in_review`. Documentation validation passed for 15 public Markdown files and 61 local links. The DOCX hash and all fixture expectations passed structural verification; all three final rendered pages were inspected. Confirmed merge evidence belongs in this PR's body first and is carried into the ledger by the next task PR. No application tests or coverage are claimed for this fixture-only change.

2026-09-06: E00.1 confirmed `done`, merged through [PR #2](https://github.com/Flippylolz/fillable/pull/2) at `e084a9ba3dc8d0c8fc8bcb2dd52fd3b59fdd9454`. Local main was synchronized before P01 began. E00.2–E00.5 editor proof remains outstanding.

2026-09-06: P01 records the user's Ukrainian-default/English-secondary UI requirement as D021 on `task/p01-ui-localization`, with the detailed contract in `AI/I18N.md`. Updated the four-page MVP, user preference/API boundaries, free-editor evaluation, foundation/profile/acceptance tasks, CI plan, and agent rules. All UI copy uses catalogs; the profile preference persists across sessions while document content stays original. Application code, synthetic fixture files, server state, and repository settings are unchanged by this documentation task. Validation and PR evidence follow before delivery.

2026-09-06: P01 submitted as [PR #3](https://github.com/Flippylolz/fillable/pull/3), status at submission `in_review`. Validation passed for 16 public Markdown files, 72 local links, balanced fences, and Git whitespace. Excluded deployment identity is absent from public documentation; the DOCX hash was verified and both synthetic fixture files are unchanged. No application tests/coverage are claimed. Confirmed merge evidence goes in this PR's body first and enters the ledger in the next task PR. Next implementation work remains E00 free-editor proof and E01 foundation, now including the localization contract.

2026-09-06: P01 confirmed `done`, merged through [PR #3](https://github.com/Flippylolz/fillable/pull/3) at `481611877b25809fead3d2840f87c6a18fd74213`. Local main was synchronized before P02 began.

2026-09-06: P02 records the user's version badge design as D022 on `task/p02-version-badge`. The user explicitly chose adding it to the MVP specification while the app remains unscaffolded. `AI/VERSION_BADGE.md` preserves the supplied markup/CSS and adds the source-commit/fallback, i18n, and acceptance contracts. E01.8 implements the badge after foundation work; E07 checks integration across pages; E08 wires and verifies the actual release hash. This documentation task adds no application code, build configuration, runtime test result, coverage measurement, or server change. Validation and PR evidence follow before delivery.

2026-09-06: P02 submitted as [PR #4](https://github.com/Flippylolz/fillable/pull/4), status at submission `in_review`. Checks passed for 17 public Markdown files, 81 local links, balanced fences, Git whitespace, and exact preservation of the user's supplied CSS/markup. Public docs exclude the local deployment identity; synthetic fixtures are unchanged. Build-input guidance was checked against official Vite/Docker documentation linked in the specification. No runtime/browser/coverage result is claimed. Record the confirmed merge in this PR's body first and carry it into the next task's ledger update. E01 foundation and E00 editor proof remain the next implementation work.

2026-09-06: P02 confirmed `done`, merged through [PR #4](https://github.com/Flippylolz/fillable/pull/4) at `ba5a2e651b975b9ad59dca801c9d3f43edf76be1`. Local main was synchronized before P03 began.

2026-09-06: P03 prepares `AI/AUTONOMOUS_AGENT_PROMPT.md` on `task/p03-autonomous-agent-prompt` for the user's next implementation agent. It directs continuous task delivery with one PR per task, actual CI/coverage enforcement before code merges, bounded escalation only for unavoidable user input, preservation of all accepted constraints, deployment last, and evidence-based resumption/completion. Creating the prompt does not launch an agent, scheduler, or implementation work. Validation and PR evidence follow before delivery.

2026-09-06: P03 submitted as [PR #5](https://github.com/Flippylolz/fillable/pull/5), status at submission `in_review`. Validation passed for 18 public Markdown files, 90 local links, balanced fences, and Git whitespace. Reviewed prompt consistency against the roadmap, agent rules, PR workflow, and accepted product/deployment constraints. Public docs exclude the local deployment identity; synthetic fixtures are unchanged. No application tests, coverage, agent launch, or implementation is claimed. Record the confirmed merge in this PR's body first and carry it into the next task's ledger update. A user-started implementation agent should inspect current state and begin/resume the next ready task, initially E01.1 if still outstanding.

2026-09-06: P03 verified merged through [PR #5](https://github.com/Flippylolz/fillable/pull/5)
at `7ae211784066b034ef9f5f2cb5f577edeb65e5a2`. Clean checkout and remote inspected;
no open PRs or unfinished code existed. E01.1 started on `task/e01-1-app-foundation`
from that origin/main commit. Scaffold includes typed FastAPI health, localized
React/Vite shell, exact dependency locks and digest-pinned non-root Docker check
images, coverage gates and initial catalog checks. Required strict `ci-required`
GitHub protection is enabled, including administrators, before any code merge.
E01.1 remains `in_progress` pending local verification and its task PR. Deployment
and all existing server services are untouched. Next: finish tests, submit E01.1,
verify CI/auto-merge and then begin E01.2 from the merged main revision.

2026-09-06: E01.1 local Docker verification passed: backend health contract and
Ruff, 9/9 executable lines (100%), no executable branches (0/0, not applicable);
frontend TypeScript/production build, catalog checks, nine behavior tests,
27/27 lines and 14/14 branches (both 100%). Raw coverage source inclusion passed.
Coverage negative tests reject 89.99%, invalid counts, missing/invalid reports,
and unreported source; exactly 90% passes. Browser, migrations, persistence, and
editor checks are not claimed by this scaffold task. Next: PR and Actions verification.

2026-09-06: E01.1 submitted as [PR #6](https://github.com/Flippylolz/fillable/pull/6),
status `in_review`, auto-merge enabled under verified strict protection. HTTPS push
lacked workflow scope; the existing authorized SSH identity successfully published
the same branch. CI passed both application suites but failed on Linux creating a
nested mountpoint in a read-only source mount. Added the mountpoint before container
startup. The failed `checks` propagated to failed `ci-required` and blocked merging,
providing real aggregation evidence. Next: verify the corrected Actions run and merge.

2026-09-06: E01.1 confirmed `done` via [PR #6](https://github.com/Flippylolz/fillable/pull/6),
merged `8d0903014a2d0b2c771693caba2199fb80e9ed3e`; Actions run 34020883600 passed
`checks` and `ci-required`. Merge evidence was added to its PR body and main was
synchronized. E01.2 started on `task/e01-2-compose-gateway` from that commit.
Adds base/dev/prod Compose and non-root nginx static/dev gateway targets, same-origin
API routing, Vite WebSocket forwarding, loopback-only configurable ports, source
mounts, health ordering, and retained document bind mount. Persistent database/queue
volumes and migrations remain E01.3. Next: verify both isolated local stacks, CI and PR.

2026-09-06: E01.2 local checks passed: both Compose variants validate and reach
health; both effective nginx configs validate; development HTML/Vite and production
hashed assets serve through gateway; same-origin health succeeds. Production nginx
runs non-root without Node. Required Docker suites passed again: backend 9/9 lines,
branches not applicable; frontend 27/27 lines, 14/14 branches (100%). Actual
application persistence and hot-reload browser acceptance remain E01.3/E01.6.

2026-09-06: E01.2 confirmed `done` through [PR #7](https://github.com/Flippylolz/fillable/pull/7)
at `9891ab5fd8dab66d06b65df890737008ad8c97df`; Actions 34021093942 passed both
required jobs and squash auto-merge completed. Recorded merge in the PR body,
synchronized main, and started E01.3 on `task/e01-3-persistent-services`.
PostgreSQL/Redis are digest-pinned, private and persistent; Alembic completes
before API/worker startup. Readiness checks exact migration heads and Redis;
process health stays separate. RQ uses JSON serialization and disables job-argument
logging. Next: real-service tests, startup/restart persistence, PR and required CI.

2026-09-06: E01.3 local verification passed: four backend tests against real
PostgreSQL/Redis, online/offline/repeat migrations and synthetic-data preservation,
readiness failures, and actual RQ JSON job execution. Backend includes migration and
worker configuration source: 64/64 lines, 6/6 branches (100%). Frontend nine tests,
27/27 lines and 14/14 branches (100%), type/build/catalog checks passed unchanged.
Isolated production stack started in migration order; PostgreSQL and Redis synthetic
markers survived `down` and recreation, then only those markers were removed.
Worker was listening and public-local `/api/ready` returned ok. No live server touched.

2026-09-06: E01.3 confirmed `done` via [PR #8](https://github.com/Flippylolz/fillable/pull/8)
at `4489b01a5060ec8b396273d9c30310183d1d3fc0`; Actions 34021453232 passed required
checks and protected auto-merge completed. Recorded the merge in its PR body,
synchronized main, and began E01.4 on `task/e01-4-api-contract`. Adds content-free
machine-readable errors, generated OpenAPI/TypeScript contracts, localized client
error mapping and mandatory drift detection. Next: Docker suites and task PR.

2026-09-06: E01.4 Docker verification passed: five backend tests, 98/98 lines and
6/6 branches (100%); twelve frontend tests, 35/35 lines and 19/19 branches (100%).
Type/build/catalog and raw source-inclusion gates passed. Both generated artifacts
were regenerated using CI's container user/mount commands and compared byte-for-byte
without differences. Errors omit submitted values/internal messages; typed client
success/error requests and both-locale mappings passed. Next: task PR and Actions.

2026-09-06: E01.4 confirmed `done` via [PR #9](https://github.com/Flippylolz/fillable/pull/9)
at `66201ad60070a5dc51883fb26575b03822a9a25b`; Actions 34021791833 passed both
required jobs including generation drift, and protected squash auto-merge completed.
Recorded merge evidence in its PR body, synchronized main, then started E01.5 on
`task/e01-5-browser-quality-checks`. Adds frontend ESLint, backend mypy, stronger
AST copy/catalog checks with negative tests, and desktop/mobile Playwright smoke
checks against the full production image. Next: verify browser runs, inspect captures,
complete required checks, open task PR and verify its merge.

2026-09-06: E01.5 local Docker checks passed: Ruff/mypy, five backend tests with
99/99 lines and 6/6 branches (100%); ESLint/TypeScript/build, 17 localization
validator tests, twelve frontend tests with 35/35 lines and 19/19 branches (100%).
Four Playwright tests passed against the production stack across desktop/mobile,
covering real health/readiness and failed-request retry. Both full screenshots were
visually inspected; current shell text fits without clipping. Product pages and
saved profile locale are not claimed. Next: task PR and required Actions/merge.

2026-09-06: E01.5 confirmed `done` through [PR #10](https://github.com/Flippylolz/fillable/pull/10)
at `28a03bda435167518235aabd5a878a117f21cb7a`; Actions 34022095669 passed required
static, browser and coverage checks, then protected auto-merge completed. Recorded
merge in its PR body, synchronized main and started E01.6 on
`task/e01-6-development-verification`. A fresh-index verification copy found Vite's
non-root cache permission failure; moved its cache to `/tmp/fillable-vite` and
allowed the internal gateway hostname. The repeated check passed real browser HMR,
backend reload, restoration of temporary edits, PostgreSQL/Redis persistence across
recreation, four production browser tests and non-root/no-Node static serving.
The working checkout was not mutated; verification copies/volumes are retained.
Replaced the planned local guide with executable commands. Next: frontend regression,
PR, required CI and merged-state verification. No live-server action occurred.

2026-09-06: E01.6 frontend regression passed after the Vite fix: ESLint, 17
localization checks, TypeScript/build, twelve tests, 35/35 lines and 19/19 branches
(100%). Backend source is unchanged from E01.5's 99/99 lines and 6/6 branches;
required CI reruns it. Public Markdown links/fences passed after guide replacement.
