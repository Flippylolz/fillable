# Autonomous implementation prompt

Use the following instructions when starting an implementation agent for Fillable. Preparing this file does not start an agent or schedule background work.

## Objective

Implement and deliver the agreed Fillable MVP in `https://github.com/Flippylolz/fillable`, completing the remaining tasks in [Epics](EPICS.md). Continue autonomously through implementation, verification, individual task PRs, and the final GitHub Actions deployment. Ask me for input only when progress requires something you cannot safely obtain or decide within the agreed scope.

Work in the existing Fillable checkout and verify its `origin` points to the repository above. If running elsewhere, use the equivalent checkout of the same remote. Do not create another repository. This is an instruction to execute the roadmap, not produce another plan and wait for permission to start.

## Establish the actual state

1. Read root `AGENTS.md`, then [Agent rules](AGENT_RULES.md), [Project guide](README.md), [Decisions](DECISIONS.md), [Product](PRODUCT.md), [Epics](EPICS.md), and [PR workflow](PR_WORKFLOW.md). Follow their task-specific reading instructions, including architecture, Docker, CI, quotas, localization, editor feasibility, test corpus, version badge, and deployment constraints.
2. Inspect Git status, remote/base commits, open PRs, CI results, and the execution ledger. Preserve existing changes and resume unfinished task work before creating duplicates. Resolve stale ledger entries from verified GitHub merge evidence.
3. At this prompt's preparation, only planning documents and the synthetic Ukrainian DOCX baseline exist; no application or executable CI has been scaffolded. Verify this before acting because another agent may have advanced the project. E00.1's generated fixture already exists; do not redo it or wait for unavailable real documents.
4. Start with E01.1 if still outstanding, establishing the Docker app/test foundation and minimum merge gate. E00.2's free-editor evaluation can proceed independently; runtime editor prototypes require the same application CI discipline. Complete E00 before editor-dependent implementation. Follow dependencies rather than task-number order alone.

## Autonomous delivery loop

- Select one ready task, confirm its bounded acceptance criteria, and implement it with necessary tests and documentation. If it needs splitting, record named subtasks and dependencies first; give each its own PR. Resolve ordinary implementation details using the accepted decisions and a small, maintainable design.
- Use current `origin/main` after prerequisites merge, with a dedicated task branch. Keep unrelated user work intact. Do not combine an entire epic into one PR or push task implementation directly to `main`.
- Run the relevant Docker checks, inspect failures, fix the cause, and repeat affected checks until they pass. Use meaningful behavior/integration/browser checks; do not inflate coverage with trivial assertions or exhaustive tests of styling constants. Verify DOCX structure, editor reopening, and visual fidelity separately, stating which evidence is available.
- Establish working CI and required GitHub branch checks before the first application PR merges. The minimum gate is part of the initial scaffold; later E01 verification tasks are not permission to postpone it. Verify the actual repository settings through available authorized tools and configure the scoped required checks when access permits.
- Require at least 90% line AND branch coverage independently for frontend and backend, including eligible unimported source. Missing reports and failed/skipped/cancelled required jobs must fail. Do not lower thresholds, broaden exclusions, add fake passing checks, or use administrator overrides. Documentation-only tasks do not invent coverage measurements.
- Open/update the task PR with a clear outcome, actual validation, measured coverage where applicable, and dependencies. Routine branches, commits, pushes, PRs, and per-PR auto-merge are already authorized; do not ask me to approve them again.
- Verify the PR head and real merge gates, then enable squash auto-merge. Follow CI and review feedback, fix actionable issues within scope, and confirm the PR actually merged. Auto-merge availability alone does not enforce coverage; leave a code PR unmerged while required protection is missing and work to establish it.
- Record task status, PR URL, merge commit, checks, measured coverage, limitations, and next action in `AI/`. Record a task's own final merge hash in its PR body first, then carry it into the ledger in the next task PR. An open PR is `in_review`, not `done`.
- Synchronize after merge and immediately continue to the next ready task. Do not stop after a plan, successful local test, PR creation, or individual task completion to ask whether to continue. If CI or one dependency is pending, advance safe independent work without starting dependent changes prematurely.

## Keep the accepted scope

- React/TypeScript/Vite frontend; Python/FastAPI backend and Python workers; PostgreSQL and Redis/RQ. Node is frontend tooling only. Development, builds, migrations, and tests run through Docker with pinned dependencies and lockfiles.
- Store documents on the local server filesystem. Enforce configurable default per-user disk allowances and operator overrides across all retained writes. No S3, MinIO, paid services, backups, or persistent staging; local and production remain the persistent environments. Preserve volumes, originals, safe writes, and crash recovery.
- Deliver the four pages: login; library with uploads, templates, processed documents, and downloads; simple profile; document workspace with direct editing, settings, synchronized fields, and version-history UI. Preserve template independence and restore history as a new revision. Do not replace the editor with a read-only preview.
- Use only free editor components and import/export paths. Evaluate current official licensing/API evidence and prove compatibility against the corpus. A project-owned editor/adapter is allowed. Do not adopt paid-required APIs, silently narrow editing requirements, or claim universal DOCX fidelity. Do not change the project's own license merely to accommodate a dependency without resolving that owner decision.
- AI/model calls and provider integration are outside the application MVP. Do not implement Groq, provider scaffolding, API-key settings, or usage UI now. The future AI idea does not block deterministic detection.
- Prioritize Ukrainian document content and Unicode fidelity. Ukrainian UI is default, English secondary; store all application copy in i18n and persist the profile language. Follow the documented version-badge design and its narrow exact-visible-text exception. UI language changes must preserve document text, field labels/values, and drafts.
- Keep private deployment identity in the ignored local configuration or available authorized environment. Do not publish it, credentials, private documents, or secret values in tracked files, PRs, or logs. Read configuration selectively; never dump the environment to diagnose missing access.

## Deployment is last

E08 starts only after E00–E07 pass. The user has already requested deployment through GitHub Actions to the supplied server; supplying its address does not authorize deploying early. When E08 becomes ready, proceed with the agreed deployment and its verification without adding an arbitrary final confirmation step.

Read [Deployment target](DEPLOYMENT_TARGET.md) and the ignored `AI/DEPLOYMENT.local.md` or configured environment for actual access details. Start with read-only preflight. Discover a new unused public port and the shared nginx's real configuration owner; investigate WEF rather than assuming it owns nginx. Use the D024 HTTPS hostname/port origin and a private Fillable upstream. Preserve every unrelated service, route, volume, and existing listener.

The shared owner has already deployed TLS 3200. Contact its configuration task before ingress changes; none are required for application rollout. Validate effective nginx read-only and preserve it unchanged. Do not restart shared Docker/nginx, prune host-wide resources, or take ports 80/443. Deploy verified immutable artifacts through Actions, check the badge against their source commit, verify persistence and MVP smoke flows, and compare existing-service checks before/after. Use the documented schema-aware, scoped recovery process; do not invent backups or delete data to recover a release.

## When my input is necessary

Before asking, inspect the relevant docs, code, PR/check output, and available authorized configuration; diagnose the actual failure and try reasonable safe alternatives. A difficult bug, failed test, missing representative document, routine dependency/version choice, or cosmetic preference is not by itself a reason to stop.

Ask only when an unavoidable dependency remains, for example:

- Credentials, account access, or permission must be supplied or granted by me and are unavailable through existing authorized access.
- Proven editor or infrastructure limitations require changing an accepted requirement, adding cost, or making an owner-level licensing decision that has not been delegated.
- The next necessary action would destroy valuable data or alter unrelated services beyond the agreed deployment scope, and no safe in-scope alternative exists.
- A tool or approval system prevents the needed action after legitimate safer alternatives have been exhausted. Do not bypass its boundary.

If the issue blocks only part of the roadmap, record it and keep working on independent ready tasks. Ask early if my response can unblock work, but stop all work only when no useful authorized progress remains. Never treat silence or elapsed time as approval.

Make the request concise: state the exact blocked task, evidence/cause, what you tried, the smallest action or decision needed from me, and your recommended resolution. If a rule or automatic approval review is the reason, identify the exact source and its relevant restriction. Do not re-ask settled product questions or request secrets in a public artifact; use the appropriate private configuration channel.

## Progress, interruption, and completion

Keep updates brief and factual: meaningful outcome, current task, and any material blocker. Updates should not repeatedly ask for permission. Do not start recurring automation, additional agents, or separate tasks merely because this prompt requests autonomous execution; those need their own user instruction.

Maintain a resumable checkpoint in `AI/EPICS.md`: task/branch/PR, last verified commit, tests already run and results, pending CI or external dependencies, and the exact next action. After an interruption, inspect live state and continue from that checkpoint without duplicating PRs or discarding work. If the environment cannot continue execution, report that limitation honestly; do not claim to be working in the background without an actual running mechanism.

The objective is complete only when all required tasks are verified and merged, E00's free editor proof is documented, MVP flows and required coverage/CI pass, local Docker instructions match tested behavior, and the final Actions deployment and existing-service checks succeed. Do not mark an epic done from documentation, mocks, an unmerged PR, or an untested deployment workflow. If a real external blocker prevents completion, leave the remaining work explicitly unfinished with the minimal user action and a concrete resumption step.
