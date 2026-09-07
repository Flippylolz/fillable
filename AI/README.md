# Project guide

Last updated: 2026-09-06.

Fillable is a self-hosted application for editing Word documents with a synchronized sidebar of detected fields.

## Current state

- Git repository initialized with empty base commit `3820bff`; [P00 planning PR](https://github.com/Flippylolz/fillable/pull/1) delivers the planning files through `task/p00-mvp-plan`. Its GitHub state and PR body record actual merge evidence.
- Product direction, application stack, local storage, and Docker-based development agreed.
- MVP contains four pages: login, library with templates/results, simple profile, and document workspace with settings, field sidebar, and version-history UI.
- UI localization is required in MVP: Ukrainian by default, English as secondary, all application copy in i18n catalogs, and a saved language switcher in the profile. See [Localization](I18N.md); changing UI language preserves original document content.
- MVP includes a fixed, translucent, noninteractive [Git version badge](VERSION_BADGE.md) showing the deployed commit's first seven characters or `development`. The supplied design is implemented and browser-verified in E01.8.
- CI must block below 90% coverage. Deployment is final epic E08 through GitHub Actions to `<DEPLOY_USER>@<DEPLOY_HOST>`, using a new port and shared nginx while preserving existing services.
- E00–E02 are verified and merged, including the free editor proof, Docker/CI foundation, accounts, profile, and quota-enforced storage. E03 has verified upload validation/persistence, the library, saved downloads and deletion. Persisted workspace entry, durable upload processing/status and independent template copies are merged. Field-discovery schemas are in progress; discovery/review, safe saves/history and deployment remain. See the execution ledger for exact task/PR evidence.
- Documents are primarily Ukrainian. [Test corpus](TEST_CORPUS.md) provides an initial generated fixture and expected outcomes while real examples are unavailable.
- D008 selects the proven free ProseMirror/Python source-package adapter. Its tested support matrix and explicit limitations are recorded in Editor feasibility. Production workspace/save integration remains later work.
- AI is outside MVP. Detection uses rules, existing controls, review, and manual fields. A possible Groq/free-allowance feature is deferred.
- Local and production environments only; no backups. Persistent data and version-history UI remain required.
- Production URL: `http://<DEPLOY_HOST>:<PORT>`, served through shared nginx on a new public port; the numeric port is pending inspection. Supplied connection values are retained in ignored `AI/DEPLOYMENT.local.md` and are not published in this repository.
- GitHub repository: [Flippylolz/fillable](https://github.com/Flippylolz/fillable), created by the user; local `origin` points to it. The public repository was empty before the documented P00 history bootstrap on 2026-09-06.
- E01.1 implements application coverage CI. Actual `main` protection now requires up-to-date `ci-required` from GitHub Actions, including administrators, before the first application merge. No deployment or server inspection has occurred.
- Every task must use its own branch and PR. GitHub auto-merge is enabled at repository level; agents enable it separately for each ready PR after verifying the required merge gates.

## Documentation map

| Document | Purpose |
| --- | --- |
| [MVP acceptance](MVP_ACCEPTANCE.md) | Four-page workflow and verification evidence |
| [Product](PRODUCT.md) | Four MVP pages, templates/results, version history, and success criteria |
| [Decisions](DECISIONS.md) | Accepted choices, proposed defaults, and open decisions |
| [Architecture](ARCHITECTURE.md) | Components, data ownership, editing, and processing |
| [Authentication](AUTHENTICATION.md) | Local accounts, sessions, CSRF/origin protection, private provisioning and verification |
| [Library](LIBRARY.md) | Upload/list UX and readable localized storage sizes |
| [Document persistence](DOCUMENT_PERSISTENCE.md) | Owned originals, revisions, saved downloads and durable deletion |
| [Processing](PROCESSING.md) | Durable job intent, bounded dispatch/worker and recovery |
| [Workspace](WORKSPACE.md) | Persisted editor entry, local drafts and navigation guards |
| [Saved history](HISTORY.md) | Owned revision list/preview APIs and history delivery boundaries |
| [Localization](I18N.md) | Ukrainian/English catalogs, saved profile language, formatting, and acceptance checks |
| [Version badge](VERSION_BADGE.md) | Supplied desktop/mobile styling, build commit metadata, fallback, and click-through behavior |
| [Editor feasibility](EDITOR_FEASIBILITY.md) | Free-component research, custom-editor fallback, and required DOCX proof |
| [Test corpus](TEST_CORPUS.md) | Ukrainian synthetic DOCX, answer key, verification evidence, and future sample updates |
| [Local development](LOCAL_DEVELOPMENT.md) | Docker development and server deployment requirements |
| [CI and deployment](CI_CD.md) | Blocking coverage gates, GitHub Actions, and the final deployment task |
| [Deployment target](DEPLOYMENT_TARGET.md) | Supplied SSH target, shared nginx/possible WEF ownership, port selection, and service isolation |
| [Storage quotas](STORAGE_QUOTAS.md) | Local file storage and configurable per-user allowances |
| [Epics](EPICS.md) | Ordered implementation work and acceptance criteria |
| [Agent rules](AGENT_RULES.md) | Instructions for automated implementation and handoffs |
| [Autonomous agent prompt](AUTONOMOUS_AGENT_PROMPT.md) | Ready-to-use implementation mandate, task/PR loop, escalation conditions, and resumption guidance |
| [PR workflow](PR_WORKFLOW.md) | One branch/PR per task, auto-merge, CI prerequisites, and merged-state verification |

## Starting implementation

Read the decisions and the relevant epic before changing code. E01 establishes the Docker foundation. E00 resolves editor feasibility and licensing; editor-dependent epics require that decision. E01 and the editor-independent parts of the storage and account work can proceed while the editor is being evaluated.

Use the epic status table as the implementation ledger. Record completed work and evidence there; do not infer implementation from the existence of these planning documents.

E01 establishes coverage-enforced CI early. E08 deploys last, after E00–E07 pass and access/routing on the supplied server are verified. Server inspection and deployment have not begun; no live server is needed to start development.
