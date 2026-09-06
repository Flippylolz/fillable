# Project guide

Last updated: 2026-09-06.

Fillable is a self-hosted application for editing Word documents with a synchronized sidebar of detected fields.

## Current state

- Git repository initialized with empty base commit `3820bff`; [P00 planning PR](https://github.com/Flippylolz/fillable/pull/1) delivers the planning files through `task/p00-mvp-plan`. Its GitHub state and PR body record actual merge evidence.
- Product direction, application stack, local storage, and Docker-based development agreed.
- MVP contains four pages: login, library with templates/results, simple profile, and document workspace with settings, field sidebar, and version-history UI.
- CI must block below 90% coverage. Deployment is final epic E08 through GitHub Actions to `<DEPLOY_USER>@<DEPLOY_HOST>`, using a new port and shared nginx while preserving existing services.
- Documentation only: no application, migrations, Compose configuration, or executable test suite exists yet.
- The editor must use free components; a project-owned implementation is an allowed fallback. Selection and DOCX fidelity remain E00 work.
- AI is outside MVP. Detection uses rules, existing controls, review, and manual fields. A possible Groq/free-allowance feature is deferred.
- Local and production environments only; no backups. Persistent data and version-history UI remain required.
- Production URL: `http://<DEPLOY_HOST>:<PORT>`, served through shared nginx on a new public port; the numeric port is pending inspection. Supplied connection values are retained in ignored `AI/DEPLOYMENT.local.md` and are not published in this repository.
- GitHub repository: [Flippylolz/fillable](https://github.com/Flippylolz/fillable), created by the user; local `origin` points to it. The public repository was empty before the documented P00 history bootstrap on 2026-09-06.
- Application CI is not implemented. Classic branch protection and rulesets were checked on 2026-09-06 and were absent; E01 must establish required coverage checks before any application PR merges. No deployment or server inspection has occurred.
- Every task must use its own branch and PR. GitHub auto-merge is enabled at repository level; agents enable it separately for each ready PR after verifying the required merge gates.

## Documentation map

| Document | Purpose |
| --- | --- |
| [Product](PRODUCT.md) | Four MVP pages, templates/results, version history, and success criteria |
| [Decisions](DECISIONS.md) | Accepted choices, proposed defaults, and open decisions |
| [Architecture](ARCHITECTURE.md) | Components, data ownership, editing, and processing |
| [Editor feasibility](EDITOR_FEASIBILITY.md) | Free-component research, custom-editor fallback, and required DOCX proof |
| [Local development](LOCAL_DEVELOPMENT.md) | Docker development and server deployment requirements |
| [CI and deployment](CI_CD.md) | Blocking coverage gates, GitHub Actions, and the final deployment task |
| [Deployment target](DEPLOYMENT_TARGET.md) | Supplied SSH target, shared nginx/possible WEF ownership, port selection, and service isolation |
| [Storage quotas](STORAGE_QUOTAS.md) | Local file storage and configurable per-user allowances |
| [Epics](EPICS.md) | Ordered implementation work and acceptance criteria |
| [Agent rules](AGENT_RULES.md) | Instructions for automated implementation and handoffs |
| [PR workflow](PR_WORKFLOW.md) | One branch/PR per task, auto-merge, CI prerequisites, and merged-state verification |

## Starting implementation

Read the decisions and the relevant epic before changing code. E01 establishes the Docker foundation. E00 resolves editor feasibility and licensing; editor-dependent epics require that decision. E01 and the editor-independent parts of the storage and account work can proceed while the editor is being evaluated.

Use the epic status table as the implementation ledger. Record completed work and evidence there; do not infer implementation from the existence of these planning documents.

E01 establishes coverage-enforced CI early. E08 deploys last, after E00–E07 pass and access/routing on the supplied server are verified. Server inspection and deployment have not begun; no live server is needed to start development.
