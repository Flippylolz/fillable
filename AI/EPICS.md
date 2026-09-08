# Implementation epics

Status vocabulary: `ready`, `waiting`, `in_progress`, `in_review`, `done`. Waiting means dependencies or a recorded product decision are outstanding. A task awaiting PR merge is `in_review`; an epic remains open until all required tasks and acceptance criteria are delivered.

Scope: the four pages in [Product](PRODUCT.md), including version-history UI inside the workspace. Ukrainian/English UI localization and the saved profile language switcher are MVP requirements under [Localization](I18N.md). Every user-facing task supplies both translations. Epics describe implementation boundaries, not additional product pages. Administrator screens, a trash browser, advanced diffs, and public registration are outside MVP.

Delivery rule: each individual task ID below gets its own branch and PR, with auto-merge enabled when ready and actually protected by required checks. Follow [PR workflow](PR_WORKFLOW.md); record PR URLs and merge commits rather than marking an open PR done.

## Roadmap

Planning task P00: consolidate the accepted MVP decisions, architecture, epics, and agent rules in one documentation PR (`task/p00-mvp-plan`). Acceptance: linked documents agree on free-only editor components, deterministic detection without AI, local/production environments without backups, HTTP on a new shared-nginx port, and the existing four-page/history/coverage/PR requirements. Validate Markdown links and consistency; no application coverage is claimed for this documentation task. A separate empty Git-history bootstrap establishes `main` before opening the PR and contains no task files.

Planning task P01: add the accepted UI localization requirement in one documentation PR (`task/p01-ui-localization`). Acceptance: product, decisions, architecture, epics, CI plan, and agent rules agree on Ukrainian as the default UI language, English as secondary, all application copy in i18n catalogs, and a profile language switcher whose preference persists across sessions. Specify translation completeness checks and preservation of document content when switching UI language. Validate Markdown links and consistency; application implementation and coverage are outside this documentation task.

Planning task P02: record the user's version badge design and behavior in one documentation PR (`task/p02-version-badge`). Acceptance: preserve the supplied CSS, seven-character deployed-commit display, `development` fallback, fixed desktop/mobile placement, theme-independent colors, monospace value, and noninteractive click-through behavior. Link the build/deployment metadata contract and future implementation/verification tasks, keeping labels in i18n. The user explicitly chose specification-only delivery; validate documentation without adding application code or claiming runtime/coverage checks.

Planning task P03: prepare a reusable autonomous implementation prompt in one documentation PR (`task/p03-autonomous-agent-prompt`). Acceptance: direct the next agent to execute the roadmap, maintain one task per PR and required CI/coverage, continue after each merge, preserve accepted product/deployment constraints, and ask the user only for an unavoidable dependency it cannot safely resolve. Continue independent work while awaiting input and stop all work only when no useful authorized progress remains. Include resumption evidence and a concrete completion definition. Creating this prompt does not launch another agent, start implementation, or schedule background work; validate documentation links and consistency.

| Epic | Outcome | Dependencies | Status |
| --- | --- | --- | --- |
| E00 | Free editor feasibility and selection | Zero-fee end-to-end components or project-owned implementation | done: E00.1–E00.5 verified and merged, PRs #2 and #14–#17 |
| E01 | Docker foundation and application skeleton | Accepted stack | done: E01.1–E01.8 verified and merged, PRs #6–#13 |
| E02 | Login/profile, accounts, local storage, and quotas | E01 | done: E02.1–E02.7 merged |
| E03 | Upload, templates, and processed-document library | E02 | done: E03.1–E03.6 and E03.1b verified merged; later history scenarios extend E06 acceptance |
| E04 | Field discovery and review model | E03; editor mapping work needs E00 | done: E04.1–E04.5 merged; saved review/copy acceptance verified through E06.2a–E06.2c and E06.6 |
| E05 | Workspace editor, settings, and synchronized sidebar | E00, E03, E04 field contract | done: E05.1–E05.6b verified merged; history completed through E06.3b/PR #59 |
| E06 | Safe saves, version-history UI, restoration, and DOCX export | E02, E05.1–E05.6a | done: E06.1a–E06.7 verified and merged; autosave completed through PR #61 |
| E07 | MVP acceptance and CI verification | E03–E06 | done: corrective browser selection merged in PR #70 |
| E08 | Final deployment through GitHub Actions | All E00–E07 done; supplied target access/nginx/port verified | verified: HTTPS rollout and deployed MVP/persistence passed; final delivery tracked by PR #75 |
| E09 | Post-release user-requested improvements and automation | E08 | in_progress: E09.1–E09.11 sections below |
| E10 | Manual QA findings and corrections | E00–E08 delivered; findings in [QA findings](QA_FINDINGS_E10.md) | ready |

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
- Login uses HttpOnly/SameSite, CSRF and exact-origin checks including the port. D024 production HTTPS requires Secure; local HTTP development retains scheme-specific cookies. Do not assume cookies are isolated from other apps by port.
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
- E05.6a: Add in-workspace back navigation, owned title rename, zoom and field highlighting; preserve draft state and current saved downloads. Depends on E05.5.
- E05.6b: Integrate working save/history entry points and save status after the corresponding E06 persistence/history operations exist. Do not substitute inactive controls for those operations.

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

- E06.1a: Add the owner/session/tab-fenced editing lease API, expiry, idempotent acquisition and generation-safe renewal/release, with PostgreSQL concurrency and migration tests.
- E06.1b: Integrate acquisition/renewal, read-only expiry and explicit stale-session recovery into the mounted workspace; retain drafts and verify browser concurrency. Depends on E06.1a. E06.2 saves must enforce the same lease fence.
- E06.2a: Validate the persisted working-document/field-review contract, retaining accepted origins, dismissed and missing records, with cross-language synthetic fixtures.
- E06.2b: Rebase independent copies of edited exports by verified structural correspondence, retaining matching review and source identities. Depends on E06.2a.
- E06.2c: Implement atomic revision/lease-checked, quota-enforced saves with matching document/review snapshots and exact idempotent results. Depends on E06.2a–E06.2b.
- E06.2d: Integrate real manual saves, exact local-revision acknowledgment and recoverable failure/reopen behavior into the workspace. Depends on E06.2c; satisfies the save portion of E05.6b, while history controls await E06.3.
- E06.3a: Add owner-scoped, bounded revision listing and exact read-only model/review preview APIs for templates and documents. Depends on E06.2d.
- E06.3b: Build the complete in-workspace history panel with timestamps, current marker, read-only preview, exact historical download and restore. Depends on E06.3a, E06.4 and E06.6; completes E05.6b. Deliver after those APIs, before E06.5 retention and E06.7 autosave.
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

- E07.1a: Correct expired-session recovery before final acceptance: keep same-owner drafts mounted through fresh CSRF/sign-in, pause editing and autosave, fence late session responses, and require explicit discard before switching accounts. Deliver in its own PR.
- E07.1b: Verify login, library, profile, and workspace navigation and states in Ukrainian and English, including the history panel, localized errors/accessibility text, and long Ukrainian labels. Verify default language, profile preference persistence/failure, and unchanged document data/drafts when switching. Check account/quota operator commands and user-facing storage meters. Confirm the version badge appears once on each page without blocking controls on desktop/mobile or changing its specified colors with theme.
- E07.1c: Correct the manual-save browser journey's timing-dependent heading selection after the main-branch CI failure. Preserve field creation/save/history assertions, verify repeated desktop/mobile journeys and full required CI, and deliver separately before resuming E08.2.
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
- E08.3: Configure only Fillable's persistent volumes, private upstream, resource limits, and schema-compatible release rollback procedure. No backups or staging environment are required. Use the owner-deployed D024 HTTPS listener on internal 3200, with only Fillable's TCP relay publishing host 3200. Coordinate with the shared nginx task before ingress changes; none are needed for rollout. Preserve local document storage, quotas, and existing workloads.
- E08.4: Run the workflow: validate capacity and persistence configuration, apply tested non-destructive migrations, update Fillable services, check private/public ports, validate effective nginx configuration read-only and preserve the owner-deployed TLS route. Perform app smoke checks at the exact HTTPS URL and recheck existing services/routes; do not require a backup.
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

2026-09-06: E01.6 confirmed `done` through [PR #11](https://github.com/Flippylolz/fillable/pull/11)
at `bee8847297980f54d38a8388a9c891519d48ab15`; Actions 34022545662 passed the fresh
Docker development/persistence check and required coverage jobs. Recorded merge in
its PR body, synchronized main and started E01.7 on
`task/e01-7-coverage-gate-audit`. The real downloaded Actions 34022095669 artifact
contains both raw reports and desktop/mobile screenshots: backend 99/99 lines,
6/6 branches; frontend 35/35 lines, 19/19 branches (100%). Strict Actions-bound
`ci-required` and administrator enforcement were reread from GitHub protection.
Disposable-container probes passed: unimported backend source caused 99/161 lines
and rejected coverage despite five passing tests; frontend caused 35/66 lines and
19/79 branches with twelve passing tests and correctly failed. Contract tests
accept exactly 90% independently, reject deficient lines/branches, missing/invalid
reports and unreported source, and reject missing/failed/skipped/cancelled aggregator
inputs. Required CI runs these negative checks without retaining probe source or
replacing normal coverage artifacts. Checkout/upload actions now use verified
upstream v7.0.1 commit pins (Node 24). Next: task PR, required Actions and merge;
then E01.8 version badge. Deployment remains untouched.

2026-09-06: E01.7 confirmed `done` through [PR #12](https://github.com/Flippylolz/fillable/pull/12)
at `c627734fcd833391a51452090a91950f46b5cd4b`; Actions 34023028738 passed normal
coverage, actual uncovered-source probes and the required aggregator. Recorded the
merge in its PR body and synchronized main. E01.8 began on
`task/e01-8-version-badge`: shared catalog-based badge outside page containers,
exact supplied CSS, safe component interpolation, validated seven-character source
commit/fallback and Docker compilation argument. Local Docker static builds passed
six desktop/mobile browser tests each with supplied commit and missing metadata.
Checks include scrolling, real safe-area overrides, light/dark and inline-code theme
styles, keyboard skipping, and mouse/touch click-through to the retry control.
Both final screenshots were visually inspected. Frontend lint, catalog/type/build
checks and 23 unit tests passed: 41/41 lines and 25/25 branches (100%). Backend source
is unchanged at 99/99 lines and 6/6 branches; required CI reruns its suite. Containers
for this isolated task were stopped, volumes preserved. Next: PR, CI and confirmed
merge, then E00.2 free-editor comparison. All four pages and live release verification
remain their later tasks; no deployment or server access occurred.

2026-09-06: E01.8 confirmed `done` through [PR #13](https://github.com/Flippylolz/fillable/pull/13)
at `1cd0bc9628a24aaac628f12d10ef9468ffe62e4d`; Actions 34023470277 passed both
required jobs, including supplied/fallback static badge browser checks and coverage
failure probes. Merge evidence is in its PR body. E01 acceptance is complete through
eight separate protected task PRs; product-page badge integration remains E07.
Synchronized main and began E00.2 on `task/e00-2-free-editor-comparison`.
Official licensing/API/version/localization sources were inspected for ProseMirror,
ONLYOFFICE, SuperDoc, Collabora, Tiptap conversion and docx-preview. The comparison
records no installed editor or runtime fidelity claim. Provisional E00.3 direction:
MIT ProseMirror with a package-preserving Python adapter, subject to corpus proof.
D008 and the project license remain unsettled; no paid API, trial or engine adopted.
This documentation task changes no application source and claims no new application
coverage run. Next: validate documentation, PR and required CI/merge, then E00.3;
E02 is independently ready. Deployment/server inspection remains deferred to E08.

2026-09-06: E00.2 confirmed `done` through [PR #14](https://github.com/Flippylolz/fillable/pull/14)
at `38d2a3dd1b741dc1c515a2ae51cbe511720c816f`; Actions 34023851032 passed both
required jobs. Merge recorded in its PR body, main synchronized and E00.3 started
on `task/e00-3-editor-synchronization`. Adds bounded source-package mapping,
stable native IDs, reusable ProseMirror controls/transactions, source-derived corpus
harness, full MIT notices, and required fixture/license/browser checks. No retained
file write or public document API was introduced. Native text replacement required
an explicit transaction handler to preserve controls; DOM parsing now preserves
run identities and whitespace. The HTTP harness uses compatible random identifiers.
Final local gates passed: 16 backend tests, 209/209 lines and 48/48 branches (100%);
30 frontend tests, 156/159 lines (98.11%) and 82/85 branches (96.47%), with lint,
catalog/type/build checks. Browser proof covers linked native fields, direct/sidebar
updates, split-run field creation, focus and locale-preserved draft/history. The
complete corpus screenshot was visually inspected as a structural editor canvas,
not a Word-pagination claim. The final fresh-index Docker run passed editor/reload,
persistent recreation and six production browser tests; earlier artifact-mount and
test-option typing failures were corrected. Next: task PR, required CI/auto-merge,
then E00.4 export/reopen and surrounding-edit proof. D008 remains provisional; E02
is independently ready and deployment remains untouched.

2026-09-06: E00.3 confirmed `done` through [PR #15](https://github.com/Flippylolz/fillable/pull/15)
at `01ad6089a78a5d3a42a5afe39c42409861cbef98`; Actions 34025494756 passed both
required jobs at head `5f8c1be17f2b7db15aec83365d2b321d50bc305f`. Merge recorded
in its PR body. E00.4 is `in_progress` on `task/e00-4-docx-roundtrip`, based on that
merge. Adds in-memory validated source-package export, lxml 6.1.3 namespace
preservation, newline/tab handling, source-derived paragraph identities, and
opt-in synthetic export/reopen routes isolated from the production app. The first
fresh-index Docker run passed three development browser tests (including actual
DOCX download/reopen), reload/persistence and six production browser tests.
Nineteen targeted backend tests passed; full final application coverage and
independent LibreOffice visual inspection are pending. No PR is open yet. Next:
finish visual/security/coverage verification, document support limits, open this
individual task PR, verify strict required checks, enable auto-merge and follow
through the actual merge. No server access or retained user-file writes occurred.

E00.4 final local verification: 26 backend tests passed with 465/469 lines (99.15%)
and 168/174 branches (96.55%); 34 frontend tests passed with 221/224 lines (98.66%)
and 120/129 branches (93.02%). Both raw gates include all eligible application
source. Lint, typing, localization, build and gate-boundary checks passed. The
fresh-index Docker proof passed three development browser checks and six production
checks, with persistence preserved. Actual browser-created fields also export and
reopen with their values/keys intact. Independent LibreOffice/Poppler verification
passed exact no-edit ZIP/page identity, three edited pages, unchanged page-two pixels
and Ukrainian text. Original and edited pages were fully inspected; Microsoft Word
has not been used. Required CI now includes the reproducible QA-only rendering check.
Strict `ci-required` protection and administrator enforcement were reverified.
E00.4 is ready for its individual PR; E00.5 follows only after verified merge.

2026-09-06: E00.4 confirmed `done` through [PR #16](https://github.com/Flippylolz/fillable/pull/16)
at `b3119eb6e0ec6b1d7c21bf51f62cccd97a4fe90a`; Actions 34027104805 passed both
required checks at head `bc45e334544dd1e3f7e433ebde9aaabe880a873d`, including
independent rendering and actual below-threshold probes. Final merge evidence was
recorded in its PR body and main synchronized. E00.5 starts on
`task/e00-5-editor-adoption`: D008 selects the proven free ProseMirror/Python path,
with exact versions, notices, support matrix and protected/unproved features.
This documentation-only task adds no application source or new coverage claim;
E00.4's measured results remain the preceding implementation evidence. Next:
validate linked docs, deliver this individual PR through required CI/auto-merge,
verify its merge and mark E00 complete, then implement E02.1 accounts/sessions.
Production editor/save integration and all live-server work remain later tasks.

2026-09-06: E00.5 confirmed `done` through [PR #17](https://github.com/Flippylolz/fillable/pull/17)
at `4103f9bab8d7cd9aee9663de88ecb33e18721f2d`; Actions 34027356979 passed both
required checks at head `629d5807dda40d0b179c37de219fc05faf2005da`. Merge evidence
was recorded in its PR body. E00 is complete through its five individual task PRs.
Main synchronized and E02.1 began on `task/e02-1-accounts-sessions`. Account/session
schema, migration, operator commands and auth endpoints are being implemented;
real PostgreSQL tests, UI, generated API and final coverage/CI remain outstanding.
No account default credentials, public signup, quota bypass or server changes.
Next: complete authentication tests and login UI, verify Docker/browser/coverage,
then deliver E02.1 alone through protected PR/auto-merge before continuing E02.2.

E02.1 final local proof: 35 backend tests passed, 742/747 lines (99.33%) and
221/228 branches (96.93%); 39 frontend tests passed, 266/270 lines (98.52%) and
156/165 branches (94.55%). Raw source-inclusive gates, lint/type/catalog/build
checks and real uncovered-source rejection probes passed. PostgreSQL tests cover
constraints, concurrent attempt accounting, rotation, idle/absolute expiry,
role/inactive-user checks, CSRF/origin rejection, credential reset, private operator
commands and real password rehashing. No default user is created by migration/startup.
The final fresh-index Docker run passed three development checks and eight
production browser checks, including desktop/mobile login, locale restoration,
logout and cookie behavior. Source-restore test writes are now atomic; production
QA reports use writable mounted output paths. Login screenshots were inspected.
The CI job pins its private browser origin across dependency recreation. Next:
individual E02.1 PR, reverify strict required checks, enable auto-merge and verify
completion before E02.2 quota models. Deployment and server services remain untouched.

2026-09-06: E02.1 confirmed `done` through [PR #18](https://github.com/Flippylolz/fillable/pull/18)
at `15b568b5e7eefe27124b30cb9823276dec28c2ec`; Actions 34028841683 passed both
required checks at head `ee2f2af275315618bbe482e79abbafe32ab0043d`. Merge evidence
was recorded in its PR body. Main synchronized and E02.2 began on
`task/e02-2-quota-lifecycle-models`. Quota settings/accounts, reservation/file schemas,
strict byte arithmetic and migration/backfill tests are in progress. This task
adds no retained-file write path; E02.3 implements allocation and filesystem recovery.
Next: complete schema/integration checks and docs, enforce coverage/CI, deliver
this individual PR and verify protected auto-merge before E02.3.

E02.2 local verification passed: 41 backend tests, 796/801 lines (99.38%) and
223/230 branches (96.96%), with lint, typing and raw full-source coverage. Tests
compare runtime metadata against the actual migrated schema, exercise backfill and
repeat upgrades, reject owner/result mismatches and invalid counters/states, and
verify populated storage metadata blocks downgrade. Frontend source is unchanged;
its preceding verified coverage is 266/270 lines and 156/165 branches, and required
CI will rerun all frontend/browser checks. No retained file write is introduced.
Next: task PR and protected CI/auto-merge, then E02.3's shared allocation/write service.

2026-09-06: E02.2 confirmed `done` through [PR #19](https://github.com/Flippylolz/fillable/pull/19)
at `4d160cc5e9040a5921974557fd808abdd9542b33`. Actions 34029829814 passed both
required checks for head `b34e013da0e7a3ffccdbf90191ef8400502eacdf`; its PR body
records final merge evidence. Main synchronized and E02.3 began on
`task/e02-3-local-storage`. The service implements serialized quota reservations,
bounded streaming, exclusive durable publication, immutable owner-checked reads,
transactional finalization hooks and idempotent crash cleanup. Scoped Docker storage
initialization and API/worker persistence checks are included. Initial PostgreSQL
and filesystem verification passed; final full checks and fresh Docker proof are
running. Next: complete verification, individual PR and protected auto-merge; confirm
its merge before E02.4 deletion/reconciliation. No server access or deployment.

E02.3 local verification passed: 55 backend tests, 1099/1104 lines (99.55%)
and 303/310 branches (97.74%), including source-inclusive lint/type/raw gates.
The fresh-index Docker proof passed three development checks, eight production
browser checks, and API/worker retained-byte/accounting checks across recreation.
Its isolated copy is `/private/tmp/fillable-verify.oFwZaN` locally; CI retains its own
reports. Frontend source is unchanged; preceding verified coverage is 266/270 lines
and 156/165 branches. Required CI reruns frontend, browser and independent DOCX
render verification. Next: open E02.3 PR, verify real strict protection, arm exact-head
squash auto-merge and follow required checks through actual merge.

E02.3 is `in_review` in [PR #20](https://github.com/Flippylolz/fillable/pull/20).
Final recovery review added preservation of the last staging hard link when a
committed final link is missing or replaced. The focused regression and repeated
committed cleanup test pass; final full coverage is 1107/1112 lines (99.55%) and
307/314 branches (97.77%) across 56 backend tests. Auto-merge was paused during this
update and will be rearmed only for the verified updated head with required CI.

2026-09-06: E02.3 confirmed `done` through [PR #20](https://github.com/Flippylolz/fillable/pull/20)
at `6c75c83f0863ea9abf72eb05a3a82bff43820573`. Actions 34031170760 passed both
required checks for exact head `31594cec3f3400546b5e8a17e19e6987eb875218`; final
merge evidence is in its PR body. Main synchronized and E02.4 started on
`task/e02-4-storage-reconciliation`. Work covers exclusive retained deletion,
shared download locks, bounded storage-operation reconciliation, content-free audit
records and operational capacity configuration. E06 owns document jobs/outbox and
E07.3 owns periodic scheduling; this task provides their storage recovery primitive.
Next: implement and verify failure/concurrency/migration/CLI cases, update docs,
then deliver this individual task through protected CI/auto-merge. Deployment remains last.

E02.4 local verification passed: 67 backend tests, 1332/1338 lines (99.55%) and
378/386 branches (97.93%), with lint, typing and raw full-source gates. Real
PostgreSQL/filesystem tests cover shared-reader exclusion, authorized idempotent
deletion, callback rollback, physical cleanup failure, a real child exit after
unlink, conservative counter repair, bounded reconciliation/inventory, audit migration
and validated private maintenance commands. The fresh-index Docker proof passed
three development and eight production browser checks, separate-copy deletion,
original/accounting persistence in both API and worker, and one-shot reconciliation,
inventory and capacity checks. Its isolated local copy is
`/private/tmp/fillable-verify.w2kcop`; volumes are preserved. Frontend source is
unchanged (preceding verified 266/270 lines and 156/165 branches); required CI reruns
its complete checks. Next: E02.4 task PR, strict protected CI and exact-head squash
auto-merge, verify merged state, then E02.5 usage and audited quota commands.

2026-09-06: E02.4 confirmed `done` through [PR #21](https://github.com/Flippylolz/fillable/pull/21)
at `a2bd687d54d056537ee51e8236b3b10495019359`. Actions 34032214377 passed both
required checks for exact head `f4514577a472d2dcbcbf6266b6b7f7f27ee27ea7`; final
merge evidence is recorded in its PR body. Main synchronized and E02.5 began on
`task/e02-5-quota-administration`. Current-user usage and audited container-only
quota commands are implemented; 72 backend tests pass, including PostgreSQL lock
wait evidence and actual setters during streaming. Typed API regeneration and fresh
Docker/operator/browser verification are in progress. Next: finish checks/docs,
individual protected PR and verified auto-merge, then E02.6 profile. No deployment.

E02.5 local verification passed: 72 backend tests, 1419/1426 lines (99.51%) and
395/404 branches (97.77%), including lint, typing and raw full-source gates. The
OpenAPI/TypeScript contract was regenerated through Docker. The fresh-index proof
passed three development and eight desktop/mobile production browser checks,
real default/zero-override/inherit/show commands, rejection of a retained write at
zero allowance without losing the original, and authenticated no-store usage reads
with rejection after logout. The isolated local copy is
`/private/tmp/fillable-verify.f1Efoc`; its volumes are preserved. Frontend runtime
source is unchanged; preceding verified coverage remains 266/270 lines and 156/165
branches, and required CI reruns the full frontend checks. Next: E02.5 individual
PR, reverified strict protection and exact-head squash auto-merge; confirm actual
merge before E02.6 profile implementation. Deployment remains last.

2026-09-06: E02.5 confirmed `done` through [PR #22](https://github.com/Flippylolz/fillable/pull/22)
at `4b0c762c7a3d15ea79f0d6fc93829fe94bb4cb8a`; Actions 34032925674 passed both
required checks for exact head `c49ab01b9f1432310c3c13d95d7c2d302a28aa05`. Final
merge evidence is in its PR body. Main synchronized and E02.6 began on
`task/e02-6-profile`. Profile display-name/password endpoints, session fencing and
rotation, consistent credential lock ordering, bilingual profile/usage UI and
logout/save coordination are implemented. Local backend verification passes 77 tests
(1487/1494 lines, 409/418 branches); frontend verification passes 45 tests above both
gates. Docker browser and visual checks are next, using a separate explicitly
provisioned synthetic profile account. No E02.6 PR yet; language editing is E02.7.
Next: finish browser/visual/raw-gate checks and docs, deliver individual protected PR,
verify merge before continuing. The user's renewed “continue” instruction preserves
the full autonomous roadmap and deployment-last scope; no server access occurred.

E02.6 local verification passed: 77 backend tests with 1487/1494 lines (99.53%)
and 409/418 branches (97.85%); 45 frontend tests with 322/326 lines (98.77%) and
214/228 branches (93.85%). Lint, typing, catalogs, build and raw full-source gates
passed. The fresh-index Docker proof at `/private/tmp/fillable-verify.rH1jo0`
passed three development and ten production browser checks, including both profile
viewports, name persistence, password rotation and peer-session revocation. Desktop
and mobile profile screenshots were visually inspected; labels/cards remain readable
and the mobile layout stacks without horizontal overflow. Retained storage and
operator/reconciliation checks passed; isolated volumes remain preserved. The real
negative frontend coverage probe now scales its uncovered source to application
size so growth cannot invalidate its assertion; thresholds/exclusions are unchanged.
Profile is the signed-in foundation-shell content until E03 adds library navigation.
Next: individual E02.6 PR, strict required CI and exact-head squash auto-merge;
verify actual merge before E02.7. Deployment remains last.

2026-09-06: E02.6 confirmed done through [PR #23](https://github.com/Flippylolz/fillable/pull/23)
at `ebd287051262505c9fa53a8098fb8d4418c54c74`; Actions 34037776985 passed both
checks for exact head `1f1a14cde04d709bf384c45667ff6e2b040b848a`. Final evidence is
in the PR body. Main synchronized; E02.7 is underway on `task/e02-7-language`.
Authorized language updates and bilingual selector are implemented; failed saves
restore the saved selection, successful responses apply the account language without
clearing profile drafts. Verification is in progress. No deployment access occurred.

E02.7 local verification passed: 79 backend tests, 1496/1503 lines (99.53%) and
409/418 branches (97.85%); 46 frontend tests, 329/333 lines (98.80%) and 230/244
branches (94.26%). Lint, typing, catalogs, build, raw full-source coverage and both
real negative probes passed. Fresh-index Docker proof at
`/private/tmp/fillable-verify.s0sgni` passed three development and twelve production
browser checks, including failed-save recovery, unchanged drafts/usage, refresh,
new browser login and stale peer preference recovery on both viewports. English
screenshots were visually inspected: native language labels and storage numbers
remain readable on desktop/mobile. Original synthetic storage persisted through
recreation and all quota/maintenance checks passed; volumes preserved. Next:
individual E02.7 PR, required protected CI and verified auto-merge, then E03.
E03.2 validation and E03.3 persistence are prerequisites for delivering E03.1's real
upload flow; follow that dependency order rather than shipping a simulated upload.
Deployment remains E08, last.

2026-09-06: E02.7 confirmed done through [PR #24](https://github.com/Flippylolz/fillable/pull/24)
at `75c897f834cbdbafb134e7506ba742132e85f760`; Actions 34038437879 passed both
checks for exact head `a113247bf75f298f8d309f4cce1c5968d4338dd4`. E02 is complete.
Main synchronized and E03.2 began on `task/e03-2-docx-validation`, preceding E03.3
persistence and E03.1's real upload UI. Source-preserving upload admission checks
and bounded shared ZIP/XML reading are implemented. Initial full checks passed 128
backend tests (1635/1643 lines, 496/506 branches); corruption checks and round-trip
verification are in progress. No upload endpoint is exposed by this task. Next:
finish checks/docs, individual PR and verified protected merge before persistence.

E03.2 final local backend checks passed: 131 tests, 1646/1653 lines (99.58%) and
505/514 branches (98.25%), with lint, typing and full-source gates. The shared-reader
fresh-index proof at `/private/tmp/fillable-verify.4nE0DS` passed three development
and twelve production browser checks plus storage/quota/persistence verification.
Independent LibreOffice/Poppler verification passed: no-edit bytes and all pages
identical, edited output retains three pages, unchanged page two and Ukrainian text.
Edited pages one and three were visually inspected. The final additional same-part
relationship-ID check is covered by the full backend suite; required CI rechecks the
complete final commit. The backend negative coverage probe now scales with source
size, preserving thresholds/exclusions. Frontend source is unchanged from E02.7's
verified 329/333 lines and 230/244 branches; required CI reruns it. No upload endpoint
or persisted resource is claimed yet. Next: E03.2 protected task PR, exact-head
auto-merge and actual merge verification, then E03.3 persistence. No deployment.

2026-09-06: E03.2 confirmed done through [PR #25](https://github.com/Flippylolz/fillable/pull/25)
at `98fd65320f0fcfa598a56851a40f62315eeac4fa`; Actions 34039344581 passed both
checks for exact head `9531e9f3f11d62ac8dcf18c2b0619b706c2332c9`. Final evidence is
in the PR body. Main synchronized; E03.3 is underway on
`task/e03-3-document-persistence`. Resource/version schema, quota-atomic upload,
owner list/detail APIs, bounded metadata/body admission and bilingual error mapping
are implemented. Initial checks pass 140 backend and 46 frontend tests; final title
validation, generated contract and Docker API persistence/gateway proof are being
checked. The gateway now streams API requests and supports the bounded upload size;
names/titles travel in a bounded base64 UTF-8 JSON header, not request URLs. No upload
UI, download/delete action or processing job is claimed by this task. Next: finish
checks/docs and individual protected PR; verify merge before E03.1 library UI.

E03.3 final local verification passed: 140 backend tests, 1827/1834 lines (99.62%)
and 533/542 branches (98.34%); 46 frontend tests, 340/344 lines (98.84%) and 241/255
branches (94.51%). Lint, typing, catalog validation, build, raw full-source gates and
both real negative coverage probes passed. The corrected fresh-index Docker proof
at `/private/tmp/fillable-verify.Im943q` passed three development and twelve
production browser checks. It verified API upload/committed retry, rejection of
malformed input above 1 MiB through the gateway, original/model ownership and exact
bytes after recreation from API and worker, plus existing quota/maintenance checks.
The worker QA invocation explicitly receives the public origin; normal worker config
is unchanged. Earlier incomplete proof copy `/private/tmp/fillable-verify.B7XtaQ`
and all isolated volumes remain preserved. Uploads have no library UI yet; E03.1
is next after protected PR/CI and verified merge. Deployment remains last.

2026-09-06: E03.3 confirmed done through [PR #26](https://github.com/Flippylolz/fillable/pull/26)
at `364d72220f00b58d8ced3195d820b47cf4a8b1d2`; Actions 34040916102 passed both
checks for exact head `6098d681fe27cc9649add77ac34a05cf2d8e4241`. Final evidence is
in the PR body. Main synchronized; E03.1 is underway on `task/e03-1-library`.
Real library/upload UI and authenticated library/profile navigation are implemented,
with preserved drafts, quota/empty/error states, cursor paging and stable retry keys.
Initial frontend verification passes 54 tests above both gates. Browser fixture and
profile navigation checks are updated; fresh Docker and visual verification are next.
A pinned development-only Node type package supports actual File-byte assertions;
no Node backend or runtime dependency was introduced. Download/delete/open actions
and processing jobs remain their own tasks. Deployment remains last.

E03.1 final local verification passed 55 frontend tests, 466/471 lines (98.94%)
and 374/399 branches (93.73%), lint, typing, catalogs, build and raw full-source gate.
Fresh staged checkout `/private/tmp/fillable-verify.iOp4LS` passed 3 development and
14 production browser checks, including real uploads of both kinds, interrupted
request retry, language/draft preservation, reload and source digest checks.
Ukrainian desktop and English mobile screenshots were inspected. An HTTP-only
`randomUUID` failure was fixed using `getRandomValues`; unit coverage now models
that browser capability. Final unit mock also handles the health endpoint's string
URL. Earlier proof copies and all volumes are preserved. See [Library](LIBRARY.md).
Next: protected E03.1 PR, exact-head auto-merge, actual merge verification, then E03.4.

2026-09-06: E03.1 confirmed done through [PR #27](https://github.com/Flippylolz/fillable/pull/27)
at `a5c4721a49a1889ac09de32dcb0a37846deeaf35`; Actions 34043078067 passed checks
and ci-required for exact head `9c3381b1c682ba0ade9ad717a13cf7febf3683d0`.
Main synchronized. User requested a Google Docs-like visual direction and readable
storage units. E03.1b on `task/e03-1b-library-design` implements that requested
follow-up before continuing E03.4. It keeps the functional controls and original
accounting, formats sizes consistently in library/profile, and compacts the shell.
E03.4 is split into E03.4a saved downloads, E03.4b confirmed deletion with durable
cleanup, and E03.4c persisted workspace open/edit entry, each with its own PR.

E03.1b local checks passed: 56 frontend tests, 470/475 lines (98.95%) and
376/401 branches (93.77%), lint, catalogs, typing/build, full-source gate and real
negative-source probe. Fresh index `/private/tmp/fillable-verify.zSyf8a` passed
3 development and 14 production browser checks; English desktop and Ukrainian
mobile layouts were visually inspected. Backend is unchanged from verified PR #27.
All isolated data/volumes preserved. Next: protected follow-up PR and actual merge,
then E03.4a downloads. No deployment work has started.

2026-09-06: E03.1b confirmed done through [PR #28](https://github.com/Flippylolz/fillable/pull/28)
at `aa699b3b23950dbd62e33e7870f0fd22456c469d`; Actions 34043685806 passed both
required checks for head `0e9f2b659463de882749fc3f73618afc655d4910`.
Main synchronized; E03.4a starts on `task/e03-4a-saved-downloads` with authorized,
bounded latest-saved byte downloads and explicit library actions. It creates no
retained file and does not change quota accounting. E03.4b/c remain separate.

E03.4a local verification passed 143 backend and 58 frontend tests. Backend raw
coverage: 1857/1866 lines (99.52%), 543/554 branches (98.01%); frontend:
495/500 lines (99.00%), 392/419 branches (93.56%). Lint, typing, catalogs, build,
full-source gates passed. Both real unimported-source negative probes correctly blocked coverage.
Fresh index `/private/tmp/fillable-verify.K9Q4dP` passed 3 development and 14 production
browser checks, now including real downloads of both kinds with byte equality.
The mobile Ukrainian download action was visually inspected. The added second-version
integration test passed after using the storage service's valid purpose/fingerprint
contract. No application behavior changed after the fresh-index check. All isolated
volumes are preserved. Next: protected E03.4a PR, exact-head auto-merge, verified
merge, then E03.4b confirmed deletion and durable cleanup.

2026-09-06: E03.4a confirmed done through [PR #29](https://github.com/Flippylolz/fillable/pull/29)
at `9bde1d414886096e6737fd494fc88912ceb1ca3a`; Actions 34044435542 passed checks
and ci-required for exact head `ec3209edc6318ea3decbd063de878b6291145322`.
Main synchronized; E03.4b is underway on `task/e03-4b-document-deletion`.
Deletion records durable intent for original/all version files, keeps accounting
charged through cleanup, and exposes pending cleanup in the existing library after
reload. Native confirmation/cancel and retry actions have both translations.
Local application tests pass 147 backend and 62 frontend tests; real browser checks
and coverage probes are being finalized. E03.4c workspace entry follows actual merge.

E03.4b initial final checks passed 147 backend and 62 frontend tests, all four raw
coverage gates and both negative-source probes. Fresh index
`/private/tmp/fillable-verify.lqBkK3` passed 3 development and 14 production browser
checks, including cancellation, both-kind confirmed deletion, exact quota reduction,
deleted download 404 and reload. Mobile English confirmation was visually inspected.
Review added clearing parsed model snapshots when recording deletion intent; the
multi-version integration assertion and final backend checks are rerunning for that
small backend-only change. Browser behavior is unchanged. All volumes preserved.

E03.4b final checks passed: 147 backend tests, 1916/1926 lines (99.48%) and
555/566 branches (98.06%); 62 frontend tests, 518/524 lines (98.85%) and 416/445
branches (93.48%). Both real unimported-source probes blocked below-threshold reports.
Final fresh index `/private/tmp/fillable-verify.uhi77E` passed 3 development and 14
production browser checks, including native modal initial focus, Escape cancellation
and focus return, both-kind deletion, quota and reload checks. Parsed model cleanup
is included in this final checkout. The earlier inspected confirmation layout is
unchanged. Next: individual protected PR and actual merge, then E03.4c. No deployment.

2026-09-06: E03.4b confirmed done through [PR #30](https://github.com/Flippylolz/fillable/pull/30)
at `b058da2f1f2bcbb4ed37f6c7d0d7801464c7d0f6`; Actions 34045437043 passed both
required checks for head `de72ec8320b2dca8d76e07ff66fdfa483ce5f593`.
Main synchronized; E03.4c is underway on `task/e03-4c-workspace-entry`.
The authenticated content endpoint returns one verified saved model/revision; library
open links mount the existing editor with draft-preserving profile/language navigation,
back/forward and logout discard guards. See [Workspace](WORKSPACE.md). E06 save/history
remain explicit outstanding work; current local edits never claim persistence.
Local checks pass 148 backend and 65 frontend tests; frontend async field tests were
fixed to await editor initialization. An initial browser locator matched a hidden
upload option; the scoped workspace locator is in the final fresh-index run.

E03.4c final local gates passed: 148 backend tests, 1943/1953 lines (99.49%) and
561/572 branches (98.08%); 65 frontend tests, 560/566 lines (98.94%) and 484/518
branches (93.44%). Lint, typing, catalogs/build, raw full-source checks and both real
negative-source probes passed. Final fresh index `/private/tmp/fillable-verify.jPFeMA`
passed 3 development and 14 production browser checks, including persisted workspace
opening, linked edits, account language/draft preservation, undo/redo and cancel/confirm
on another resource. Desktop English and mobile Ukrainian workspace layouts were
inspected. Failed initial proof `/private/tmp/fillable-verify.61AMZK` and all volumes
remain preserved. Next: protected E03.4c PR, actual merge, then E03.5 durable processing.
Safe persisted edits, leases/history and autosave remain E06. Deployment stays last.

2026-09-06: E03.4c confirmed done through [PR #31](https://github.com/Flippylolz/fillable/pull/31)
at `4b9c029f1139d46239cc5ab281e7fea0f6a494cb`; Actions 34046414338 passed both
required checks for exact head `5264ea774584fedb89381fdb6319d2c0ea85c121`.
Main synchronized. E03.5 is split into E03.5a durable processing API/outbox/worker
and E03.5b upload intent/library polling, each in its own PR. E03.5a is underway on
`task/e03-5a-durable-processing`; migration, private dispatcher, source/lease fences,
three-attempt recovery and explicit owned APIs are implemented. See [Processing](PROCESSING.md).
The initial processor inspects existing supported controls/structure; E04 discovery
is not claimed. No retained files or quota writes occur during inspection.
Local checks pass 156 backend and 65 frontend tests. Initial fresh Docker proof
`/private/tmp/fillable-verify.trQNef` passed real dispatcher/worker completion before
and after recreation plus all existing browser checks. Review added bounded recovery
for delivery failure before the business claim; final fresh proof is underway.

E03.5a final local checks passed: 156 backend tests, 2182/2197 lines (99.32%) and
609/626 branches (97.28%); 65 frontend tests, 560/566 lines (98.94%) and 484/518
branches (93.44%). Lint, typing, generated API, catalog/build and both raw full-source
gates passed. Both real unimported-source probes blocked below-threshold reports.
Final fresh index `/private/tmp/fillable-verify.KUQm67` passed real dispatcher/forked
worker processing before/after recreation, unchanged saved bytes/quota, 3 development
and 14 production browser checks. All isolated volumes preserved. Next: protected
E03.5a PR and verified merge, then E03.5b upload intent and library status polling.

2026-09-06: E03.5a verified merged in [PR #32](https://github.com/Flippylolz/fillable/pull/32),
commit `312fa274d8801d0685b6749b0ec2a7a4c58d03a0`, exact head
`98c73386a5ab20a02f390a20059b8de8e11175bc`; Actions 34047918000 passed required checks.
E03.5b resumed on `task/e03-5b-processing-status`: upload and job intent commit
atomically, list status reflects the current revision, and localized polling/retry
controls preserve drafts. Backend 157 tests and frontend 71 tests pass; raw coverage
and fresh real-worker/browser verification are being finalized. Next: protected task
PR, actual merge, then E03.6 independent template snapshots. Deployment stays last.

E03.5b final local verification passed: 157 backend tests, raw 2188/2203 lines
(99.32%) and 609/626 branches (97.28%); 71 frontend tests, 584/590 lines
(98.98%) and 511/545 branches (93.76%). Lint, typing, catalogs/build and generated
API checks passed. Both real uncovered-source probes failed below 90% as required.
Fresh index `/private/tmp/fillable-verify.P65paP` passed automatic upload processing
through the real dispatcher/worker before and after recreation, 3 development and
14 production browser tests, including interrupted polling/retry and both upload
kinds reaching inspection completion. English desktop/Ukrainian mobile screenshots
were inspected; readable storage units and the Docs-inspired layout remain intact.
The first fresh run `/private/tmp/fillable-verify.Fvq9tg` stopped on a duplicate test
variable, corrected in the final run. All verification volumes remain preserved.
Next: protected E03.5b PR and verified merge, then E03.6.

2026-09-06: E03.5b verified merged through [PR #33](https://github.com/Flippylolz/fillable/pull/33),
commit `e3e3ab51419090c077c529efa937c002aeaa26da`; Actions 34049142719 passed
`checks` and `ci-required` for exact head `45ef4368485632b458f511497944b69f9922a56f`.
Main synchronized. E03.6 is underway on `task/e03-6-template-copies`: independent
saved-template copies, quota/idempotency enforcement, and workspace navigation.

E03.6 implementation and local unit/integration gates pass. See [Template copies](TEMPLATE_COPIES.md)
for transaction and retry behavior. Fresh Docker/browser verification is next, including
a lost committed response and source deletion with the independent copy still usable.

E03.6 final local gates passed: 163 backend tests, 2253/2268 lines (99.34%) and
620/636 branches (97.48%); 78 frontend tests, 613/620 lines (98.87%) and 547/582
branches (93.99%). Lint, typing, catalogs/build, generated API and raw full-source
checks passed. Both real unimported-source probes failed below 90% as required.
Final fresh index `/private/tmp/fillable-verify.EskYGN` passed 3 development and
14 production browser tests, including committed-copy response loss, idempotent retry,
workspace entry, independent quota and source deletion. Desktop/mobile copy-form
error screenshots inspected. Earlier successful proof `/private/tmp/fillable-verify.hws0Kr`
and all isolated volumes remain preserved. Next: protected E03.6 PR, actual merge,
then E04.1 field/occurrence/candidate/review schemas. Deployment stays E08 last.

2026-09-06: E03.6 verified merged through [PR #34](https://github.com/Flippylolz/fillable/pull/34),
commit `b9cc874f1823917af02056b75c4385a04688591d`; Actions 34050140543 passed both
required checks for exact head `2c3603ab30427488b98e90b43616e2cf8c62b191`.
E03 upload/library task implementations are merged; end-to-end later source edits,
restoration and formal field-schema copies remain cross-epic E04/E06 acceptance.
Main synchronized; E04.1 is underway on `task/e04-1-field-schemas`, defining bounded
field/occurrence/candidate/review records and validation against known revision anchors.

E04.1 local checks passed: 201 backend tests, raw 2423/2438 lines (99.38%) and
692/708 branches (97.74%); 78 frontend tests, 613/620 lines (98.87%) and 547/582
branches (93.99%). Lint, typing, catalog/build and both raw source gates passed.
The new schemas and validator are covered by corpus/native-control, Unicode/split-run,
protected/overlapping range, reference/review/provenance, revision and resource-limit
tests. See [Field schemas](FIELD_SCHEMAS.md). No UI or document transformation changed;
required CI will rerun browser, fresh Docker, rendering and negative-gate checks.
Next: E04.1 protected PR and verified merge, then deterministic extraction in E04.2.
The updated backend real-unimported-source probe passed: its 2423/7640 line report
was rejected below 90% while all 201 tests remained successful. The unchanged frontend
source retains the preceding task's successful negative probe and is checked again by CI.

2026-09-06: E04.1 verified merged through [PR #35](https://github.com/Flippylolz/fillable/pull/35),
commit `7d5b168232e412a89e68b36de8a366143c9b3f9b`; Actions 34051020682 passed both
required checks for exact head `7540087f93419e3d3b53e39b6b61ee4436ad67ff`.
Main synchronized. E04.2 is split into E04.2a deterministic native-control/explicit-token
extraction and E04.2b source-revision result persistence/API integration, each with
its own PR. E04.2a starts on `task/e04-2a-explicit-discovery`. Literal token-shaped text
remains a proposal and is never auto-accepted. E04.3 adds blank rules; E04.4 measures
labeled accuracy; E04.5 implements workspace review actions.

E04.2a local checks pass 208 backend tests, raw 2478/2493 lines (99.40%) and
710/726 branches (97.80%). The detector reproduces all 22 labeled explicit locations
in the Ukrainian corpus plus one permitted, unaccepted token-shaped literal. It
preserves source Unicode/native values, exact-tag groups, protected barriers and
source paragraph order; candidate/value limits fail without truncation. See
[Field discovery](FIELD_DISCOVERY.md). No UI, API wiring or retained-file change is
claimed in this subtask. Next: protected PR/merge, then E04.2b result persistence/API.
Frontend local checks also passed all 78 tests, raw 613/620 lines (98.87%) and
547/582 branches (93.99%), with lint, typing and catalogs/build. The updated backend
negative probe rejected 2478/7827 lines with all 208 tests passing. Required protection
still enforces strict, up-to-date Actions `ci-required`, including administrators.

2026-09-06: E04.2a verified merged through [PR #36](https://github.com/Flippylolz/fillable/pull/36),
commit `043ea4bb4e0f51f7ddaf9f060d662f69b7e08ce3`; Actions 34051985712 passed both
required checks for exact head `ce17f6115831a752ee1db0f94404068cfa14466e`.
Main synchronized. E04.2b is underway on `task/e04-2b-discovery-results`: derived
source-revision result persistence/API, independent copy cloning and deletion cleanup.

E04.2b local backend/frontend checks pass (211/78 tests). The new migration preserves
existing data and refuses destructive result downgrade. Results are published under
revision/attempt/lease fences, cloned independently on completed template copies,
and cleared on source deletion. Typed API artifacts are regenerated. Fresh Docker
verification is next, including durable results after recreation and copied results
after source deletion. Deployment remains last.

E04.2b final local verification passed: 211 backend tests, raw 2536/2551 lines
(99.41%) and 724/740 branches (97.84%); 78 frontend tests, 613/620 lines (98.87%)
and 547/582 branches (93.99%). Lint, typing, generated API, catalogs/build and raw
full-source gates passed. Both real unimported-source probes rejected below-90%
reports. Fresh index `/private/tmp/fillable-verify.WoHOKJ` passed durable discovery
results through the real dispatcher/forked worker before and after recreation,
3 development and 14 production browser tests, including independently cloned
results surviving source deletion and unchanged saved bytes/quota. All isolated
volumes preserved. No review UI is claimed; E04.5 consumes the new owned result API.
Next: protected E04.2b PR and verified merge, then E04.3 conservative blank rules.

2026-09-06: E04.2b verified merged through [PR #37](https://github.com/Flippylolz/fillable/pull/37),
commit `6135ad60934842d0cee4538e3bf9fa3d054cd2d4`; Actions 34053025320 passed both
required checks for exact head `60dd3adf01f8bc1f4b7d0f577b09403322a2fe86`.
Main synchronized. E04.3 starts on `task/e04-3-blank-discovery`: conservative labeled
blank proposals, combined with explicit discovery, never automatically accepted.

E04.3 local verification passed: 218 backend tests, raw 2641/2658 lines (99.36%)
and 781/800 branches (97.63%); 78 frontend tests, 613/620 lines (98.87%) and
547/582 branches (93.99%). Both real unimported-source negative probes passed.
The first frontend run had two editor-readiness failures during concurrent Docker
verification; the complete isolated rerun passed without source changes. Fresh
index `/private/tmp/fillable-verify.FV8Fr6` passed 3 development and 14 production
browser tests and verified 28 durable proposals through the real worker before
and after recreation. All five labeled corpus blanks have exact expected anchors;
ordinary prose, protected controls, ambiguous empty cells and budget limits are
covered. No blank is auto-accepted. Existing volumes preserved. Required protection
remains strict Actions `ci-required`, including administrators. Next: protected
E04.3 PR and verified merge, then E04.4 per-detector accuracy evaluation.


2026-09-06: E04.3 verified merged through [PR #38](https://github.com/Flippylolz/fillable/pull/38),
commit `ff83cec3d4d507639360ea33b3970cf84b14eaec`; Actions 34054416368 passed both
required checks for exact head `b319209b8a11f8f110439893021e848b69325729`.
Main synchronized. E04.4 starts on `task/e04-4-detector-evaluation`: reproducible
per-detector accuracy, exact answer-key location projection and committed report
checked for drift in required backend tests. The v1 source and answer key stay unchanged.

E04.4 local verification passed 229 backend tests: raw 2753/2770 lines (99.39%)
and 831/850 branches (97.76%). All 78 frontend tests passed: 613/620 lines (98.87%)
and 547/582 branches (93.99%). Lint, types, catalogs/build and both raw source gates
passed. The backend real-unimported-source probe rejected 2753/8638 lines while
all 229 tests passed. The evaluator report is compared exactly in required tests;
all 27 positive locations are found, with one permitted unaccepted literal suggestion,
zero incorrect confirmed fields and no inferred auto-acceptance. Projection and
scoring regressions cover native values, Unicode, tabs/breaks, protected text,
repeated text, deliberate misses/misclassification and invalid answer keys.
No UI, DOCX transformation or retained-file behavior changed; required CI reruns
fresh Docker, browsers, independent rendering and all failure probes. Next: protected
E04.4 PR/verified merge, then E04.5 workspace review. Deployment stays last.
The frontend real-unimported-source probe also passed: 613/2231 lines and 547/3802
branches were rejected with all 78 tests passing.


2026-09-06: E04.4 verified merged through [PR #39](https://github.com/Flippylolz/fillable/pull/39),
commit `1f74de722a34c9f774d2d3abe708462c559d4b2a`; Actions 34055321934 passed both
required checks for exact head `04e158be60efa69f3101182e74dac7754d830cb1`.
Main synchronized. E04.5 is split before implementation into E04.5a safe reviewed
label/group DOCX export, E04.5b editor review transactions/location tracking, and
E04.5c localized workspace sidebar integration, each in its own PR. E04.5a begins
on `task/e04-5a-review-export`. E04 remains open until review UI acceptance passes;
retained revision saves remain E06.

E04.5a implements bounded alias/group edits with immutable control identities and
unique IDs for newly grouped controls. Metadata-only changes preserve native control
content/properties, including placeholder display. Corpus and generalized tests cover
explicit grouping with distinct values, same-label independence, original formatting,
legacy metadata, invalid attributes and ambiguous property rejection. Targeted export
regressions pass (22 tests). Full Docker/coverage and rendered/fresh verification follow.

E04.5a final local verification passed: 243 backend tests, raw 2779/2796 lines
(99.39%) and 843/862 branches (97.80%); 78 frontend tests, 613/620 lines (98.87%)
and 547/582 branches (93.99%). Lint, typing, catalogs/build and both raw source gates
passed. The backend negative probe rejected 2779/8706 lines with tests successful.
Fresh index `/private/tmp/fillable-verify.4ekJgq` passed 3 development and 14 production
browser tests, real-worker discovery/persistence, and recreation. The established
independent rendering check passed original byte/pixel identity, three edited pages,
unchanged page two and Ukrainian text. A separate export changing all five native
aliases/group keys rendered pixel-identical to the original on all three pages;
all three images were inspected. These are LibreOffice/Poppler and structural XML
checks; Microsoft Word was not used. All volumes preserved. Next: protected E04.5a
PR/verified merge, then editor review transactions in E04.5b.
The frontend real-unimported-source probe also passed (613/2231 lines, 547/3802
branches rejected; 78 tests successful). Strict required Actions protection is intact.

E04.5a PR #40's first CI run (34056273020) was correctly blocked: the frontend
negative probe reported one failed test, but the old assertion omitted its identity.
All earlier CI steps passed. The probe now prints failing test diagnostics; the
workspace test waits for editor readiness instead of assuming its heading means
mount effects completed. Vitest workers are bounded to two for the small CI runner.
The complete frontend rerun passed all 78 tests with unchanged raw coverage, and
the updated real-source probe passed under a two-CPU Docker limit. No thresholds,
source inclusion or assertions were removed. Required CI will rerun on the updated
PR head before dependent implementation.

2026-09-06: E04.5a verified merged through [PR #40](https://github.com/Flippylolz/fillable/pull/40),
commit `0b9913604b171797b35b022d10e6f79a094793c3`; Actions 34056829570 passed both
required checks for exact head `3c4a310c1ab1b790647ea1c808c9156bb30022d3`, including
the frontend negative probe. Main synchronized. E04.5b starts on
`task/e04-5b-review-transactions`: source-validated proposal mapping, atomic review
transactions and explicit missing locations. Localized sidebar consumption follows
in E04.5c; saved metadata/copy acceptance remains tied to E06 revision persistence.

E04.5b implements source-validated Unicode proposal mapping and atomic acceptance,
dismissal, label/group configuration and navigation. Root review metadata tracks
missing locations through edits and shares editor undo/redo. A new regression exposed
value propagation corrupting undo of conflicting grouped values; history transactions
now restore their exact recorded values. The source-derived 28-proposal editor fixture
is regenerated alongside the model in required CI. See [Working field review](FIELD_REVIEW.md).
Full frontend/backend gates and fresh Docker/browser verification follow.

E04.5b final local checks passed: 90 frontend tests, raw 721/728 lines (99.04%)
and 708/743 branches (95.29%); 243 backend tests, 2779/2796 lines (99.39%) and
843/862 branches (97.80%). Lint, typing, catalogs/build, source-fixture drift and
both raw gates passed. Both real unimported-source probes rejected below-90%
reports with tests successful. Fresh index `/private/tmp/fillable-verify.NeqDjS`
passed 4 development and 14 production browser tests, including exact restoration
of distinct native values through undo/redo and locale switching. Worker results,
retained bytes/quota and recreation passed; all volumes preserved. Independent
LibreOffice/Poppler rendering passed unchanged package/pages, three edited pages,
unchanged page two and Ukrainian text. Strict required Actions protection remains
intact. Next: protected E04.5b PR and verified merge, then E04.5c sidebar/result loading.

2026-09-06: E04.5b verified merged through [PR #41](https://github.com/Flippylolz/fillable/pull/41),
commit `243643cf8011f15d39d1ba244597c6f615732350`; Actions 34058350851 passed both
required checks for exact head `1821b81dcb7d6d48815dce91418ec1d31c7b2d1a`.
Main synchronized. E04.5c starts on `task/e04-5c-workspace-review`: localized review
sidebar, bounded owned-result loading and source revalidation without discarding drafts.

E04.5c implements the collapsible review sidebar, explicit source-checked loading,
bounded polling and manual retry, and discard-confirmed reopening after stale results.
Acceptance, dismissal, label/group settings and navigation share editor history; locale
changes retain unapplied inputs. Review remains an open draft until E06 persistence.
See [Working field review](FIELD_REVIEW.md).

Local checks passed: 101 frontend tests, raw 808/815 lines (99.14%) and 816/851
branches (95.89%); 243 backend tests, 2779/2796 lines (99.39%) and 843/862 branches
(97.80%). Lint, typing, catalogs/build and both raw gates passed. Real unimported-source
probes rejected below-90% reports while all tests passed. Fresh index
`/private/tmp/fillable-verify.o7fkk1` passed 4 development and 16 production browser
checks, actual worker processing, quota/byte invariants and persistent recreation.
The initial browser run exposed an exact-label selector including dropdown options;
using the dropdown's accessible role/name fixed both desktop/mobile checks without
changing application behavior. Ukrainian/English desktop/mobile screenshots were
inspected. Independent LibreOffice/Poppler rendering passed no-edit byte/pixel identity,
three edited pages, unchanged page two and Ukrainian text; Microsoft Word was not used.
All volumes preserved. Strict Actions `ci-required` protection and administrator
enforcement remain enabled. Next: E04.5c PR/verified merge, then E05.1 adapter integration.

2026-09-06: E04.5c verified merged through [PR #42](https://github.com/Flippylolz/fillable/pull/42),
commit `3f631c1c72dea32df837d87918969c2cc8137494`; Actions 34060992071 passed both
required checks for exact head `6331ad2a57c228e6c6f42b77c1ecc0a21aa8ca18`.
Main synchronized. E05.1 starts on `task/e05-1-editor-adapter`: isolate mounted editor
operations behind a narrow adapter, preserving shared workspace behavior and source
snapshots. E06 retains responsibility for production revision saves and history.

E05.1 isolates the editor lifecycle and operations behind `mountEditor`. React consumes
field summaries and review presentation; no raw view or transaction reaches its controls.
Inputs, exported models and callback/review payloads are detached from live state. A local
monotonic change counter excludes selection, initial discovery and interface localization.
The same adapter supplies production workspaces and the Python DOCX round-trip proof.
See [Workspace](WORKSPACE.md). Production retained saves remain E06.

Local verification passed: 103 frontend tests, raw 801/806 lines (99.38%) and 816/847
branches (96.34%); 243 backend tests, 2779/2796 lines (99.39%) and 843/862 branches
(97.80%). Lint, typing, catalogs/build and independent raw gates passed. Both real
unimported-source probes rejected below-90% reports with all tests passing. Fresh index
`/private/tmp/fillable-verify.5nW9Lx` passed 4 development and 16 production browser
checks, worker discovery, retained byte/quota invariants and persistent recreation.
Independent LibreOffice/Poppler checks passed no-edit byte/pixel identity, three edited
pages, unchanged page two and Ukrainian text. Microsoft Word was not used; all volumes
preserved. Next: protected E05.1 PR/verified merge, then E05.2 sidebar validation/navigation.

2026-09-06: E05.1 verified merged through [PR #43](https://github.com/Flippylolz/fillable/pull/43),
commit `35ad66cc43583c6adb3f640b51c55001d06fa99b`; Actions 34061805890 passed both
required checks for exact head `b55c617ae973dc8b95d310e51969c8b21eb18afa`.
Main synchronized. E05.2 starts on `task/e05-2-sidebar-navigation`: accessible occurrence
navigation, explicit active-field status and retained review validation/conflict feedback.
Long/multiline value synchronization continues in E05.3; manual/missing controls in E05.4.

E05.2 adds occurrence-specific sidebar cards, previous/next navigation with explicit
boundaries, localized selected-position status and visible/accessible active markers.
Repeated values remain separately inspectable with conflict feedback. Empty-state guidance
and review error associations are localized; navigation and locale changes do not dirty
content. See [Workspace](WORKSPACE.md).

Local verification passed: 105 frontend tests, raw 810/815 lines (99.39%) and 834/865
branches (96.42%); 243 backend tests, 2779/2796 lines (99.39%) and 843/862 branches
(97.80%). Lint, typing, catalogs/build, independent raw gates and both real unimported-
source negative probes passed. Fresh index `/private/tmp/fillable-verify.K48uup` passed
4 development and 16 production browser checks, including real occurrence navigation
without dirtying the source, plus worker/persistence/byte/quota checks. Ukrainian/English
sidebar screenshots were inspected on desktop and mobile. Independent LibreOffice/Poppler
checks passed no-edit byte/pixel identity, three edited pages, unchanged page two and
Ukrainian text. Microsoft Word was not used; all volumes preserved. Next: protected
E05.2 PR/verified merge, then E05.3 value synchronization and long/multiline input.

2026-09-07: E05.2 verified merged through [PR #44](https://github.com/Flippylolz/fillable/pull/44),
commit `72656eddb9e6d67dfe2238acffd3ef7b35f164c7`; Actions 34062557010 passed both
required checks for exact head `7d61d46a74780fd806a8cc41d7290d003b1473cb`.
Main synchronized. E05.3 starts on `task/e05-3-field-values`: multiline/long Unicode
value synchronization, retained invalid drafts with feedback, and actual export/reopen
coverage. Production saved writes still belong to E06.

E05.3 implements multiline textareas and field-value validation without a second value
store. Invalid values remain in the editable draft with associated localized errors and
can be corrected or undone. Adapter snapshots expose field-value validity; the opt-in
proof blocks invalid exports. The first native browser check exposed multiline insertion
replacing the control DOM before parsing. Scoped beforeinput/paste handlers now retain
control identity and linked values through editor transactions. Full native rerun passed.

The old QA renderer overlapped multiline native values despite exact DOCX reopening.
Boolean/run variants did not fix it; no exporter workaround was retained. Official
LibreOffice documentation places multiline-control support at 24.2. QA now pins Writer
25.2.3, Poppler 25.03, Liberation 2.1.5 and Noto Color Emoji 2.051 on the verified Trixie
image. The same exported bytes render correctly. Required rendering now checks five
multiline pages, exact repeated Ukrainian/astral text and separate rendered lines for
both native occurrences, alongside the original three-page identity regressions.
See [Editor feasibility](EDITOR_FEASIBILITY.md); the application image is unaffected.

Final local checks passed: 109 frontend tests, raw 834/839 lines (99.40%) and 871/902
branches (96.56%); 243 backend tests, 2779/2796 lines (99.39%) and 843/862 branches
(97.80%). Lint, typing, catalogs/build, raw gates and both real unimported-source probes
passed. Fresh index `/private/tmp/fillable-verify.1olOLr` passed 5 development and 16
production browser checks, actual export/reopen, worker processing, byte/quota invariants
and persistent recreation. UK/EN multiline controls were inspected on desktop/mobile.
The updated independent renderer passed all checks against those browser outputs; all
five multiline and all six original/edited pages were inspected. Source justification,
explicit breaks and the resulting pagination remain intact. Microsoft Word was not used.
All volumes preserved. Next: protected E05.3 PR/verified merge, then E05.4 manual/missing
field integration; E06 still owns production retained saves and revision history.

2026-09-07: E05.3 verified merged through [PR #45](https://github.com/Flippylolz/fillable/pull/45),
commit `db79591a2e7fb50a5d94a2273b93e4810274613d`; Actions 34064122825 passed both
required checks for exact head `61c9c5fc442718d4c772dc401637b1b90b171113`.
Main synchronized. E05.4 starts on `task/e05-4-manual-fields`: bounded manual creation
and explicit missing/moved control records in the existing review history. Local tracking
before discovery is explicitly unbound; it cannot replace the saved source's result.

E05.4 adds bounded manual creation and accepted local records tied to immutable control
identities. Movement retains the record, removal preserves source text and marks its
location missing, and undo restores it. Duplicate identities cannot be focused or
removed arbitrarily. Invalid labels/selection/capacity leave the draft intact with
localized feedback. Tracking before discovery remains explicitly unbound and refuses
late attachment. See [Working field review](FIELD_REVIEW.md).

Local verification passed: 113 frontend tests, raw 851/855 lines (99.53%) and 894/926
branches (96.54%); 243 backend tests, 2779/2796 lines (99.39%) and 843/862 branches
(97.80%). Lint, typing, catalogs/build, independent raw gates and both actual unimported-
source negative probes passed. Fresh index `/private/tmp/fillable-verify.YX8Lmp` passed
5 development and 16 production browser checks, including manual creation/removal/undo
and actual export/reopen, plus real worker/persistence/byte/quota checks. UK/EN production
workspace and manual proof screenshots were inspected. Independent LibreOffice/Poppler
verification passed unchanged byte/pixel identity, three edited pages with unchanged
page two, and five multiline pages with exact repeated Ukrainian/astral text; an edited
page was visually inspected. Microsoft Word was not used; all volumes preserved.
Next: protected E05.4 PR/verified merge, then E05.5 keyboard/composition/history checks.

2026-09-07: E05.4 verified merged through [PR #46](https://github.com/Flippylolz/fillable/pull/46),
commit `85c4534c76ddf2ec202cfe0d60ec725347302f46`; Actions 34065403103 passed required
checks for head `a96d15fba5034fa5470becbf5ba7455e354cec4b`.

E02.3a is a bounded corrective task discovered during E05.5 verification. The concurrent
copy regression returned two busy responses: an active retry could acquire the operation
lock before its creating writer, briefly preventing the writer from starting. Acceptance:
active/aborted retries do not acquire that lock, a coordinated real PostgreSQL regression
proves the creator completes with one allocation, and committed replays retain locking
and exact idempotent results. Dedicated branch `task/e02-3a-retry-lock` starts from merged
E05.4. E05.5 editor changes remain isolated on `task/e05-5-editor-input` and resume after
this correction merges. No retained format, quota, lease or recovery policy is relaxed.

E02.3a local verification passed: 244 backend tests, raw 2778/2796 lines (99.36%)
and 843/862 branches (97.80%); 113 frontend tests, 851/855 lines (99.53%) and
894/926 branches (96.54%). Lint, typing, catalogs/build, raw gates and both real
unimported-source negative probes passed. The deterministic test pauses a writer
after reservation and verifies a retry takes no filesystem lock or extra allocation,
then the writer and committed replay succeed with exact accounting. Fresh index
`/private/tmp/fillable-verify.P3qqpS` passed 5 development and 16 production browser
checks, real worker processing and persistent byte/quota invariants. Independent
LibreOffice/Poppler regression checks passed. No frontend appearance, DOCX format,
server service or persistent volume was changed. Next: individual protected PR,
verified merge, then synchronize the unfinished E05.5 editor branch.

2026-09-07: E02.3a verified merged through [PR #47](https://github.com/Flippylolz/fillable/pull/47),
commit `572c3cc1399c3f989e2d0d504001ff9d6fdc47ce`; Actions 34066439392 passed both
required checks for exact head `52711fe98561465947572f1391b98551a2f12c46`. The
E05.5 branch synchronized with this correction, preserving its editor changes.
E05.5 continues on `task/e05-5-editor-input`: native keyboard/composition/repeated-field
history checks and idempotent sidebar updates that cannot create feedback loops.

E05.5 native Chromium tests exposed duplicated IME candidates, root-review redraws,
fast commits unwrapping a control, and stale keyboard selections. The adapter now lets
the native editor own composition, accumulates its exact steps, then synchronizes linked
values/review using the native history identity after settlement. It restores an unwrapped
control only at its mapped editable text range, retaining identity/source formatting.
Enter/Shift-Enter and selection-collapse commands are scoped to fields; identical sidebar
updates do not dispatch. Snapshots expose pending composition and the proof waits before
exporting. Discovery cannot attach during composition. See [Workspace](WORKSPACE.md).

Final local verification passed: 118 frontend tests, raw 907/912 lines (99.45%) and
950/988 branches (96.15%); 244 backend tests, 2778/2796 lines (99.36%) and 843/862
branches (97.80%). Lint, typing, catalogs/build, raw gates and both actual unimported-
source probes passed. Final fresh index `/private/tmp/fillable-verify.5WVKWT` passed
7 development and 16 production browser checks, actual keyboard/IME/cancellation/undo/
reopen, worker processing and persistent byte/quota checks. Independent LibreOffice/
Poppler passed the standard three/five-page regressions and rendered both native-input
exports with both expected Ukrainian values; the fast-commit first page was inspected.
This verifies Chromium's native IME protocol, not every physical OS input method or
Microsoft Word. All volumes preserved. Next: protected E05.5 PR/verified merge, then
E05.6 workspace controls and the remaining E06 persistence integration.

2026-09-07: E05.5 verified merged through [PR #48](https://github.com/Flippylolz/fillable/pull/48),
commit `ce0bd2afda9e7cc21d140d46fdad9acaa1140c29`; Actions 34067380184 passed required
checks for exact head `93eb061b53ed0a8224168342e70b1c7693a6ae09`. Main synchronized.
E05.6 is split above to keep settings delivery bounded while save/history controls depend
on real E06 operations. E05.6a starts on `task/e05-6a-workspace-settings`: rename updates
owned resource metadata only, with revision/title conflict checks and idempotent retry;
zoom/highlight remain presentation state. Back/locale navigation preserves editor drafts.

E05.6a local verification passed: 253 backend tests, raw 2819/2837 lines (99.37%)
and 853/872 branches (97.82%); 123 frontend tests, 953/959 lines (99.37%) and
1005/1045 branches (96.17%). Lint, typing, catalogs/build, generated API, raw gates
and both actual unimported-source negative probes passed. Fresh index
`/private/tmp/fillable-verify.ha3XLs` passed 7 development and 16 production browser
checks, including a committed rename with a lost response, safe retry, retained
editor/upload drafts and both-language desktop/mobile settings. Settings screenshots
were inspected. LibreOffice/Poppler passed identical no-edit pages, three edited pages
and five multiline pages with repeated Ukrainian/astral text. Microsoft Word was not
run. Actual main protection still requires strict Actions `ci-required`, including
administrators. Next: protected task PR and verified merge, then E06.1 editing leases;
E05.6b waits for real save/history operations. Deployment remains E08, last.

E05.6a [PR #49](https://github.com/Flippylolz/fillable/pull/49) is in review with
protected squash auto-merge. Initial Actions 34069010601 passed browser/persistence
and backend checks but caught a frontend test mounting race: the settings summary
rendered before the editor effect. The helper now awaits the actual editable textbox
before interacting. No application behavior or coverage policy was changed. Revalidate
frontend and its negative probe, push the correction, then follow the new exact head
through required CI and actual merge before E06 implementation.
The corrected helper passed all 123 frontend tests, lint/catalog/build and raw coverage
at unchanged 953/959 lines and 1005/1045 branches. The real unimported-source probe
also passed with 123 tests and correctly rejected 953/3192 lines, 1005/5509 branches.
Existing full fresh/browser/DOCX evidence remains applicable to unchanged app code.

2026-09-07: E05.6a verified merged through [PR #49](https://github.com/Flippylolz/fillable/pull/49),
commit `2de77d51280a9b943894e94491ff1e1ecfb5271f`; Actions 34069561355 passed both
required checks for exact head `2a4454f99bf7ad96825b86c53f0813773739a3e2`. Main synchronized.
E06.1 is split above before implementation. E06.1a starts on `task/e06-1a-editing-leases`;
workspace integration follows in E06.1b, and actual save enforcement in E06.2.

E06.1a local verification passed: 263 backend tests, raw 2909/2927 lines (99.39%)
and 873/892 branches (97.87%); 123 frontend tests, 953/959 lines (99.37%) and
1005/1045 branches (96.17%). Lint, typing, catalogs/build, generated API, raw gates
and both actual unimported-source probes passed. Real PostgreSQL tests cover tab
competition, session identity/revocation/expiry, generation-safe delayed release,
revision changes, ownership/CSRF, no quota/file effects, deletion, schema constraints
and guarded downgrade/upgrade. Fresh index `/private/tmp/fillable-verify.ds4WSg`
passed 7 development and 16 production browser checks, worker processing, byte and
quota preservation after recreation. Independent LibreOffice/Poppler regression
checks passed; no Microsoft Word run or new workspace lease UI is claimed.
Main protection verified strict Actions `ci-required` with administrator enforcement.
Next: individual E06.1a PR and verified merge, then E06.1b mounted-editor lease flow.

2026-09-07: E06.1a verified merged through [PR #50](https://github.com/Flippylolz/fillable/pull/50),
commit `e2038f3aea05156fc2d851fe1dee293ac956de53`; Actions 34070595270 passed both
required checks for exact head `856ca4f2c290df6a30153642853311e7969013d9`. Main synchronized.
E06.1b starts on `task/e06-1b-workspace-lease`: acquire/renew, synchronous expiry
checks at mutation boundaries, retained-draft pause/retry and two-tab browser checks.

E06.1b local verification passed: 130 frontend tests, raw 1018/1026 lines (99.22%)
and 1087/1141 branches (95.27%); 263 backend tests, 2909/2927 lines (99.39%) and
873/892 branches (97.87%). Lint, typing, catalogs/build, raw gates and both actual
unimported-source probes passed. Fresh HTTP checks exposed unavailable randomUUID;
client identity now uses the existing getRandomValues helper and a unit regression
omits randomUUID. The browser invariant assertion excludes only changing processing
status; desktop/mobile use independent synthetic accounts to isolate language state.
Final fresh index `/private/tmp/fillable-verify.2MQmoW` passed 7 development and 18
production browser checks, including two-tab exclusion, lost access during native
IME composition, retained draft/history, same editor after reacquisition and language
change, plus saved-content/quota invariants. Desktop/mobile Ukrainian/English paused
screenshots were inspected. LibreOffice/Poppler regression checks passed; Microsoft
Word was not run. Strict main Actions `ci-required` and administrator enforcement
were verified. Next: individual E06.1b protected PR and verified merge, then the bounded
E06.2 save contract/storage/UI work. Deployment remains E08, last.

2026-09-07: E06.1b verified merged through [PR #51](https://github.com/Flippylolz/fillable/pull/51),
commit `fcffbdf424ee8cbe7bb61b212a3fdf33153bfc08`; Actions 34072141436 passed both
required checks for exact head `4819cbd75c23c835bfa01a1c4cb56f1b8ff25634`. Main synchronized.
E06.2 is split above before implementation to validate metadata and edited-copy
identity before exposing persisted saves. E06.2a starts on
`task/e06-2a-working-review-contract`; no save or deployment is claimed yet.

E06.2a local verification passed: 271 backend tests, raw 3105/3126 lines (99.33%)
and 970/992 branches (97.78%); 131 frontend tests, 1018/1026 lines (99.22%) and
1087/1141 branches (95.27%). Lint, typing, catalogs/build, raw gates and both actual
unimported-source probes passed. The shared golden fixture is generated by real
editor transactions; normal frontend tests compare it without updating, and backend
tests validate the same representation, export against the immutable original and
reopen the Ukrainian/multiline fields. Invalid/stale/overlapping/protected/surrogate
anchors, duplicate or mismatched controls and traversal budgets are checked.
Fresh index `/private/tmp/fillable-verify.udW4eV` passed 7 development and 18 production
browser checks plus worker/persistence/quota invariants. Independent LibreOffice/Poppler
standard regressions passed. The working fixture rendered three inspected pages with
both astral characters and Ukrainian text; pages two and three are pixel-identical
to the original. Microsoft Word was not run. Actual strict Actions `ci-required` and
administrator enforcement were verified. Next: individual E06.2a PR and verified
merge, then E06.2b edited-copy rebasing. No save API or deployment is claimed yet.

E06.2a PR #52 review corrected native fields with empty aliases: discovery's fallback
display label must not become working control metadata. The new regression passed
with all 132 frontend tests and unchanged raw coverage (1018/1026 lines, 1087/1141
branches); the real unimported-source probe also passed. Fresh index
`/private/tmp/fillable-verify.k3EPB4` passed 7 development and 18 production browser
checks, persistence invariants and LibreOffice/Poppler regressions. Backend code and
shared fixture are unchanged from the verified 271-test run above. Auto-merge was
disabled before this correction; re-arm only for the updated head after pushing.
Next: verify required CI and actual PR #52 merge, then E06.2b.

2026-09-07: E06.2a verified merged through [PR #52](https://github.com/Flippylolz/fillable/pull/52),
commit `236a0aa8fc5499b382d115933e5cdf6ce65e9248`; Actions 34074851751 passed checks
and ci-required for head `0b6fa53aa74e4698504c4fde579c9c35de0fdc2d`. Main synchronized.
E06.2b starts on `task/e06-2b-edited-copy-rebase`, implementing the documented
structural correspondence and independent-copy review contract before save writes.

E06.2b local verification passed: 287 backend tests, raw 3218/3239 lines (99.35%)
and 1018/1040 branches (97.88%); 132 frontend tests, 1018/1026 lines (99.22%) and
1087/1141 branches (95.27%). Lint, typing, catalogs/build, raw coverage gates and
both real unimported-source failure probes passed. Tests cover the shared real-editor
fixture, source-location/grouping-key rebasing, sticky missing-control collisions,
run segmentation/formatting, structural mismatch rejection and source non-mutation.
Actual owner/storage API tests verify edited-template copy, completed discovery
rebinding, exact quota/retry behavior and independence after source deletion.
Fresh index `/private/tmp/fillable-verify.C1IjAq` passed 7 development and 18 production
browser checks, worker/persistence/quota invariants and LibreOffice/Poppler regressions.
The independent copied fixture re-export is byte-identical to the previously inspected
three-page working fixture. Microsoft Word was not run. Strict Actions ci-required
and administrator enforcement were verified. Next: individual E06.2b PR, exact-head
auto-merge and verified completion, then E06.2c atomic save storage. Deployment is last.

2026-09-07: E06.2b verified merged through [PR #53](https://github.com/Flippylolz/fillable/pull/53),
commit `8576bfd63d7981cab8e16918f2daa41b02222900`; Actions 34076087578 passed checks
and ci-required for exact head `428bd944daca88317c5e4958e7dd935e3e7b3a8e`. Main synchronized.
E06.2c starts on `task/e06-2c-atomic-saves`: paired version review, immutable-original
export, owner/revision/lease-fenced quota writes, exact replay result and stored-model
worker discovery. Manual save UI follows separately in E06.2d.

E06.2c local verification passed: 310 backend tests, raw 3353/3375 lines (99.35%)
and 1033/1056 branches (97.82%); 132 frontend tests, 1018/1026 lines (99.22%) and
1087/1141 branches (95.27%). Lint, typing, generated OpenAPI/client, catalogs/build,
raw gates and both real unimported-source failure probes passed. Integration tests
cover atomic paired revisions, source-original preservation, subsequent edits, worker
anchors, copies, exact replay after advancement/lost commit response, disk/quota
failures, concurrency, lease/revision/deletion/revocation fences and migration/data
guards. Final review added rejection of anonymous sessions before the bounded body
read; its regression and final backend/probe runs passed.
Fresh final index `fillable-verify.h3jB9o` under the system temporary directory passed
7 development and 20 production browser tests, worker/persistence/quota checks and
LibreOffice/Poppler regression. The new desktop/mobile browser tests saved through
nginx, replayed a valid JSON body above the former 24 MiB limit, and reopened matching
manual/review fields in the editor. Actual saved downloads are byte-identical to the
previously inspected three-page working fixture; reopened desktop/mobile screenshots
were inspected. Microsoft Word was not run. Actual strict Actions ci-required and
administrator enforcement were verified. Next: E06.2c individual PR/auto-merge and
verified merge, then E06.2d manual-save UI with exact local-revision acknowledgment.
Deployment remains E08, last; existing services and volumes are preserved.

E06.2c PR #54 final review binds null-origin native/manual review to its first saved
source, retaining that origin on subsequent saves without mutating the request or
editor undo history. A real two-save manual-field regression and desktop/mobile
reopen checks cover it. Final backend verification: 311 tests, raw 3355/3377 lines
(99.35%) and 1035/1058 branches (97.83%); the real unimported-source probe passed
by blocking 3355/10353 lines. Frontend application coverage remains the measured
132 tests, 1018/1026 lines (99.22%), 1087/1141 branches (95.27%).
Fresh final index `fillable-verify.q6vaJu` passed 7 development and 22 production
browser checks plus worker/persistence/recreation. The new test scopes processing
status to the visible workspace and waits for the real worker; an earlier locator
incorrectly matched the hidden library. The development selection assertion retains
its exact selected text, uses normal key intervals and waits for browser selection;
five isolated repeats and the full fresh suite passed. Both downloaded saved DOCX
artifacts exactly match the previously inspected working fixture. Initial PR head
`e7a4b81d2222026653bb876963afffa0344db20c` passed Actions 34090517903; auto-merge was
disabled for this correction. Final LibreOffice/Poppler regression passed: no-edit
bytes/pages identical, three edited pages with unchanged page two, five multiline
pages with exact Ukrainian/astral text. Microsoft Word was not run. Next: push the
correction, reverify strict protection, arm exact-head auto-merge and verify actual
merge before E06.2d. No deployment has started.

PR #54 Actions 34093550128 correctly blocked merge: the fresh mobile library test
matched two alerts because its injected processing failure could target another
retained document from earlier browser cases. The correction captures its own
uploaded template before fulfilling the response, scopes the processing failure to
that exact resource and checks the upload form's alert. Required assertions and
zero retries remain unchanged. Final fresh index `fillable-verify.k0Fd9w` passed
7 development and 22 production tests with persistence/worker/recreation checks.
Application source and measured coverage are unchanged from the preceding run;
DOCX render verification remains the passed q6vaJu evidence. Next: verified CI and
actual merge for this corrected PR head, then E06.2d.

2026-09-07: E06.2c verified merged through [PR #54](https://github.com/Flippylolz/fillable/pull/54),
commit `fef906636106df8e32f99c141af9d7448c285726`; Actions 34094472364 passed checks
and ci-required for exact head `b73ce913fdeb8801ccc19f2c1a828c335b53bee1`. Main synchronized.
E06.2d starts on `task/e06-2d-manual-save`: exact local revision acknowledgment,
immutable uncertain retries, stable tab lease identity, settled input/field checks,
retained editor history, proposed title and recoverable failure/reopen behavior.

E06.2d local verification passed: 311 backend tests, raw 3355/3377 lines (99.35%)
and 1035/1058 branches (97.83%); 153 frontend tests, 1083/1091 lines (99.27%) and
1190/1243 branches (95.74%). Lint/type/catalog/build/raw gates passed; real uncovered
source probes blocked backend 3355/10353 and frontend 1083/3553 lines, 1190/6165
branches while all tests passed. The final adapter regression also verifies that
acknowledgment leaves snapshot, revision and undo unchanged.
Fresh index `fillable-verify.LRbyhe` passed 7 development and 26 production browser
checks with worker/persistence/recreation. New desktop/mobile flows cover early
manual fields, exact acknowledgment with later edits, pending title, subsequent save
with stable tab identity, undo/redo, saved reopen and matching review. Native CDP
composition prevents new saves; a real committed save with an aborted response
replays exactly after old-revision renewal pauses access. Later draft and locale
survive. Injected quota failure retains input and a subsequent real save succeeds;
actual quota/disk enforcement remains covered by PostgreSQL/storage tests.
Both actual saved downloads reproduce exact bytes from their paired model/review
and immutable original, pass structural correspondence and retain manual provenance.
LibreOffice/Poppler renders each as three pages with page two pixel-identical to the
original and both repeated Ukrainian/astral values preserved. Changed pages and
Ukrainian desktop/mobile UI plus English quota error were visually inspected. Standard
no-edit/edited/multiline regression also passed. Microsoft Word was not run.
Next: individual E06.2d PR, actual strict gate verification, exact-head auto-merge and
verified merge. Then split history API/download/restore/UI dependencies before their
implementation. Autosave/history remain unfinished; E08 deployment stays last.

PR #55 initial Actions 34097000657 blocked merge at browser setup. Trace inspection
confirmed overlapping initial session GETs (both set cookies) before the new test's
API login returned 403. Its helper now waits for the login form, matching established
API-assisted test setup and preserving the real CSRF checks. Final fresh index
`fillable-verify.5uLD76` passed all 7 development and 26 production browser tests with
worker/persistence/recreation. Application code/coverage and inspected DOCX render
artifacts remain unchanged. Next: push this test correction and verify exact-head
required CI and actual PR #55 merge before E06.3a.

Final PR #55 review corrected inherited upload wording for in-progress, aborted and
invalid-document save failures. Both catalogs now describe the save/draft action;
real frontend checks passed 154 tests and the raw gate remains 1083/1091 lines
(99.27%), 1190/1243 branches (95.74%). The actual uncovered-source probe again
blocked 1083/3553 lines and 1190/6165 branches with all 154 tests passing. The change
is message presentation only; existing fresh browser and rendered DOCX evidence
remains applicable. Auto-merge was disabled while verifying the correction and will
be rearmed for its exact commit under the strict required gate.

2026-09-07: E06.2d verified merged through [PR #55](https://github.com/Flippylolz/fillable/pull/55),
commit `1602ea40382d9261892cbcf755b78cd6ad4a6258`; Actions 34098604978 passed checks
and ci-required for exact head `620848ed6b9fb1ac2d3f24c5e085d0dc4b9a6542`. Main synchronized.
E06.3 is split above before implementation: E06.3a list/preview API, then E06.4
historical download, E06.6 restore API, and E06.3b complete history UI. Each receives
its own PR and verified merge. E06.3a begins on `task/e06-3a-history-api`. Preview
reads the selected saved model/review pair through the verified file reader, consumes
no retained space and never changes the current revision or editing lease.
Read-only acceptance review also identified two later E07 items: in-place expired
session reauthentication must preserve same-owner drafts and isolate different
accounts; unexpected server logging needs content-free handling beyond sanitized
API response bodies. Record bounded E07 task splits before implementing those fixes.

E06.3a local verification passed: 322 backend tests, raw 3435/3457 lines (99.36%)
and 1049/1072 branches (97.85%); 154 frontend tests, 1083/1091 lines (99.27%) and
1190/1243 branches (95.74%). Lint/type/catalog/build/generated contracts/raw gates
passed. Actual unimported-source probes blocked backend 3435/10605 lines and frontend
1083/3553 lines, 1190/6165 branches with all tests passing. Real PostgreSQL tests
cover coherent listing during a committed save, exact original/edited/review-only
pairs, owner/resource/version isolation, bounded/empty pages, corruption/admission,
content-free failures and unchanged quota/current/lease state.
Fresh index `fillable-verify.qXgcsj` passed 7 development and 26 production browser
tests, hot reload and worker/persistence/recreation. This task changes read-only APIs;
no new historical UI, export transformation or Word compatibility is claimed. Next:
individual E06.3a PR, actual strict gate verification and exact-head auto-merge,
verified merge, then E06.4 exact historical downloads. Deployment remains E08, last.


2026-09-07: E06.3a verified merged through [PR #56](https://github.com/Flippylolz/fillable/pull/56),
merge `a470a2a4f5f91e0ff8fe0045cda4f3e9368c27b5`; Actions 34100793853 passed
`checks` and `ci-required` for exact head `fcca84036cd22d40a77bf0b08f9bcb7c3972fc4b`.
E06.4 begins on `task/e06-4-historical-downloads`: exact retained revision bytes,
owned bounded verified reads and reopening evidence. Current downloads stay current;
selected downloads never resolve to a newer revision. No new retained output is
created by a download; existing quota-enforced saves supply the immutable bytes.
Restore allocation remains the separately planned E06.6 task, followed by E06.3b UI.

E06.4 local verification passed: 328 backend tests; raw 3463/3485 lines (99.37%)
and 1059/1082 branches (97.87%); Ruff, mypy and gate contracts passed. Frontend
154 tests, lint/catalog/type/build and raw source gate passed: 1083/1091 lines
(99.27%) and 1190/1243 branches (95.74%). Real unimported-source negative probes
passed their tests and blocked both stacks below 90%. OpenAPI/TypeScript regenerated.
Fresh staged checkout `fillable-verify.ITc6zu`, project `fillable-verify-84175`,
passed 7 development and 26 production browser tests, reload, worker processing,
persistence/recreation and production static serving; all volumes preserved.
Desktop/mobile gateway tests fetched exact original bytes after a newer save,
compared selected saved bytes with current and reopened matching reviewed content.
Backend reopening also verifies original equality, edited/review-only correspondence,
owner/admin isolation, bounded/corrupt reads and unchanged lease/current/quota state.
No new DOCX transform or layout change; Microsoft Word is not claimed. Actual strict
Actions `ci-required` protection including administrators was rechecked. Next:
individual PR/auto-merge and actual merged-state verification, then E06.6 restore.
E06.3b history UI and E06.5/E06.7 remain unfinished. E08 deployment stays last.


2026-09-07: E06.4 verified merged through [PR #57](https://github.com/Flippylolz/fillable/pull/57),
merge `017d6599f10bb03caf1aad8df81a2f345996262b`; Actions 34102641718 passed
`checks` and `ci-required` for exact head `9a8c98756e3aad133e3f229d98910be2bbd24c47`.
E06.6 starts on `task/e06-6-restore-revisions`: selected immutable bytes and matching
review as a new quota-enforced revision; shared save/restore final transaction fences,
exact retry identity and parent/restored-from provenance. Migration backfills parents
and guards destructive downgrade. Unsaved draft confirmation/recovery UI follows in
E06.3b after this API merges; no premature discard or history pruning is introduced.

E06.6 local verification passed: 353 backend tests, raw 3559/3582 lines (99.36%)
and 1074/1098 branches (97.81%); Ruff, mypy and gate contracts passed. Frontend
154 tests, lint/catalog/type/build and raw source gate passed: 1083/1091 lines
(99.27%) and 1190/1243 branches (95.74%). Both real unimported-source negative
probes passed their behavior suites and blocked below 90%. OpenAPI/TypeScript regenerated.
Fresh staged application checkout `fillable-verify.wBPYqa`, project `fillable-verify-87057`,
passed 7 development and 28 production browser tests, hot reload, worker, static
assets and persistence/recreation; all volumes preserved. The final two backend-only
race/deletion regression tests were added afterward and passed in the 353-test suite.
Both desktop/mobile actual restored downloads are 595214 bytes, SHA-256
`e6dbca45b21efbc2c83536f8a6832d9074ea656edf59a68bf0fedf276a4d9fed`, identical to the
previously independently rendered reviewed DOCX. Browser reopening and captured
workspace views were inspected. The standard independent renderer also passed
no-edit byte/pixel equality, edited three-page/unchanged-page checks and five-page
multiline Ukrainian/astral checks. Microsoft Word itself is not claimed.
Real PostgreSQL checks cover original/reviewed/review-only restore, exact late replay,
concurrent restore/restore and save/restore, stale authority, late quota/selection
removal, corrupt data, disk failure, deleted-result replay, worker correspondence,
copy independence, parent backfill, scoped FKs and guarded downgrade.
Actual strict `ci-required` protection including administrators was verified. Next:
individual E06.6 PR, exact-head auto-merge and verified merge, then E06.3b complete
history UI with explicit draft handling. Retention/autosave and E07 remain; deployment
is E08, last, preserving unrelated services.

2026-09-07: E06.6 verified merged through [PR #58](https://github.com/Flippylolz/fillable/pull/58),
merge `042b5d0d35c1da5598d103fb775efde95787d1a8`; Actions 34104984875 passed
`checks` and `ci-required` for exact head `597cf7f903273099632e0925265c444a33797575`.
E06.3b starts on `task/e06-3b-history-panel`: complete in-workspace history, localized
revision metadata, separate read-only preview, exact download, restore confirmation
and recovery. The live draft stays mounted while viewing history and is replaced
only after restore acknowledgment and loading its exact current pair. Unknown
requests survive mode/locale changes and retry their original selected version/key.

E06.3b local verification passed: 191 frontend tests, lint/catalog/type/build and raw
coverage 1221/1231 lines (99.19%), 1370/1435 branches (95.47%). Backend 353 tests,
Ruff/mypy/gate contracts, raw 3559/3582 lines (99.36%), 1074/1098 branches (97.81%).
Both real unimported-source probes passed their suites and blocked below 90%.
Fresh staged application `fillable-verify.jp82Fn`, project `fillable-verify-91337`,
passed 7 development and 34 production browser tests, hot reload, worker, static
assets and persistence/recreation; all volumes preserved. A final preview-conflict
copy correction then passed all 191 frontend tests and the negative coverage probe.
Six new desktop/mobile browser cases exercise both resource types, draft/title/DOM
preservation through preview/back, readonly native input, exact historical download
without quota change, restore confirmation/cancellation, new revision/current/origin
markers, real committed lost-response retry across a newer draft and profile language
change, and injected quota failure without draft/current loss. PostgreSQL quota and
race behavior remains covered by the real backend suite, not claimed from injection.
Hook/component tests additionally cover paging, independent preview/list retry,
identity mismatch, timeout, stale result, failed post-commit content loading, explicit
reset and localized recovery. The desktop panel uses the right-side revision list;
mobile stacks the list above the paper. Ukrainian desktop and English mobile captures
were visually inspected. Independent DOCX rendering passed no-edit byte/pixel equality,
three edited/unchanged-page and five multiline-page Ukrainian/astral checks; Word is
not claimed. No history preview can save or replace the live draft.
Actual strict `ci-required` protection including administrators was verified. Next:
individual E06.3b PR, exact-head auto-merge and actual merge verification; then E06.5
operator retention. E05.6b history completion awaits this PR's merge. E06.7 autosave,
E07 acceptance and final E08 deployment remain; unrelated services are untouched.


2026-09-07: E06.3b verified merged through [PR #59](https://github.com/Flippylolz/fillable/pull/59),
merge `0ce5e945abe1ff7f31cb1ee95d135d1983f64c63`; Actions 34108570911 passed
`checks` and `ci-required` for exact head `ad1d2e01719a8cacea466fb39fb6cec4f5a7a27f`.
This completes E05.6b and E05's delivered workspace/history requirements. E06.5
starts on `task/e06-5-version-retention`: explicit operator policy (all by default),
bounded one-shot pruning, retained provenance, reader/restore coordination and
visible localized policy. Configuration alone never deletes history. Scheduling
remains E07.3, autosave E06.7 and deployment E08, last.


E06.5 implementation checkpoint: explicit keep-all/default operator policy and bounded
one-shot pruning now protect original/current/shared files, coordinate readers and
restore commits, clear pruned content while retaining provenance, and keep failed
unlink charged for reconciliation. History exposes policy in its read snapshot and
shows localized limits without replacing the live draft. Migration 0011 removes no
data and guards configured-policy downgrade. Scheduling remains E07.3.

Docker backend checks passed: 377 tests, lines 3680/3706 (99.30%), branches 1099/1126
(97.60%). The real unimported-source negative probe passed (377 tests; line gate
blocked 3680/11438). Frontend initial successful checks: 195 tests, lines 1221/1231
(99.19%), branches 1374/1439 (95.48%); final repeat passed after
fixing an existing preview-selection test race; the negative probe passed with all
195 tests (1221/3969 lines and 1374/6913 branches blocked). Fresh staged verification
passed 7 development and 34 production browser cases in copy `nGgVlH`, project
`fillable-verify-95304`, with a configured policy of two retained latest revisions; no pruning runs in that
browser environment. Actual deletion/races are covered by isolated PostgreSQL/storage
tests. An automatic approval review rejected adding pruning to the production-style
browser verification; that step was removed and the safer verification was approved.
The policy persisted across recreation and both-language desktop/mobile browser checks
passed; desktop English and mobile Ukrainian policy screenshots were visually inspected.
Exact historical downloads and live draft preservation passed. No DOCX transformation
changed here; these checks do not claim Microsoft Word validation. Next: open the
individual E06.5 PR and verify required CI/auto-merge through actual merge.
Then E06.7 autosave; E07 and E08 remain unfinished. No server changes were made.


E06.5 PR #60 is in review with squash auto-merge. Initial head
`8ce1adfd37f15dbdaa199621b87a9d539e8793f8`, CI `34115861870`, failed the
fresh production browser repeat (33/34): the existing mobile manual-save test used
Home/Shift+End to select a heading, which selects only the last visual line when
wrapped. All retention cases passed. The test now selects from document start by
character, preserving actual native keyboard selection and its exact-text assertion.
Required `ci-required` correctly failed and prevented merge. Next: verify this
correction, update the same PR and follow its new exact head through CI/merge.

The corrected selection passed the fresh staged repeat: 7 development and 34
production cases, including both mobile manual-save cases, in copy `3h0NNO`, project
`fillable-verify-96770`. This correction changes only browser selection; application
coverage remains the measured 377 backend/195 frontend test result above. The PR's
new head must pass the complete required CI before E06.7 implementation starts.


Verified E06.5 completion: [PR #60](https://github.com/Flippylolz/fillable/pull/60)
merged as `cf9faecd21e8a6c87b2a31410b3326457fb61437`, exact head
`98fe5b13d58a0e6f0aa9fdf332fda49a0dd1322d`. CI `34116978818` succeeded;
`checks` and `ci-required` both SUCCESS. The browser-selection correction and all
local checks above passed; originals/current files, accounting and provenance remain
protected. Main was synchronized before starting `task/e06-7-autosave`.

E06.7 bounded scope: default-on two-second document autosave using the existing
immutable save/retry protocol, local workspace toggle, localized status, synchronous
composition/validity/lease preflight, and pauses for history, mutations and errors.
No automatic retry of uncertain outcomes and no title-only/document writes. Preserve
newer drafts across acknowledgments and let explicit retry resolve the original
attempt. Verify default-on browser flows, history/IME/error/toggle behavior and both
coverage gates. E07 acceptance/recovery/diagnostics and E08 deployment remain later.


E06.7 local checkpoint: the timer, workspace setting and both-language status/cost
copy are implemented. Docker frontend lint/catalog/type/build and all 203 tests
passed: lines 1231/1242 (99.11%), branches 1401/1468 (95.44%). The real unimported
source probe passed with all 203 tests, blocking 1231/4006 lines and 1401/6994 branches.
The new component tests wait for the new-version lease before simulating further
input; real browser input already waits for editable controls. Initial fresh Docker
verification passed 7 development and 40 production browser cases in `y8EMzG`, project
`fillable-verify-98945`. The final repeat passed 7 development and 40 production cases in `eE6kP3`, project
`fillable-verify-99719`, after tightening checkbox layout and making the manual-save
browser helper explicitly disable autosave. Desktop English settings and mobile
Ukrainian quota-error layouts were visually inspected. Backend source is unchanged from verified
PR60 (377 tests; lines 3680/3706, branches 1099/1126); this task's required CI will
repeat the complete backend/frontend/renderer and failure-gate checks before merge.
Next: open the individual E06.7 PR,
verify strict required checks and exact-head squash auto-merge, then verify MERGED
before E07. Deployment remains last and no server work has begun.


E06.7 review follow-up on PR #61: initial head
`c0544ca3a37468dc8c39485f31da29099f6c6d3c`, CI `34119480377`. Auto-merge was
held after finding that a hidden workspace could start autosave during another
page's active profile/library mutation. SessionPages now passes its shared busy
state into autosave eligibility; document editing/drafts remain intact and the
timer resumes after that mutation finishes. A component test verifies the pause
and later save. New-head verification/auto-merge must complete before E07 starts.

The coordination correction passed all 204 frontend tests and the real unimported-source
negative probe: lines 1231/1242 (99.11%), branches 1405/1472 (95.45%); the probe
blocked 1231/4007 lines and 1405/7000 branches with every test passing. The final
fresh repeat passed 7 development and 40 production cases in `1eW6sJ`, project
`fillable-verify-1534`, before updating PR61 and rearming exact-head auto-merge. Backend application source remains unchanged.


Verified E06.7 completion: [PR #61](https://github.com/Flippylolz/fillable/pull/61)
merged as `d42a463a64eddc9aff5a23290951f406251a402e`, exact head
`28d4692d1fb6a06cc34f823590ecf9dfa1d1dec9`. CI `34120934728` succeeded;
`checks` and `ci-required` both SUCCESS. This closes E06. E04's previously deferred
retained-review/copy acceptance is verified by the merged E06.2a–E06.2c reviewed
snapshot/rebase/save tests and E06.6 restore/reopen evidence; the whole UI acceptance
flow remains an E07.1b verification, not an unimplemented detector feature.

Main synchronized before `task/e07-1a-session-recovery`. E07.1 is split into the
bounded correction E07.1a and acceptance E07.1b above, each delivered separately.
Current gap: an expired session pauses editing but cannot reauthenticate while
retaining the mounted editor. Implement same-owner recovery, a paused API boundary
that treats obsolete write results as uncertain, explicit account-switch discard,
and session identity remounting. Verify actual cookie/CSRF rotation, draft/undo
preservation, old-request fencing and isolation. E07.2–E07.6 and E08 remain later;
no deployment or server access has occurred.

E07.1a implementation retains the hidden/inert same-owner workspace across recovery,
pauses protected requests and lease/autosave activity, and treats obsolete write
responses as uncertain. Account switching requires the existing discard guard and
uses an account UUID page key. Fresh session/login calls have bounded cancellation.
Local Docker frontend lint/catalog/type/build and 228 tests pass: raw lines
1290/1301 (99.15%), branches 1496/1565 (95.59%). The real unimported-source negative
probe fails at 1290/4173 lines and 1496/7307 branches with all 228 tests passing.
The first fresh attempt exposed a typed test-call omission, corrected before the
successful frontend run. A subsequent fresh desktop run verified actual missing
cookies with a still-live old lease, same DOM/draft after sign-in, cancelled discard,
and exact committed-write retry without another revision. Final full browser/locale
verification is running before PR readiness. Backend source is unchanged from the
merged 377-test baseline; this task's required CI will rerun it independently.

Final request-boundary review also cancels in-flight response bodies when their
session generation ends, preserving uncertain write retries. Docker checks now pass
229 frontend tests with 1292/1303 raw lines (99.16%) and 1500/1569 branches (95.60%).
The real negative probe blocks 1292/4178 lines and 1500/7317 branches with all tests
passing. Fresh `18pwmF` passed 7 development/44 production browser cases, including
actual missing-cookie recovery after the old lease expires on both viewports.
English desktop and Ukrainian mobile recovery screenshots were visually inspected.
The final browser suite adds explicit cross-account discard/ownership isolation and
preserved undo/redo; its full repeat and required CI must pass before auto-merge.
Actual main protection remains strict `ci-required` from Actions app 15368, enforced
for administrators; repository squash auto-merge remains enabled. No server actions.


Verified E07.1a completion: [PR #62](https://github.com/Flippylolz/fillable/pull/62)
merged as `b60ba4185407ba38a478f9a9f87ad310a3bbd479`, exact head
`4fcd54080f8b8f263ac486bd967311cb2700fe03`. Required CI `34125040520` succeeded,
including `checks` and `ci-required`. Final fresh `aubF6k` passed 7 development and
46 production browser cases with response-body cancellation enabled. CI independently
passed backend 377 tests and frontend 229 tests, with unchanged raw 90% gates.

Main synchronized before `task/e07-1b-mvp-acceptance`. Add the full reviewed-template
UI journey through independent copy edits/download/reopen and source restoration;
verify the exact shared badge on all four pages in both languages and viewports.
Existing browser suites cover field navigation, quota/errors, profile persistence,
localization failures, autosave, history conflicts and recovery. Record the combined
acceptance evidence without claiming E07.2–E07.6 or deployment complete.

E07.1b's first full Docker run passed 7 development and 48 production browser cases
in `gmzvMr`, project `fillable-verify-9102`. The new journey passes both viewports:
real upload/review/save/copy/edit/download/reopen, source restoration with unchanged
copy bytes/current revision, and both-language badge checks on all four pages.
The final run adds readable remaining-GB assertions; targeted field-card screenshots
will verify long Ukrainian labels. Application source is unchanged from PR62's
backend 377/frontend 229 tests and measured 99.30%/97.60% backend,
99.16%/95.60% frontend line/branch coverage. Required CI reruns both independently.
Documentation links resolve. Final browser/visual verification precedes readiness.


Verified E07.1b completion: [PR #63](https://github.com/Flippylolz/fillable/pull/63)
merged as `71f6250dbe7b7fe8516187f689068a49abc031c3`, exact head
`4a49b3f6c4870c06575e3d81ebecc828b31ac15b`. CI `34127671210` succeeded with
`checks` and `ci-required` SUCCESS. Final fresh `lyl9j9` passed 7 development and
48 production cases, plus 2 focused final-file journey/visual cases. Long Ukrainian
mobile labels and desktop history were inspected. Both raw coverage gates passed.

Main synchronized before `task/e07-2-content-free-diagnostics`. Implement bounded
operator job/capacity/audit diagnostics, content-free API and gateway failure logs,
and atomic revision audit events. Existing unexpected exceptions can reach Uvicorn
with their raw message; nginx currently logs raw URI and native request context.
Verify actual logs with synthetic markers. Preserve all data; any audit index is
additive. Scheduling remains E07.3, and no server access/deployment has occurred.

E07.2 Docker backend lint/mypy and 401 tests pass: 3799/3826 raw lines (99.29%)
and 1132/1160 branches (97.59%). Real Uvicorn tests verify ordinary, streaming and
background failure logs without original exception messages/chains. Real PostgreSQL
checks cover counters, redacted chronological audit pagination, index upgrade/
downgrade without event loss, failed transaction rollback and exact replay without
duplicate save/restore audits. The negative unimported-source probe blocks 3799/11816
lines with all 401 tests passing. The initial audit test used dictionary access on
its typed UserInfo fixture; the assertion is corrected.

Fresh gateway verification initially expected a production 404 from Vite's development
asset fallback (which returns 200); the probe now checks each configured mode explicitly.
Actual development and production gateway stdout/stderr pass content-marker redaction,
including unknown methods and oversized requests. Docker `app.diagnostics status`
and `audit --limit 2` ran successfully against the isolated production-style project
and returned only counters/opaque event identities. The complete browser suite is
finishing before PR readiness. Frontend application source remains unchanged from
PR63's 229-test, 99.16% line/95.60% branch baseline; required CI reruns it.

Final CLI review distinguishes invalid arguments from runtime configuration ValueErrors:
unavailable runtime state now exits 1, while invalid input exits 2. Docker lint/mypy
and 402 tests pass with 3800/3827 lines (99.29%) and 1132/1160 branches (97.59%).
Fresh `eQtDzn` passed all 7 development/48 production browser cases and both actual
log probes, but its still-reading shell wrapper was edited during the run and
failed afterward; it is not recorded as a successful complete verification.
The final repeat runs a frozen staged script. Test-project cleanup preserved volumes.

The final backend unimported-source probe rejects 3800/11821 lines with all 402
tests passing. The frozen fresh run has passed development, production migration/
persistence and both log probes; final production browser cases are running before
PR readiness. Documented operator status/audit commands are included in that run.

Frozen `dFtiIa` passed 7 development/47 production cases; the mobile uncertain-autosave
proof encountered a legitimate 409 `operation_in_progress` on its exact retry after
the first request had committed 201. Trace and worker timing show the saved revision
was being inspected under its shared read lock; the UI correctly kept the pending
snapshot and did not claim success. The browser proof now waits for actual worker
completion before its single-success retry assertion, still asserting no automatic
retry, identical key/body, a separate newer save and no duplicate history. Application
save behavior is unchanged. Repeat the full frozen verification before readiness.


Verified E07.2 completion: [PR #64](https://github.com/Flippylolz/fillable/pull/64)
merged as `191282ce485d6f562be0cd8d0a8b183b7e2ebb1d`, exact head
`814ba015383d87fc68b5356fa8ac7d4021ebf9f6`. CI `34132221304` passed `checks`
and `ci-required`, including both negative coverage probes. Backend 402 tests:
3800/3827 lines (99.29%), 1132/1160 branches (97.59%). Frontend 229 tests:
1292/1303 lines (99.16%), 1500/1569 branches (95.60%). Frozen fresh `CCr4vP`
passed 7 development/48 production cases, both gateway log probes and operator CLI.

Main synchronized before `task/e07-3-scheduled-maintenance`. E07.3 is in progress:
add a Python Compose scheduler with bounded batches/retries, persistent cursors,
singleton locking and content-free durable failure state. Preserve default all-history
retention and unknown filesystem entries. Verify real PostgreSQL concurrency,
crash replay, failed cleanup accounting and actual isolated Compose startup.
E07.4–E07.6 and final E08 deployment remain outstanding; no server access occurred.

E07.3 backend lint/mypy and 416 tests pass: 3969/3998 raw lines (99.27%) and
1174/1206 branches (97.35%). Real tests include process death and PostgreSQL guard
loss, old-run fencing, poisoned-entry cursor advance/wrap, opt-in scheduled pruning,
failed unlink accounting, unknown-entry preservation and bounded account lock waits.
The initial lint/type findings were fixed before this full run. Fresh development
has observed an actual scheduler tick with 5-second statement/2-second lock timeouts;
full production/browser verification and the negative coverage probe are pending.
A frozen launcher preserves the staged verification script while review continues.
Frontend application source is unchanged from PR64's measured 229-test baseline.

E07.3 [PR #65](https://github.com/Flippylolz/fillable/pull/65) is in_review on
`task/e07-3-scheduled-maintenance`. The real negative coverage probe passes: all
416 tests succeed but added unimported source is rejected at 3969/12326 lines.
The first frozen fresh run `kQs6JI`, project `fillable-verify-17887`, fully passed
7 development and 48 production browser cases, both gateway probes, persistence
and actual maintenance ticks. Volumes and evidence are retained. Final committed
verification additionally requires a different maintenance run ID after recreation,
so an old persisted success cannot satisfy the new-process check; that full repeat
and required GitHub CI are running. Changed Markdown links and shell syntax pass.
Next: inspect final results, verify actual strict required rules, enable exact-head
squash auto-merge, confirm MERGED, then begin E07.4. Deployment remains last.


Verified E07.3 completion: [PR #65](https://github.com/Flippylolz/fillable/pull/65)
merged as `e16fb5adbc63449ee96090c01e3af85bc9d31398`, exact head
`38831e232df3ca36fcd98728267f2da35d632978`. CI `34135615841` passed `checks`
and `ci-required`: backend 416 tests, 3969/3998 lines (99.27%), 1174/1206 branches
(97.35%); frontend 229 tests, 1292/1303 lines (99.16%), 1500/1569 branches (95.60%).
Both negative probes passed. Fresh `Xz6P2i` passed 7 development/48 production cases.
The final stricter scheduler probe passed separately after controlled service restart,
requiring a distinct completed successful run. Its initial docker-cp attempt was
rejected by the container's read-only root filesystem; streaming the read-only Python
probe through exec succeeded without changing that protection. Volumes were preserved.

Main synchronized before `task/e07-4-restart-upgrade-proof`. E07.4 is in progress:
verify previous merged application/schema0012 to current/schema0013 using one isolated
synthetic data set, preserving reviewed/copy/restored version bytes and metadata.
Prove a real post-unlink child-process crash remains charged until the actual scheduler
reconciles it after full-stack restart. Add a separate mandatory upgrade CI job and
require both job results in ci-required. No backup or live-server work is introduced.

E07.4's complete isolated `0usKoE` run passed: previous PR64 images/schema0012,
reviewed template plus edited independent copy, original/reviewed restorations,
current images/schema0013, and a real post-unlink exit74 followed by full-stack
restart and actual daemon reconciliation. API, SQL, file hashes, paired review,
provenance and exact quota match. Six desktop/mobile badge cases passed across
previous/upgraded/restarted images. The first run found a helper-only httpx client
lifecycle mistake before document creation; it was corrected. Final formatting and
both-job aggregation failure coverage are included before the final repeat/PR.
Application source is unchanged from PR65's backend416/frontend229 coverage baseline;
required CI reruns both gates. All synthetic volumes and evidence are retained.

E07.4 is in_review in [PR #66](https://github.com/Flippylolz/fillable/pull/66),
branch `task/e07-4-restart-upgrade-proof`. The completed local proof used candidate
`20aa056`; final probe lint and both-job aggregation combinations were added in
`a198389`. The final frozen repeat and both required CI jobs are running. Before
readiness, inspect those results and actual strict main protection, enable exact-head
squash auto-merge, and verify MERGED before E07.5. No product decision is outstanding.


Verified E07.4 completion: [PR #66](https://github.com/Flippylolz/fillable/pull/66)
merged as `0750bd8eb32082692155d0292fcaeb87eabcb0b8`, exact head
`1c53bf2d4f9f2b6226f79e1915bb9abe1b214c73`. CI `34138371739` passed `checks`,
`upgrade-checks` and `ci-required`. Backend416: 3969/3998 lines (99.27%),
1174/1206 branches (97.35%); frontend229: 1292/1303 lines (99.16%), 1500/1569
branches (95.60%). Both negative probes passed. Final local `CVz0BX` independently
passed previous-image upgrade, full restart, post-unlink crash reconciliation and
six badge cases. No server access occurred; synthetic volumes remain preserved.

Main synchronized before `task/e07-5-runtime-isolation`. E07.5 is in progress:
align development/production runtime ceilings, scope log rotation, verify effective
runtime isolation and freeze staged verification drivers/source trees. Refresh stale
onboarding/architecture contracts while preserving the Docs-like UI and readable
localized storage. Initial Compose editing hit nested dependency mappings and was
corrected before startup. First runtime comparison hit duplicated separators in
macOS's temporary path; normalization preserves exact path equality. The second
fresh run passed development/runtime startup and is completing production browsers.
Final frozen source and both mandatory CI jobs must pass before readiness/merge.

E07.5 fresh `sGFuL3`, project `fillable-verify-sgful3`, passed 7 development and
48 production browser cases. All four effective-runtime assertions passed before/
after development and production flows: configured hard ceilings/log rotation,
users, private shared mounts, loopback-only publication and no reported container
OOM/restarts. Docker samples are point-in-time, not peaks. The frozen source still
matched its captured Git tree after the working index changed; the initial ad-hoc
zsh comparison had a colon-modifier syntax error and the corrected byte comparison
passed. Final drivers also isolate synthetic environment settings, retain source-tree
reports, and use `development` for uncommitted snapshot badge metadata. Final full
fresh/recovery repeats and both CI jobs are required before readiness.

E07.5 is in_review in [PR #67](https://github.com/Flippylolz/fillable/pull/67),
branch `task/e07-5-runtime-isolation`, candidate `f2f32ec`. Utility lint, shell syntax
and the first complete bounded-runtime browser run pass. Final committed fresh and
previous-image recovery proofs run in separate unique projects with immutable drivers.
Review their results and required CI, then enable exact-head squash auto-merge under
verified strict protection and confirm MERGED before E07.6. Deployment remains last.


Verified E07.5 completion: [PR #67](https://github.com/Flippylolz/fillable/pull/67)
merged as `5b18bd53f09f8bf55d1668f0032c018119206279`, exact head
`009e8314f7d1650af046277cb2a4717a9d7263e2`. CI `34141793505` passed `checks`,
`upgrade-checks` and `ci-required`. Backend416: 3969/3998 lines (99.27%),
1174/1206 branches (97.35%); frontend229: 1292/1303 lines (99.16%), 1500/1569
branches (95.60%). Final local fresh `GhkrgQ` passed 7 development/48 production
browser cases and four runtime probes; recovery `OSkwd1` passed upgrade, restart,
post-unlink reconciliation and six badge cases. All synthetic volumes preserved.

Main synchronized before `task/e07-6-coverage-provenance-audit`. E07.6 adds source
fingerprints captured before tests and verified unchanged afterward, plus report
byte digests checked by the independent raw coverage gate. A real coverage.py
scratch reproduction showed the previous filename-only check accepted a stale
report after a same-name source edit. Previous CI used fresh reports; those recorded
measurements remain valid. New producer wrappers remove old reports/stamps and only
record successful runs. No threshold, application exclusion or dependency changes.
Both real negative probes, complete local suites and required CI must pass. Actual
GitHub protection was reread: strict `ci-required`, Actions app 15368, administrators
enforced. No deployment workflow or server access exists yet; E08 remains last.

E07.6 is in_review in [PR #68](https://github.com/Flippylolz/fillable/pull/68),
source candidate `730ad7f`. Three provenance tests, raw boundary/source contracts and
all aggregation result combinations pass. Frontend229 passes with baseline coverage;
the real negative probe rejects both metrics with all tests passing. Its final probe
also exercises the actual producer and verifies failed coverage removes an old stamp.
Full backend suite/probe and final frontend producer repeat are running. Required CI
must pass for the final head; verify protection and exact-head auto-merge, then actual
MERGED before E08 preflight. There is no external blocker or server access yet.


Verified E07.6 completion: [PR #68](https://github.com/Flippylolz/fillable/pull/68)
merged as `5e645f731f486772d8eee302c486957093251557`, exact head
`4479288c82a6b6c19fe423892e8366496efdc556`. CI `34144215382` passed `checks`,
`upgrade-checks` and `ci-required`, both real negative probes, source provenance
contracts, fresh/runtime/browser/persistence checks and independent DOCX rendering.
Backend416: 3969/3998 lines (99.27%), 1174/1206 branches (97.35%); frontend229:
1292/1303 lines (99.16%), 1500/1569 branches (95.60%). E00–E07 are complete.

Main synchronized before `task/e08-1-server-preflight`. Strict trusted-host SSH works;
read-only preflight verified Linux amd64, Docker/Compose, remaining capacity, fifteen
existing containers and WEF's authoritative shared-nginx manager snapshot. The
candidate edge was already unhealthy; other baseline states are preserved. Initial
nginx -t used the image default, then the actual custom config was identified and
explicitly validated successfully. The shared container publishes only 80/443; a
Fillable-owned TCP relay can expose a new port without recreating shared nginx, with
HTTP routing still handled by the existing manager. E08.3 must prove this topology.

The live existing HTTPS response has HSTS max-age=31536000. After that conflict was
explained, the user explicitly reaffirmed HTTP, requested a new port like 3200, and
excluded TLS/HTTPS. D019 records the resulting browser limitation; existing TLS stays
untouched. Port 3200 is unused and absent from checked managed Compose allocations.
An isolated, resource-limited temporary Docker HTTP probe worked locally but failed
publicly; it was stopped and removed automatically. The user then reported TCP 3200
opened/forwarded and the public retry is running. No application deployment, shared
reload, manager edit, data deletion or unrelated service restart has occurred.

E08.1 public retry succeeded after the user's network update: exact fixed HTTP probe
response at port 3200, followed by successful stop/automatic removal. Access is no
longer blocked. The user explicitly kept HTTP after HSTS disclosure. Preflight
documentation is ready for its own PR; no application source or new coverage
measurement is introduced. Required CI must pass and the PR must merge before E08.2.

E08.1 is in_review in [PR #69](https://github.com/Flippylolz/fillable/pull/69),
branch `task/e08-1-server-preflight`, candidate `53dd9e1`. Documentation links,
private-identity scan and whitespace passed. The successful public 3200 probe was
stopped/removed; no server application/configuration change remains. Repository
secrets and deployment environments are currently empty (names-only inspection).
Next: verify final required CI/protection, exact-head squash auto-merge and MERGED;
then E08.2 creates the protected immutable-artifact workflow. The HTTP decision and
port access are settled; do not ask again. No external dependency is outstanding.


Verified E08.1 completion: [PR #69](https://github.com/Flippylolz/fillable/pull/69)
merged as `0b38ea67f729ce9f37f36c3c296106b6e0cdfde4`, exact head
`08341c7fe502b8facf7262143559768ed208293a`. Required CI `34146598548` passed
both jobs and ci-required, with baseline backend416/frontend229 independent coverage
and both negative probes. The local relay proof also passed: validated graceful
reload introduced a listener while the existing route, container ID/start time and
zero restart count were preserved. Public HTTP 3200 and strict SSH access work.

The user reported subsequent main push CI `34147985255` failed on merge revision
`0b38ea6`: desktop manual-save heading selection returned `КЛІЄНТА` plus the next
paragraph instead of `АНКЕТА КЛІЄНТА`. The other 47 browser cases and upgrade job
passed; ci-required correctly failed. No deployment was attempted. E08.2's unfinished
workflow/artifact files remain preserved on its original branch/workspace. E07.1c
runs in an isolated worktree on current main, branch `task/e07-1c-browser-selection`.

The correction selects the complete first paragraph through the native DOM Selection
API and waits for the actual selectionchange event observed by the editor. This save
journey no longer assumes that a global Control+Home followed immediately by arrow
keys established the intended starting caret. The exact heading assertion and all
real field creation, save, history, download/reopen assertions remain. Full fresh
browser checks and repeated focused desktop/mobile journeys must pass before PR
readiness; required CI/90% gates and actual merge are still mandatory. Port and HTTP
choices are settled; no external dependency is outstanding.

E07.1c is in_review in [PR #70](https://github.com/Flippylolz/fillable/pull/70),
candidate `4ac12ba`. A frozen source/driver runs full fresh verification plus ten
repetitions per viewport of the affected manual-save journey; source is isolated from
E08.2's uncommitted deployment files. The initial run has passed service startup,
account provisioning and persisted storage/document checks. Required PR CI and
repeated browser results remain pending. Before readiness, inspect results, verify
strict protection, enable exact-head squash auto-merge and confirm MERGED. Then
synchronize the E08.2 branch without discarding its preserved work.


Verified E07.1c completion: [PR #70](https://github.com/Flippylolz/fillable/pull/70)
merged as `1bc9fb95549abfb25810aa5d40cc1d2933dbbf35`, exact head
`72df9824a37eb317d5ca5b5e399d5a98d51a5301`. Required CI `34149117891` passed
checks, upgrade-checks and ci-required. Backend 416 tests: 3969/3998 lines and
1174/1206 branches; frontend 229 tests: 1292/1303 lines and 1500/1569 branches.
Both real uncovered-source probes failed their gates as required. Frozen local
verification passed all 7 development and 48 production browser cases, plus 20
repeated desktop/mobile manual-save journeys and effective runtime isolation checks.
The historical failed main run remains failed; replacement main CI `34150436861`
is being followed separately. E08.2 resumed without discarding its preserved files.

E08.2 is in progress on `task/e08-2-gated-artifact-workflow`. The
[release contract](RELEASE_ARTIFACTS.md) implements exact-main successful CI evidence,
serialized manual deployment, source-bound amd64 image archives and strict SSH receipt/
apply validation. Seven Docker contract tests pass; actual image packaging and required
PR CI remain pending. The receiver is intentionally absent until E08.3, so the workflow
cannot claim rollout success. No production runtime or shared nginx has been changed.
Next: validate real Docker archives and badge, open this task's PR, verify required
CI and exact-head auto-merge, then confirm MERGED before E08.3 implementation.

E08.2 is in_review in [PR #71](https://github.com/Flippylolz/fillable/pull/71).
Candidate `c450f3712e634677b03cd2d400084ebb18d318b0` passed seven Docker contract
tests, Ruff, shell syntax and diff checks. A real Linux amd64 build from that exact
Git archive produced a 129,914,880-byte release archive with SHA-256
`83b8f079e028e212e000d700f32c5f35bc35cae4c6d596df149df6c39abae246`.
Strict unpack and Docker load passed; the loaded gateway served `version: c450f37`
on desktop/mobile with click-through CSS intact. This isolated badge check stubbed
API responses and does not claim a production MVP smoke test. Its temporary gateway
and network were removed; artifact and screenshot evidence is retained locally.
The artifact records its actual candidate PR run `34151276606` for local QA only;
that run is not eligible main deployment evidence. The production gate independently
requires successful current-main push CI. Required final-head PR CI remains pending.

Verified E08.2 completion: [PR #71](https://github.com/Flippylolz/fillable/pull/71)
merged as `fe0170278382e0aec7cb4524f42c68a839ab409e`, exact head
`a2ea1ecff80e8dfdf41456b773a5db06f39a3dd5`. Required CI `34151518784` passed all
three jobs. Backend416: 3969/3998 lines, 1174/1206 branches; frontend229:
1292/1303 lines, 1500/1569 branches. Both real negative coverage probes blocked.
The live Docker release gate accepted corrected-main CI `34150436861` and rejected
wrong source identity. Six isolated transport success/failure scenarios passed.
A deliberately invalid-revision dispatch `34152780582` is verifying the actual
workflow rejects deployment before any production job; it is an intentional gate
probe, not an application CI failure. No application deployment has occurred.

E08.3 begins on `task/e08-3-isolated-runtime` from verified E08.2 merge. Scope:
fixed namespaced runtime configuration, bounded restricted artifact receiver,
reviewed same-schema/forward recovery, authoritative shared-nginx include and
coordinated activation, isolated local lifecycle checks, and private server/bootstrap
configuration. Actual Actions application rollout remains E08.4; deployed MVP and
persistence proof remain E08.5. Only Fillable resources may be mutated. HTTP 3200,
existing TLS/services, independent coverage gates and keep-all history remain fixed.

The deliberate invalid-source workflow `34152780582` failed in verify and skipped
release, as required. It performed no server action. The prior application main CI
`34150436861` is fully successful after PR #70's correction.

E08.3 local implementation now includes the [fixed server runtime](SERVER_RUNTIME.md),
restricted receiver, source-fingerprinted private installer and coordinated shared
manager extension. Nine Docker receiver/runtime contracts plus seven release contracts
pass with Ruff. Real Compose configuration and nine unsafe mutation probes pass. The
first real-manager local attempt stopped because host Python 3.9 cannot load the
existing manager's evaluated union type; its own stack shut down with volumes retained.
Rerunning with the available compatible Python succeeded using frozen helper/config
copies and actual amd64 application images from E08.2's candidate.

The successful isolated proof (`fillable-e083-npyj_wem`) passed six desktop/mobile
manual-save/badge cases through relay → real shared-manager nginx → private app.
Stored ready-file bytes/digests and quota counters matched after restarting every
Fillable long-running service. Shared container ID/start time/restart count and its
existing route remained unchanged. Scoped removal preserved injected owner edits in
current configuration and templates. All own proof services/network were removed;
volumes, source copies and reports are retained. No server application or shared
configuration has been changed. The supplied server's Python 3.12 is compatible;
its inspected manager/template fingerprints are retained privately for bootstrap.

Next: finish final checks/documentation, deliver E08.3 through its own required-CI PR
and verified auto-merge, then privately install the receiver and main-only environment,
verify strict-key readiness and unchanged service baselines before E08.4. Actual
application release and deployed acceptance remain unfinished.

E08.3 is in_review in [PR #72](https://github.com/Flippylolz/fillable/pull/72),
initial candidate `da0e51b`. All local evidence above passed. Actual strict
ci-required protection with administrator enforcement was reread; no production
environment exists yet. Final-head required CI and verified merge must precede
private bootstrap. Prepare a new dedicated key locally while CI runs; install only
verified merged files, retain private settings, constrain the environment to main,
and confirm receiver check plus unchanged server baselines before E08.4.

E08.3 receiver review also identified Docker's OCI index as an alternate image/tag
source beside the legacy manifest. The archive verifier now checks that index's
manifest bytes/digests, exact two image configurations and Fillable-only aliases;
it rejects nested indices, extra images, mismatched configs and unsafe outer Docker
members. The actual saved amd64 archive passes both metadata paths. Eight release
contracts and nine runtime contracts pass; final-head required CI restarts for this
necessary receiver-boundary correction. Private bootstrap guards must use the updated
PR head/run and still wait for verified MERGED.

E08.3 also prepares source-bound initial administrator provisioning so the first
Actions rollout can complete authenticated verification without deploying public
fixture credentials. The restricted provision command accepts bounded private stdin,
requires the last successful source/digest and matching running API image, and calls
the existing account CLI only when the user table is empty. It cannot reset/delete
accounts. Ten runtime contracts and eight release contracts pass; application code
and its coverage gates remain unchanged. Final-head CI must pass again before bootstrap.

Live E08.3 checkpoint: PR #72 final candidate
`851feafc7db2522d8d29ea71a54111030503fa1e`, required CI `34156895196` running,
exact-head squash auto-merge enabled. The superseded checkpoint/OCI-only runs were
cancelled by the newer head. This checkpoint is carried forward without restarting
CI for a metadata-only commit. Dedicated key/trusted-host/private initial-account
inputs are prepared only in ignored local operator files; no production environment,
receiver installation, account provisioning or server configuration change has run.
The private bootstrap guards require this exact head/run to succeed and PR #72 to
be MERGED. Next: inspect CI, confirm merge, run guarded private bootstrap and main-only
environment preparation, verify unchanged containers and restricted receiver readiness,
then begin E08.4's authenticated Actions rollout task.

E08.3 code PR #72 is verified MERGED as
`c086a1f58d2e8fec483b7684e557bfda233ff1c3`, exact head
`851feafc7db2522d8d29ea71a54111030503fa1e`; CI `34156895196` passed all jobs,
backend416/frontend229 raw coverage and both negative probes. Guarded bootstrap
stopped in its first read-only container inventory before any server mutation:
Docker 29 rejects direct `.State.Health` access for four of the 15 existing containers
without a healthcheck. Private files/keys remain local; no receiver/environment/account
was installed. The failure also affects the receiver's shared-service snapshot format.

E08.3a corrective task: make missing health state valid through safe map lookup,
verify actual Docker inspection of a newly created container without a healthcheck,
and verify the supplied server's mixed health/no-health inventory read-only. Deliver
in its own PR with required CI/auto-merge before retrying private bootstrap from the
corrected merged source. E08.4 remains blocked only on completing this routine fix.

E08.3a local verification passes: ten runtime contracts, eight release contracts,
scoped Ruff, actual Compose rejection probes, and real Docker inspection of an owned
stopped container without a healthcheck. The probe was removed. Read-only server
inventory now parses all 15 containers (10 healthy, one pre-existing unhealthy, four
without healthchecks). No server state changed. Required final-head CI and merge
remain pending before corrected private bootstrap.

Live E08.3a checkpoint: [PR #73](https://github.com/Flippylolz/fillable/pull/73),
head `ce00405d1dbe1f9350e707231d370148d4c2dc6c`, required CI `34158778326`
running and exact-head squash auto-merge enabled under strict administrator-enforced
ci-required protection. Upgrade/recovery job passed. Main CI `34158010119` for PR #72
merge is also being followed. Port 3200 remains absent from all 13 inspected managed
Compose files. Guarded private bootstrap/environment scripts now require PR #73 and
its exact successful head/run/merge; no receiver installation or server mutation yet.

E08.3a PR #73 is verified MERGED as `beffa8a54c53cf1cadf3f923cc32775a9e774fa3`,
head `ce00405d1dbe1f9350e707231d370148d4c2dc6c`, CI `34158778326` SUCCESS
for all three required jobs. Backend 3969/3998 lines, 1174/1206 branches; frontend
1292/1303 lines, 1500/1569 branches; both real unimported-source probes passed.
The corrected merged receiver is now privately installed: restricted check passes,
arbitrary command is rejected, and exact before/after container baselines match.
No application or shared nginx configuration was started/changed by bootstrap.

E08.3 private preparation is complete: production environment is verified main-only,
and four dedicated deployment secret names are configured via private stdin. E08.4
begins from `beffa8a54c53cf1cadf3f923cc32775a9e774fa3` on
`task/e08-4-actions-rollout`. Add authenticated public HTTP smoke after artifact apply,
private initial-account provisioning only for an empty database, and safe evidence
for upload/save/original/current/history downloads. Exercise this checker against
the actual isolated app and test failure handling. Deliver this task through required
CI and verified merge, then dispatch Actions only after exact-main push CI succeeds.
Compare existing service/routes and preserve HTTP 3200, data and shared TLS policy.
E08.5 remains the broader deployed browser and persistence acceptance task.

E08.4 local implementation verifies public authenticated rollout with generated private
credentials and source-bound empty-database provisioning. Shared SSH setup preserves
strict trusted-host/dedicated-key behavior. Two HTTP contract tests and six shell
provisioning/failure scenarios pass, along with the six existing transport scenarios.
An isolated actual amd64 app + real manager + relay proof passed login and two full
upload/save/original/current/history smoke executions. Full Fillable restart preserved
stored file bytes/digests/quota counters; scoped include removal preserved concurrent
owner edits and the shared container baseline. Own probes were stopped; data retained.
Proof root `fillable-e084-real.timgnz3s`, project `fillable-e084-timgnz3s`.
Next: task PR, required CI/verified merge, configure two private initial-account
environment secrets, wait successful exact-main CI and run the Actions workflow.

Live E08.4 checkpoint: [PR #74](https://github.com/Flippylolz/fillable/pull/74),
head `2819601f9de390ad4484f76fc5b693ac5c814a8f`, CI `34160681711`
running, exact-head squash auto-merge enabled under verified strict protection.
Main CI `34160031264` for E08.3a merge is being followed. Private account-secret
preparation is guarded on PR #74 MERGED; two additional secrets are not installed yet.
Next: complete CI/merge, configure those secrets, wait successful exact-main push CI,
recheck target reservations/capacity, dispatch deployment, verify public smoke and
unchanged existing services/routes, then begin E08.5. No application deployed yet.

E08.4 code PR #74 is verified MERGED as `fdfe53bb5f739fe8c72ff905785c753f260e7780`,
head `2819601f9de390ad4484f76fc5b693ac5c814a8f`; CI `34160681711` passed
all required jobs and unchanged raw coverage (backend 3969/3998,1174/1206; frontend
1292/1303,1500/1569) plus both negative probes. Main CI `34161861411` is running.
Automatic approval review rejected configuring the two newly generated initial-account
secrets in GitHub production, requiring explicit approval of that payload/destination.
A concise approval request is pending; no retry or workaround has run, and no app has
been deployed. Existing four transport secrets/receiver are ready.

E08.5 independent tooling preparation starts from the merged E08.4 source on
`task/e08-5-deployed-acceptance` while that credential dependency waits. Parameterize
the existing real bilingual four-page journey with private credentials, retain only
synthetic identity/digest manifests, and add read-only post-restart verification.
Exercise locally through real app/relay; actual deployed acceptance and task completion
still depend on successful E08.4 rollout. This does not advance or bypass deployment.

E08.5 local tooling verification passed: desktop/mobile four-page bilingual journey
(2 cases, 25.8s), inspected local screenshots, actual shared-manager/relay path, full
Fillable restart with identical stored bytes/digests/quota counters, and public checks
of retained document models/downloads/full version history for both manifests.
Corruption contracts reject changed bytes/models/current/history and wrong version.
Proof root `fillable-e085-real.uvw0vu9t`; own containers stopped, volumes retained.
The task will be a draft PR while actual target rollout/acceptance is blocked on the
pending explicit credential-secret approval. It must not auto-merge or be marked done
until that acceptance is verified; deployment must use current-main source.

E08.4 code PR #74 merged as `fdfe53bb5f739fe8c72ff905785c753f260e7780`;
PR CI `34160681711` and main CI `34161861411` passed. Actual deployment waits
for explicit approval requested by automatic review for the two generated initial
account secrets. Independent E08.5 tooling is in draft PR #75.

E08.5a corrective task: draft #75 CI `34162407970` exposed an existing editing-lease
test race in the fresh production suite (47 cases passed, one failed). The synthetic
trace shows its initial `/content` API request returned HTTP 409, but the test parsed
that error as its baseline and compared later document content to undefined. Make
both saved-state reads require HTTP 200, retry only the documented temporary busy
response, and preserve the exact document/resource/quota comparisons. Deliver in its
own PR from merged main with repeated real browser verification and required CI;
then refresh the draft acceptance PR. Do not retry credential upload without approval.

E08.5a local verification passed all 20 real two-tab browser scenarios (10 desktop,
10 mobile, 48.5s) through the isolated actual app/shared-manager/relay. Full scoped
restart retained stored bytes/digests/quota counters; shared service/route remained
unchanged and own containers stopped with volumes preserved. Proof project
`fillable-e085a-fpcvr2vg`. Required final-head CI and merge remain pending.

Live E08.5 checkpoint: draft [PR #75](https://github.com/Flippylolz/fillable/pull/75),
head `05c44db2dd6d120c426e3cfb383f44bb8907256d`, required CI `34162407970` running.
PR stays draft without auto-merge because actual deployed acceptance is still pending.
E08.4 main CI `34161861411` for `fdfe53bb5f739fe8c72ff905785c753f260e7780`
is also running. Local acceptance proof and corruption tests passed; no target app
rollout has run. Automatic-review credential approval question remains pending.
On approval, run guarded private initial-account secret preparation, verify exact-main
CI success/current main, recheck capacity/reservations, dispatch E08.4 Actions, verify
existing services, then run E08.5 private browser/restart/negative-badge acceptance.
Record actual results and only then ready/auto-merge PR #75 behind its required CI.

E08.4 exact merged-main CI `34161861411` is verified SUCCESS for all required jobs
on `fdfe53bb5f739fe8c72ff905785c753f260e7780`. Current rollout source is eligible
subject to rechecking main/CI at dispatch. Explicit credential-secret approval remains
pending, so no deployment dispatch or secret-upload retry has run. Draft #75 CI
`34162407970` remains in progress; upgrade and browser jobs/stages passed.

Draft #75 CI `34162407970` failed in an existing editing-lease test during the fresh
production run: 47 passed, initial `/content` API baseline was HTTP 409 (trace verified),
so the test compared later document content to undefined. Actual new acceptance cases
passed. Corrective E08.5a is isolated in `/private/tmp/fillable-ci-content-fix`, branch
`task/e08-5a-lease-snapshot-read`, based on verified merged main. It requires HTTP 200
for baseline/final reads, retries only operation_in_progress, retains every exact
comparison, and uses a unique synthetic title for repeated verification. Twenty real
browser cases are running (10 per viewport). Deliver corrective PR/CI/merge, then
refresh draft #75; actual deployment still waits on the credential approval.

Corrective E08.5a is in [PR #76](https://github.com/Flippylolz/fillable/pull/76),
head `bc5abee` (full head in corrective worktree), CI `34163615157` running with
exact-head auto-merge enabled and actual strict/admin-enforced protection verified.
Twenty local real browser repetitions passed in 48.5s. Next verify required CI/merge,
merge origin/main into draft #75 preserving its checkpoint, rerun required CI, and
retain draft status until actual deployment acceptance. Credential approval still pending.

E08.5a PR #76 is verified MERGED as `3a8d5f8e1c906839ce379571cd8626609fd6a700`,
head `bc5abee79961088e40340d9b8589c800676b9a98`, CI `34163615157` SUCCESS.
Draft #75 is refreshed with that merged correction and retains its local acceptance
proof. Required CI must pass on the refreshed head. Current-main deployment source
is now the E08.5a merge and requires its successful push CI before dispatch; the
credential-secret approval remains pending. Actual target rollout/acceptance remains
unperformed, so #75 stays draft without auto-merge.

Final resumable checkpoint — 2026-09-08 Europe/Warsaw:
- Current main `3a8d5f8e1c906839ce379571cd8626609fd6a700` is verified unchanged,
  CI `34164778514` SUCCESS on all required jobs. PR #76 correction merged.
- Draft #75 head `404ba6fbc1f07b46ba7cc00438f392bf159b4883` passed CI
  `34164855430` on all required jobs. Backend 3969/3998 lines,1174/1206 branches;
  frontend 1292/1303 lines,1500/1569 branches; both actual source-inclusion negative
  probes passed. Draft remains OPEN/isDraft=true, autoMergeRequest=null because actual
  deployed acceptance is unfinished. Local two-viewport/restart/digest proof passed.
- No target application rollout has run. Corrected receiver/dedicated key and four
  transport environment secrets are installed, verified; existing services preserved.
- Sole external blocker: automatic approval review rejected storing the generated
  initial-account email/password as FILLABLE_INITIAL_EMAIL/FILLABLE_INITIAL_PASSWORD
  in GitHub production. Explicit approval question remains pending. Do not retry,
  work around the rejection, or treat elapsed time as approval.
- On explicit approval: run guarded `/private/tmp/fillable-e084-account-secrets.py`;
  recheck current-main successful CI and target capacity/3200 reservations, then
  dispatch deploy.yml for exact current main. Verify Actions apply/public smoke and
  unchanged existing containers/routes/HSTS. Run draft #75's private desktop/mobile
  acceptance, controlled wrong/development badge rejection and scoped Fillable restart
  with public retained-model/download/history comparisons. Record actual release
  source/digests/results, ready draft #75, verify required CI/protection, enable
  exact-head auto-merge, confirm MERGED and finish E08 only after actual acceptance.
- Keep HTTP3200/TLS-out-of-scope choice; no shared service restart, pruning, volume
  removal, backups or fixed public passwords. Private operator input remains ignored.

2026-09-08 resumed checkpoint: the requested password is exactly ten characters;
prior agent counts were incorrect. The user approved login-name authentication and
a ten-character minimum, and rejected storing account credentials in GitHub.
Ignored private requested-account configuration is prepared with mode 0600;
no account has been created and no application is running on the target.
E08.6 is PR #77, branch `task/e08-6-login-identifier`, head
`60ee49ad36ab1d89bdd5786fd2f7018bd8bc3ef4`, in isolated worktree
`/private/tmp/fillable-login-change`. Local 417 backend / 229 frontend tests and
7 development / 48 production browser tests passed, including storage recreation.
Backend raw coverage 3970/3999 lines and 1174/1206 branches; frontend 1292/1303
lines and 1500/1569 branches. CI run 34194979359 is pending, upgrade-checks passed,
exact-head squash auto-merge is enabled under strict admin-enforced ci-required.
After its verified merge, implement E08.7 private operator provisioning/acceptance
workflow adaptation in its own PR. Then deploy through Actions, privately create
the requested normal user, and finish draft PR #75's actual public browser,
history/persistence and wrong-badge negative acceptance. The target port is still
unreserved across 13 managed Compose files; shared active release is unchanged.

E08.6 user-requested account update (2026-09-08): use a login name instead of an
email address and a ten-character password minimum. The supplied private password
is ten characters; an earlier agent count was incorrect. Do not publish credentials
or upload them to GitHub secrets. Preserve existing account UUIDs, stored identifiers,
hashes, sessions, quotas and documents; expose login in API/UI/operator commands,
allow existing email-shaped identifiers as logins, and keep legacy request/CLI input
aliases so installed tooling and upgrade verification remain compatible. No database
rewrite is needed: the existing unique text column stores the same identifiers.
Deliver this change separately with auth/profile/browser/upgrade and >=90% gates.
Then adapt deployment verification to private operator account creation (no credential
secrets), perform actual rollout and create the requested user through private stdin.

E08.6 local gates: 417 backend tests pass with raw coverage 3970/3999 lines
(99.27%) and 1174/1206 branches (97.35%); 229 frontend tests pass with raw
coverage 1292/1303 lines (99.16%) and 1500/1569 branches (95.60%). Login tests
cover Unicode/case-folded identifiers, duplicate rejection, 9-character rejection,
10-character creation/change/reset, session revocation and legacy input aliases.
Fresh development/production browser verification and final-head CI remain pending.
The requested account will be created privately after the final Actions rollout;
no account credentials have been sent to GitHub.

E08.6 PR #77 initial CI run 34194979359 reached the 20-minute `checks` job
limit during the frontend negative coverage probe. Both real browser suites,
DOCX rendering, 417 backend tests, 229 frontend tests, and the backend negative
probe passed; upgrade-checks passed. The aggregator correctly failed on cancellation.
Allow 30 minutes for this sequential full verification job, preserving every check,
threshold and failure rule. This is bounded runtime headroom for observed runner
variance, not a retry or coverage bypass. Exact updated-head CI must pass.

E08.5 refreshed against merged E08.6 login behavior. PR #77 is MERGED at
bdf5ca846eea0afefabf92b9f50c0f73bdaa88cd, CI 34196658969 successful. Existing
acceptance browser/persistence helpers now take private FILLABLE_INITIAL_LOGIN
and the new login labels. E08.7 PR #78 is independently under required CI;
actual deployment and this draft's final public acceptance still remain pending.

2026-09-08 latest checkpoint: E08.6 PR #77 MERGED at
bdf5ca846eea0afefabf92b9f50c0f73bdaa88cd; final PR CI 34196658969 SUCCESS.
Its first run hit the 20-minute job limit after application tests passed; checks now
have 30 minutes with unchanged coverage/negative probes and aggregation rules.
E08.7 PR #78 is ready with exact-head squash auto-merge on
280fbdc3a775faf55de60aed03c4fd79afe6f761, CI 34198928848 running.
Its 16 shell and 3 HTTP contracts passed; real local readiness, repeated authenticated
smoke and full restart bytes/digests/quota proof passed in fillable-e087-k9m9t1k6.
Private credentials are absent from GitHub: only the four transport secret names
exist in production. The private requested-account JSON remains ignored, mode 0600.
A guarded private provisioning helper is prepared but has not executed on the server.
It requires a successful exact-source Actions rollout/evidence, locks the receiver's
release lock, verifies active image/state, and never resets an existing account.

Draft E08.5 PR #75 refreshed merged login behavior at
20dff9abc356ab16e7a6982226924dde9a9ffead; CI 34199296170 running, still draft.
Refreshed real desktop/mobile MVP journeys and public retained byte/model/full-history
checks passed after scoped restart in fillable-e085-login-cp7q34zu. Both local proof
projects stopped their own containers, retained volumes, and preserved shared test
routes/container state/concurrent owner edits. Actual target deployment/acceptance
remains pending. Next: verify #78 merge, refresh #75 with that merged base, wait for
exact-main CI, recheck target baselines, dispatch Actions, create requested user by
private stdin, run authenticated public/badge/persistence proofs, and only then
ready/auto-merge #75 and verify final completion. No credential upload is authorized.

E08.5 refreshed CI 34199296170 found a separate history acceptance read race:
47 browser tests passed; the restored-current download returned documented
HTTP 409 operation_in_progress, and the test compared its 58-byte JSON body with
the 595094-byte original DOCX. The synthetic trace confirms restore succeeded
(201). Require HTTP 200 and retry only that specific transient busy response before
retaining the exact-byte equality assertion. This corrects acceptance observation;
it does not weaken document or history comparisons or change application behavior.

E08.5 history-read correction verified locally: all 20 real template/document history
scenarios (desktop/mobile, five repetitions each) passed in 1.7 minutes. Exact
restored DOCX bytes, retained versions and draft behavior remained checked. Full
scoped restart preserved stored bytes/digests/quota; shared route/container state
and concurrent owner edits survived. Proof project fillable-e085-history-quntd4pz
stopped with persistent volumes retained. Final refreshed-head CI still required.

E08.6 done: PR #77 merged as bdf5ca846eea0afefabf92b9f50c0f73bdaa88cd.
Exact-head CI 34196658969 passed checks, upgrade-checks and ci-required. Local and
CI application coverage remained above both independent 90% gates; the negative
probes rejected real unimported application source. The initial timed-out run is
superseded by this successful run; no gate was bypassed.

E08.7: private account creation and acceptance (user-requested dependency before
final rollout). Keep only dedicated transport secrets in Actions. Verify public
readiness without account credentials; explicitly leave authenticated acceptance
pending. The operator privately creates the requested normal user and runs the
required authenticated smoke, browser and persistence checks before completion.
Remove automatic account provisioning from the private smoke shell; failed login
must fail without resetting or creating any account. Preserve installed receiver
fingerprints, all coverage/CI gates, HTTP 3200 and existing server services.
Tests must reject broken readiness/cookie/CSRF/auth boundaries and stale evidence,
and prove the private smoke shell never invokes SSH/provisioning. Verify this task
in its own PR before actual deployment and final E08.5 acceptance.

E08.7 local contract verification: all 16 shell scenarios pass, including wrong
source/image, unapplied release, invalid credentials, bad receipts and failures after
writing output; no scenario invokes SSH/provisioning or exposes credentials.
Three HTTP contract tests pass, with readiness rejecting broken service, HTML,
session/cache/cookie/CSRF/origin/private-data boundaries. Real isolated readiness,
authenticated plain-login smoke and full restart/storage verification are in progress.
Application source is unchanged from E08.6; its measured backend coverage is
3970/3999 lines and 1174/1206 branches, frontend 1292/1303 lines and 1500/1569
branches. This task's exact-head CI will remeasure both independently.

E08.7 verified MERGED: PR #78 at 4e1d574932e19843c5f43e7f1d2a1661df0be476,
required PR CI 34198928848 SUCCESS. Exact merged-main CI 34200635960 is pending
and must pass before the final Actions dispatch. E08.5 draft now incorporates that
merged base plus the verified history-read correction; its required CI must pass.
No target deployment or private account creation has run yet.
E08.8 user-directed HTTPS handoff (2026-09-08): shared nginx now owns the already
deployed TLS listener on internal 3200, proxying to fillable-gateway:8080 over
wef-edge. Fillable alone publishes host 3200 through its TCP relay. Forecast HTTP
3000, WEF HTTP 3100/HTTPS 443, the existing certificate and HSTS remain unchanged.
This explicitly supersedes the earlier HTTP-only decision. Contact the shared-nginx
configuration task before ingress changes; no old HTTP rollout may be dispatched.

Adapt runtime/public checks and private operator configuration to HTTPS with Secure
cookies and certificate verification. Treat the shared listener as externally owned:
receiver application rollout must not add/remove includes, patch templates/manager,
reload nginx, or remove the existing TLS route on failure. Update only Fillable's
installed receiver/runtime origin after reviewed CI/merge, under its release lock,
preserving credentials, keys and data. Prove TLS through the relay and private app,
authenticated acceptance, immutable artifacts and unchanged existing services. This
is a separate prerequisite PR before actual deployment and E08.5 completion.

E08.7 prerequisite PR #78 merged as `4e1d574932e19843c5f43e7f1d2a1661df0be476`;
PR CI `34198928848` and main CI `34200635960` succeeded. E08.5 draft #75 head
`45826f0555a5ba003207fa6331610a83c46befd8` also passed CI `34200757732` after
its real download-reader conflict retry correction. Actual deployment remains pending;
these HTTP-era green runs do not authorize dispatching the superseded HTTP runtime.

E08.8 local verification passed: 16 receiver/public-readiness contracts including real
TLS trust and hostname rejection, guarded idle-upgrade credential/key preservation,
partial-write recovery and no shared activation on relay failure; all 16 shell
transport scenarios; actual Docker Compose boundary and rejection probes. A synthetic
preconfigured TLS nginx with the real application and TCP relay passed credential-free
readiness, case-insensitive login, repeated authenticated upload/save/history downloads,
and full Fillable restart with identical stored bytes/digests/quota counters. The
synthetic CA was trusted normally in the disposable client; verification was never
disabled. Shared configuration and container identity/start/restart state stayed exact,
including after stopping only the relay. Isolated containers were stopped; persistent
volumes retained. No production app, relay, user or receiver upgrade has run yet.

The existing shared nginx configuration task confirmed its deployed interface and
that no nginx edit/reload is needed; coordination is complete for this unchanged
interface. E08.8 is ready for its own PR/required CI. Application code is unchanged
from E08.6: last measured backend 3970/3999 lines, 1174/1206 branches; frontend
1292/1303 lines, 1500/1569 branches. Exact-head CI must remeasure both before merge.
Next: verify merge, upgrade only the idle private Fillable receiver from merged source,
set the exact HTTPS origin, recheck existing-service baselines, deploy that verified
release through Actions, privately create the requested normal user and complete
E08.5 deployed browser/restart acceptance. Keep shared nginx untouched.


E08.8 verified MERGED: PR #79 at `8497c82bf4fedf2c5b54ee2c1f71b45c9ea317da`.
Required CI `34203848582` passed all three jobs with backend 3970/3999 lines and
1174/1206 branches; frontend 1292/1303 lines and 1500/1569 branches. Real unimported
source probes failed the 90% gates as required. Auto-merge respected strict admin-
enforced `ci-required`; no bypass was used.

The guarded private HTTPS receiver upgrade from that merged source is now verified.
The restricted key passes TLS preflight and rejects arbitrary shell commands. Existing
containers matched exactly before/after; database credentials, SSH authorization,
shared active configuration, edge state and shared Compose bytes were preserved.
The app and relay are still absent. Main CI `34205708238` must pass before the exact
HTTPS source can be dispatched through Actions; no old HTTP source may be deployed.

The user subsequently requested the highest account role. The requested private
account is now prepared as `admin`, superseding normal-user preparation. Preserve
its supplied ten-character password. Create it after verified rollout (or promote
only that account if already present), then verify role through the authenticated
HTTPS session as well as stored account state. No account creation/promotion has
occurred yet. E08.5 now resumes from the merged HTTPS base; deployed acceptance
and its final PR merge remain outstanding.
E08.9 — Portable Docker image identity (in_progress, prerequisite to retry rollout).
Actions deployment `34207568628` failed closed before any Fillable application
containers: the build engine records config digests, while the target's containerd
image store exposes the verified OCI manifest digest as image ID. The archive itself
imports successfully. A retry was cancelled; do not weaken identity checks or change
the server's Docker storage driver. Shared nginx remains unchanged.

Return both config and checked OCI manifest digests from archive validation, select
only an exact loaded immutable identity with matching platform/revision, and record
that host's resolved IDs for Compose and subsequent account/runtime checks. Preserve
all source/archive checks, reject alternate tags/configs/descriptors and prove both
classic and containerd identities. Deliver this correction in its own PR with required
CI and raw 90% gates, then upgrade only the still-undeployed receiver under its lock.

WEF production containers were replaced by concurrent work before Fillable's receiver
step; existing route observations match. Coordinate current owner activity using the
existing shared configuration task, then establish the current stable baseline rather
than rolling back unrelated WEF containers. The user's requested account must have
the highest supported role, admin, with its supplied password preserved; creation and
authenticated role verification remain pending successful rollout.

E08.9 verification: 23 receiver/release contracts passed, including archive-bound
candidate derivation, classic/containerd resolution, wrong digest/platform/revision
rejection and existing malformed OCI/tag/index checks. Real saved local release
images resolved by config digest. Four actual imported target images resolved by
checked OCI manifest digest; bounded read-only-root, network-none disposable image
processes started and their container Image fields matched the resolved IDs. Those
probes were removed; all existing container snapshots were unchanged. No production
app/relay/account exists and no shared ingress change was made.

The shared nginx configuration task confirmed WEF's separate production workflow
completed successfully, current production/shared nginx are healthy, expected routes
answer 200, and no WEF workflow is queued/running at its sample. The historical
candidate edge remains its pre-existing unhealthy baseline and must remain untouched.
Recheck current owner/host state immediately before the later Fillable rollout.

E08.9 is ready for its task PR and required CI. Application source is unchanged;
last exact-main CI `34205708238` passed all jobs with raw backend 3970/3999 lines,
1174/1206 branches and frontend 1292/1303 lines, 1500/1569 branches. Draft E08.5
head `8cb2bb789a3e5405e05e5e13b198ace1fd22ed39` passed CI `34205853855`, but
actual deployed acceptance remains pending. Next: verify this correction's merge,
upgrade only the idle Fillable receiver from that reviewed source, wait for exact-main
CI, then retry Actions with a fresh stable baseline and create/verify the requested
administrator privately. Do not retry the old incompatible receiver or image-ID path.


E08.9 verified MERGED: PR #80 at `141288bcb12215fb34aede79ac2d7b7e799654d3`.
Required CI `34209282057` passed all three jobs and the unchanged raw coverage gates.
The guarded idle receiver update from that exact merged source passed TLS preflight,
rejected arbitrary SSH commands and preserved existing containers, private credentials,
SSH authorization and shared configuration/state/Compose bytes. Main CI `34211072187`
must pass before dispatching the corrected release. The failed old rollout created
no Fillable application containers, and its retry was cancelled. E08.5 resumes from
this merged prerequisite; private admin-role proof passed locally, but actual account
creation, public browser journeys and restart/persistence verification remain pending.


E08.4 final rollout verified: Actions `34215081786` succeeded from protected-main
`141288bcb12215fb34aede79ac2d7b7e799654d3` after exact-main CI `34211072187` passed
all three jobs. The unrelated active WEF release completed before a fresh baseline
and Fillable dispatch. Archive SHA-256 is
`c325afd2ad9984427fa543a2a729db712ef1bff0076f5cd6a4037869fdad0aab` (130,181,120 bytes).
Portable immutable IDs resolved correctly, migrations reached `0013_maintenance_state`,
and private/public HTTPS readiness passed through the existing owner-managed ingress.

E08.5 deployed acceptance passed: the requested administrator was created privately
with its supplied password unchanged, and its HTTPS session role was verified before
and after restart. Authenticated upload/processing/save/history smoke passed. Both
real desktop/mobile bilingual journeys passed with exact template/copy/history bytes
and persisted language, returning the account to Ukrainian. Actual screenshots were
visually inspected. Full Fillable restart preserved 12 retained files, digests and
quota counters; public current-model/revision/full-history comparisons matched both
browser manifests. Four browser-only wrong-badge probes rejected development/wrong
hash values while the real served badge remained `141288b`. All 15 unrelated
containers and six route/HSTS baselines matched after rollout and after restart.
No shared nginx edit/reload or unrelated-service mutation was performed.

See [Deployed acceptance](DEPLOYED_ACCEPTANCE.md) for complete content-free evidence,
coverage and recovery limits. Source coverage remains backend 3970/3999 lines,
1174/1206 branches; frontend 1292/1303 lines, 1500/1569 branches. E08.5's final task
PR #75 remains in_review until its final exact-head required CI and protected merge
are verified. Final merge evidence is recorded in the PR body; no further production
change is required for this acceptance documentation/test delivery.

## E09.1 — Render retained DOCX layout in the editor

Status: in_progress. User-reported real documents exposed a gap between source-preserving export and generic browser rendering. Acceptance: render source fonts, paragraph spacing/indentation, page dimensions/margins, and table sizing/borders in current and historical editors; retain canonical editing identities and save contracts; apply to existing uploads without rewriting originals or revisions. Add synthetic layout/security/round-trip tests, retain independent 90% gates, merge a dedicated PR, then deploy and visually compare the private examples. Floating Word drawing placement and exact automatic pagination require explicit evidence and must not be claimed from content round-trip checks.

E09.1 completion: PR #81 auto-merged as `eb8bc4fdb4023b7a794d0def688a2d3474681079`; PR CI 34228913257 and exact-main CI 34230864623 passed. Actions 34233024911 deployed that source. Both private examples were visually inspected, retained revision bytes verified, and 15 unrelated containers/six routes unchanged. Backend lines/branches 4178/4210 and 1264/1304; frontend 1319/1330 and 1531/1604. Exact Word pagination remains outside the proven layout support.

## E09.2 — Retain outlines and fill boxed dates

Status: in_review. User requests missing outlines and one date entry distributed across boxes. Acceptance: preserve supported paragraph/run and internal table borders; provide a localized single-date action targeting six/eight separated digit positions or selected date-table cells, retaining separators, source identities and cell formatting; validate calendar dates, reject ambiguous/locked selections, support one-step undo/redo and existing save/history contracts. Test synthetic bordered dates with export/reopen and private visual comparison. Deliver a dedicated gated PR and verify Actions deployment last, preserving existing services.

Local Docker verification: 424 backend tests; 4246/4279 lines and 1292/1332 branches. Frontend 236 tests; 99.20% lines and 95.34% branches. Required browser/CI, merge and deployed acceptance remain pending.

E09.2 completion: PR #82 auto-merged as `a5932cb3edad60e96ec3ae3388a565202e0c2b58`; PR CI 34236660133 and exact-main CI 34239106552 passed. Actions 34241492451 deployed that source. Both retained private document versions were verified, live outlines/date controls inspected, and 15 unrelated containers/six routes unchanged. Backend lines/branches 99.23%/97.00%; frontend 99.20%/95.49%.

## E09.4 — Add the Fillable favicon

Status: in_progress. Acceptance: serve a small, crisp document favicon matching the existing blue application mark on all application pages; include it in the production build; verify the asset visually and through the deployed HTML. Deliver a dedicated PR with required CI and unchanged independent 90% coverage gates, then deploy through Actions while preserving shared services. This static asset change needs no new implementation-mirroring tests.

## E09.3 — UI polish: navigation, buttons, and workspace toolbar

Status: in_review. User-reported polish: fix the home button, give the profile link its own place, align buttons across pages, remove the useless "Увійти знову" strip button, and run a full UI diagnosis. Acceptance: the brand in the header is a home link to the library; the signed-in strip keeps identity and logout only while session recovery stays automatic on a rejected protected request; the profile link keeps its own account place on the navigation row with correct current-page state; the workspace toolbar aligns back/title/actions in one row with consistent button sizes; main actions use one primary button style across login, library, profile, and workspace; both catalogs stay complete and the independent 90% gates hold. Deliver a dedicated PR, verify required CI and auto-merge, then deploy and confirm the public origin.

## E09.5 — Center the sign-in card

Status: in_review. User feedback that the login page is not centered. Acceptance: the signed-out sign-in form renders as one centered card below the header on desktop and mobile in both languages, without changing authentication behavior, copy, or tests' semantics. Deliver a dedicated PR with required CI, merge, deploy through Actions, and confirm on the public origin.

## E09.6 — Deploy automatically on merges to main

Status: in_review. User request: make deployment automatic when work merges to `main`. Acceptance: a push to the protected default branch waits for that exact commit's required CI (`ci-required`) and then dispatches the unchanged gated release workflow; a commit whose CI fails, is missing, or is superseded by a newer merge is never deployed; the release gate, artifact transport, and rejection behavior are unchanged and pinned by a required contract test; documentation agrees. Deliver a dedicated PR with required CI, merge, and verify the first automated rollout on the public origin.

## E09.7 — Automatic Dependabot updates with automerge

Status: in_review. User request: implement automatic Dependabot updates with automerge. Renumbered from a provisional E09.6 ID that the merged deploy-automation task took. Acceptance under D025: weekly Dependabot version updates cover GitHub Actions workflows, the frontend npm manifest, `infra/` Dockerfiles, and root Docker Compose files, with minor/patch updates grouped per ecosystem and major updates standalone; a dedicated workflow enables squash auto-merge only on `dependabot[bot]` pull requests, armed on the exact head commit; every automatic merge still passes the strict up-to-date `ci-required` gate; as under E09.6, the merged commit then deploys automatically once its exact-commit CI is green. Backend Python dependencies stay on the manual pip-tools procedure because the hash-pinned `requirements.lock` is not a Dependabot-recognized manifest; that limitation is recorded in D025 and [CI and deployment](CI_CD.md). Deliver a dedicated PR with required CI and unchanged independent 90% gates, then verify Dependabot's first update run on the repository.

Configuration and documentation only; no application source changes, so coverage is unchanged and no new implementation tests are required. Local validation passed: YAML parsing of both new files, dependabot.yml checked against the SchemaStore v2 schema, actionlint on the new workflow, Markdown link/fence checks on the three updated documents, and `git diff --check` cleanliness. Required CI on the PR reruns the full backend/frontend suites and gates unchanged.

## E09.8 — Parallel required CI jobs and concurrent release image builds

Status: in_progress. The single sequential `checks` job made every PR wait for the sum of image builds, lints, both test suites, browser flows, development verification and contract tests, with a 30-minute ceiling. Acceptance: split static checks and tests into independent parallel jobs (`lint`, `backend-tests`, `frontend-tests`, `browser`, `development`, `contracts`) beside the unchanged `upgrade-checks`; keep the independent raw 90% line/branch gates, source provenance binding, both real unimported-source negative probes and fail-closed `ci-required` aggregation over all seven job results; update the deployment gate and its contract tests to the exact new job set and build the two release images concurrently; keep the E09.6 deploy-main dispatcher, E09.7 Dependabot automerge and their contract tests required (in the `contracts` job) and unchanged; keep branch protection on the single `ci-required` context and update AI documentation. No threshold, exclusion, or required check may be relaxed.

## E09.9 — Restore the deploy-dispatch contract in the split CI

Status: in_review. E09.8's CI split dropped `scripts/test_deploy_dispatch_contract.py` from required CI while the script and the E09.6 dispatcher stayed in use. Acceptance: the dispatch-dispatcher contract test runs again inside the required `contracts` job against the checked-out source, keeping the deploy-on-merge behavior pinned. Deliver a dedicated PR with required CI; the merge itself then deploys automatically through the E09.6 dispatcher.

## E09.10 — Dependabot updates for backend Python dependencies

Status: in_review. Follow-up to E09.7 and the user request to update Python dependencies the same way as the sibling WEF/estate_test repository: cover backend Python dependencies through the Dependabot `pip` ecosystem. Acceptance: the pip-compile lockfile lives at the Dependabot-recognized path `backend/requirements.txt` (renamed from `requirements.lock` with the Docker install path updated and the header normalized by a real pip-tools 7.5.3 recompile in the digest-pinned base image); `dependabot.yml` gains a grouped `pip` entry for `/backend`; hash-pinned `--require-hashes` installation is unchanged and remains enforced by the Docker build; D025 and [CI and deployment](CI_CD.md) no longer record a Python exclusion; both ecosystems' PRs flow through the existing squash automerge and `ci-required` gate. Configuration/rename only — no application source changes, so coverage is unchanged; the backend test image build validates the renamed lock locally, and required CI reruns all suites and gates.

## E09.11 — Dependabot automerge branch reconciliation

Status: in_review. The first Dependabot wave showed the automerge workflow arming every pull request but none of them merging: `main` protection requires branches to be up to date, Dependabot rebases only on conflict, and every merge to `main` re-staled the remaining pull requests, which then sat behind with stale green checks indefinitely. Acceptance: `.github/workflows/dependabot-automerge.yml` also updates a behind Dependabot branch through the update-branch API bound to the expected head SHA (letting the resulting synchronize event arm the new head) and reconciles all open Dependabot pull requests after every push to `main` plus a twice-hourly offset schedule fallback — updating behind branches and arming squash auto-merge on pull requests that are neither armed nor carrying failed/cancelled checks, so remaining updates follow each merge with one required-CI cycle; the trust contract is unchanged (`pull_request_target` from the trusted base, no checkout, repository + author guards, only `contents: write`/`pull-requests: write`, no deployment dispatch, merges still gated by strict up-to-date `ci-required`); `scripts/test_dependabot_automerge_contract.py` pins the contract in the required `contracts` job; D025 and [CI and deployment](CI_CD.md) record the reconciliation behavior. Workflow/configuration and contract test only — no application source changes, so coverage is unchanged; the required CI run re-runs all suites and gates. Delivered as #103; follow-ups: #104 moved the fallback cron from `*/30` to `13,43 * * * *` after GitHub's scheduler produced no runs at the packed `:00`/`:30` slots (the repository's Actions history records zero `schedule` runs), and the reconciliation then became push-driven on `main` so no scheduled run is required for convergence.

## E09.12 — Stabilize the history restore browser check

Renumbered from a provisional E09.10 ID now used by the merged Dependabot Python task. Status: in_review. CI run 34259413491 flaked in the required browser job: after accepting the restore confirm, the desktop history check waited only five seconds for the toolbar button that reappears when the panel closes, so a missed dialog or a slow restore surfaced as an unrelated visibility failure and blocked `ci-required` and that cycle's automated deployment (identical browser content passed in the adjacent runs). Acceptance: the restore must be confirmed through the document endpoint before the panel-close assertion runs, keeping every original assertion and producing a direct failure if the restore does not happen. Test-only change; the independent 90% gates, catalogs and deploy behavior are untouched.

## E10 — Manual QA findings and corrections

Outcome: the issues found by the 2026-09-08 comprehensive manual test ([QA findings](QA_FINDINGS_E10.md)) are fixed or explicitly dispositioned, and the manual checks that could not run are completed. Each finding below cites its evidence in that document. Deliver every task in its own branch and PR per the standing workflow; after each merge the deployment automation ships it, so keep the independent 90% gates and catalogs intact.

Work:

- E10.1: Enforce the ≥10-character password minimum everywhere credentials are set: the profile password-change endpoint, the account provisioning command, and the account reset command. Acceptance: a 9-character password is rejected by all three paths with a localized, machine-readable error, a 10-character password is accepted, backend tests cover both boundaries on each path, and the profile form's error message renders in both catalogs. Fixes [QA findings](QA_FINDINGS_E10.md) F1.
- E10.2: Keep the workspace settings panel open while the user works. Acceptance: the expanded settings section does not collapse on its own across background refresh cycles (editing-lease renewal, processing poll, storage usage poll); open state and in-progress input survive at least one lease renewal and one autosave; a browser check holds the panel open for 60+ seconds with autosave and lease activity; first reproduce against a clean `main` checkout and record the root cause (suspected remount of `WorkspaceSettings` or its parent by a periodic refetch). Fixes F2.
- E10.3: Reflect undo/redo availability in the toolbar buttons. Acceptance: "Скасувати"/"Повторити" are disabled when no undo/redo exists (fresh open, and after undoing everything), enable after the applicable edit, and stay consistent after save, autosave, and history restore; covered by component/browser assertions in both locales. Fixes F3.
- E10.4: Bring login error feedback into the catalogs and near the card. Acceptance: empty-submit validation shows app-localized inline messages (no reliance on native browser bubbles) in the active UI language; the invalid-credentials alert renders inside or directly above the sign-in card without shifting the page layout; desktop/mobile screenshots in both locales. Fixes F4 and F5.
- E10.5: Complete the storage audit trail. Acceptance: original uploads, use-template copies, and restores produce audit rows; deletion events record the authenticated actor that issued the request; existing diagnostics/audit tests extend without weakening content-free logging rules. Fixes F6.
- E10.6: Enrich 422 `invalid_request` error payloads with the offending parameter name in `parameters` (no submitted values, no internal messages), regenerate the OpenAPI/TypeScript contract, and use the detail in localized presentation where available. Fixes F7.
- E10.7: Complete the manual checks listed as pending in [QA findings](QA_FINDINGS_E10.md) (profile GUI, delete confirmation dialog, use-template click-through, history panel interactions, manual-save failure presentation, English-locale and mobile-viewport passes) and record newly found issues in that document with evidence. Add the favicon `.ico`/`.png` fallback (F8) alongside this pass if E09.4 has not already delivered it.

Acceptance:

- Every finding F1–F8 in [QA findings](QA_FINDINGS_E10.md) is fixed by its task above or dispositioned in this ledger with the user's accepted reason.
- The pending manual pass (E10.7) is executed on a clean checkout, its results recorded, and any new issues get their own tasks.
- Required CI (including the independent 90% gates and catalog completeness) passes on each task PR; merges deploy through the existing automation.

2026-09-08: E10 added after a comprehensive manual test pass (browser GUI + direct API probing) recorded in [QA findings](QA_FINDINGS_E10.md) on branch `task/e10-manual-qa-findings`. Confirmed: missing ≥10-character password minimum in the password-change API and the provisioning CLI (F1); workspace settings panel self-collapse (F2); undo/redo enabled with empty history (F3, confirmed in committed sources); login alert placement and native-validation i18n (F4/F5); storage audit gaps for upload/copy/restore and NULL deletion actor (F6); opaque 422 payloads (F7); SVG-only favicon (F8). Verified correct: two-way sidebar/document sync, field navigation and highlighting, zoom, autosave and revision creation, restore byte-identity/idempotency/provenance, copy idempotency, cross-user isolation, CSRF/Origin enforcement, login rate limiting, quota enforcement and reservation cleanup, upload validation matrix. Pending GUI checks (browser automation input failure mid-session) are tracked as E10.7. Environment notes: the shared checkout carried another agent's uncommitted checkbox work whose production build currently fails (`tsc` TS2339 in `adapter.ts`) — not a `main` defect; a concurrent test process uploaded a document into the `qa-main` account before its password was rotated. Documentation-only change; no application tests or coverage claimed.
