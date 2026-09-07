# Project guide

Last updated: 2026-09-07.

Fillable is a self-hosted application for editing Word documents with a synchronized sidebar of detected fields.

## Current state

Fillable implements login, library, profile and a document workspace with direct
editing, synchronized fields, settings, autosave and retained version history.
Ukrainian is the default UI language and English is persisted per account. The
Docs-like workspace and locale-aware storage displays are verified on desktop/mobile.

E00–E07 are merged. E07 has verified bilingual MVP flows, session recovery,
content-free diagnostics, bounded scheduled maintenance and a previous-image upgrade/
full-stack crash proof. Runtime isolation, documentation and the final gate audit are
merged. E08.1 is inspecting the supplied server and preparing HTTP ingress on port 3200. [Epics](EPICS.md) contains exact PR, commit and check evidence.

- The free ProseMirror/Python adapter preserves supported source DOCX structures,
  originals and revision-matched review metadata. See [Editor feasibility](EDITOR_FEASIBILITY.md)
  for tested limits; it does not promise universal Word layout fidelity.
- Detection is deterministic, with existing controls, suggestions and manual review.
  AI/provider integration is outside MVP.
- All retained writes use local quota-enforced storage. Copies are independent,
  restores create new revisions, and retention keeps everything unless configured.
  Local and production are the only persistent environments; backups are excluded.
- Docker is the development, verification and deployment runtime. Required CI checks
  enforce raw >=90% lines and branches independently for frontend/backend. The
  aggregator requires both standard checks and the separate upgrade/recovery job.
- [The version badge](VERSION_BADGE.md) shows the built source commit or `development`
  with its specified fixed appearance and click-through behavior.
- Every task has its own PR and verified exact-head auto-merge. Actual strict main
  protection includes administrator enforcement.
- E08 deploys through Actions to `http://<DEPLOY_HOST>:<PORT>` on new shared-nginx
  ingress while preserving existing services. Read-only supplied-server preflight and isolated port probes have started;
  application deployment has not occurred. Private connection values stay in ignored local configuration.
- Repository: [Flippylolz/fillable](https://github.com/Flippylolz/fillable).

Start with [Docker development](LOCAL_DEVELOPMENT.md), including explicit account
provisioning and isolated fresh/recovery verification commands.

## Documentation map

| Document | Purpose |
| --- | --- |
| [Diagnostics](DIAGNOSTICS.md) | Content-free job/capacity/audit operator commands |
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

E01 establishes coverage-enforced CI early. E08 deploys last, after E00–E07 pass and access/routing on the supplied server are verified. Server preflight is underway in E08; application deployment is not yet complete.

- [Scheduled maintenance](MAINTENANCE.md): bounded reconciliation, retention and failure state.

- [Application restart and upgrade](APPLICATION_RECOVERY.md): synthetic previous-image and crash verification.
