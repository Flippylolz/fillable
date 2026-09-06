# Architecture

Status: target design; not implemented.

## Components

| Component | Responsibility |
| --- | --- |
| React application | Login, template/document library, profile, and workspace with settings, fields, and version history |
| Embedded editor | Working document state, selection, editing transactions, undo/redo, DOCX import/export |
| FastAPI application | Authentication, profile, templates/documents, field definitions, version history/restoration, and quota enforcement |
| Python document package | DOCX inspection, deterministic candidates, validation, editor-independent field schemas |
| RQ worker | Deterministic detection, retained exports, cleanup, and reconciliation |
| PostgreSQL | Users, sessions, document/version records, field metadata, quota accounting, durable job state |
| Redis | RQ transport and worker coordination; not the authoritative document or quota store |
| Local filesystem | Immutable document versions, originals, retained outputs, bounded staging files |
| Fillable nginx gateway | Same-origin app routing and production static frontend assets on a private upstream port |
| Existing shared nginx | Public HTTP listener on Fillable's new port, potentially configured in WEF; outside Fillable's service lifecycle |

Locally, the browser talks to the project-owned nginx gateway, which routes `/api` to FastAPI and frontend requests to containerized Vite. In production, the existing shared nginx listens at `http://<DEPLOY_HOST>:<PORT>` and routes to the isolated private Fillable gateway, which serves built static assets and proxies `/api`. Distinguish the public nginx listener from the private upstream port/network. User files are never served from a public static directory. Shared ingress ownership/networking is verified during E08, including whether WEF manages it.

The page contract lives in [Product](PRODUCT.md). Operators provision accounts and configure quotas through containerized maintenance commands using the same Python services. The MVP has no administrator dashboard; history is a panel in the document workspace.

## Planned repository layout

```text
AI/                     Project knowledge and implementation ledger
frontend/               React application and browser tests
backend/                FastAPI app, worker, domain packages, migrations, tests
fixtures/               Synthetic DOCX files and expected outcomes
infra/                  Dockerfiles and project-owned nginx gateway configuration
compose.yaml            Shared service definition
compose.dev.yaml        Development overrides
compose.prod.yaml       Production overrides
.github/workflows/     CI early; deployment workflow in final epic E08
.env.example            Documented, non-secret configuration template
```

Only `AI/` and root discovery/configuration files exist at this stage. Future implementation should use these paths unless a documented practical reason requires adjustment.

## Data model boundaries

- `User`: identity, display name, credential hash, role, status, nullable quota override.
- `Session`: server-side authenticated session and expiry.
- `Document`: owner, kind (`template` or `document`), title, current version, lifecycle state, editing lease, optional source-template provenance.
- `DocumentVersion`: immutable revision, file reference, matching field-schema snapshot, parent revision, creation time, optional restored-from revision.
- `StoredFile`: owner, server-generated storage key, byte size, digest, lifecycle state, purpose.
- `FieldDefinition`: logical key, label, type, validation, review status.
- `FieldOccurrence`: one location/control in one document version, associated with a logical field.
- `DetectionCandidate`: source revision, location evidence, proposed type/label, review status.
- `QuotaAccount` and `StorageReservation`: used/reserved bytes and operation-bound allocations.
- `Job`: owner, operation, source revision, status, retry state, and result reference.

The database is the authority for permissions and committed versions. A version must not claim a field snapshot from a different DOCX revision. Original uploads are retained unchanged.

## Template instantiation

1. Authorize access to the source template and capture its saved revision, not an unsaved editor buffer.
2. Reserve space and create a new owner-scoped document with an independent file and field-schema snapshot through the storage service.
3. Scope logical field keys and occurrence mappings to the new document. Filling the copy must never update the template's values.
4. Commit the new record, file, and schema consistently, then open it in the document workspace. Retrying the request returns the same created document.
5. Keep source revision/title information as provenance, not a live content dependency. Template changes/restoration/deletion must not cascade into existing documents or make their files unavailable.

Both templates and documents appear in the one library page with separate tabs. Processing/job status is distinct from the existence of a saved downloadable revision; it is not a completion assessment of user-entered fields.

## Version history and restoration

- Expose an owner-authorized list of retained revisions with creation time and current-version marker for each template/document.
- Historical preview is read-only and loads the exact selected DOCX with its field-schema snapshot. Download likewise addresses that revision explicitly.
- Preserve the current working draft when entering history; require an explicit save or discard decision before restoration could replace unsaved edits. Opening a historical preview must not autosave it over the current document.
- Restore through the ordinary revision-checked save service. Create a new current revision with the selected content and fields, a parent pointing to the previously current revision, and restored-from provenance.
- Keep later retained revisions intact. A stale client, failed copy, or insufficient quota leaves the current version unchanged.
- Restores allocate their new file through the quota/storage service and are idempotent. Restoration of a template does not propagate to existing derived documents.
- Make retention policy visible in the panel and coordinate pruning with active preview/download/restore operations. Advanced diffing and branching are outside MVP.

## Document and sidebar synchronization

1. Open a saved version and acquire an editing lease. A second session receives an explicit conflict or read-only state.
2. Load editor field occurrences and reconcile them against that version's field schema.
3. Sidebar updates go through editor transactions using stable occurrence identities.
4. Editor change events refresh sidebar values and active-field selection.
5. The live editor document is the authority for the working draft. Sidebar state is derived from it; it is not a second independent document.
6. Guard event origin and transaction identity to prevent feedback loops. Preserve focus, input composition, and undo grouping.
7. Linked occurrences update in one logical operation. Pre-existing inconsistent values require review; do not pick an arbitrary winner.
8. Deleting or invalidating a control marks its occurrence missing. Never silently remap it by matching similar text.
9. Save an immutable DOCX and its matching field snapshot. Reject a stale base revision instead of overwriting another save.

The editor adapter should cover only operations the product needs: load, export, enumerate/create/read/update/focus controls, subscribe to changes, and expose revision state. Do not build a speculative universal editor framework.

The editor and its required import/export path must be free under D008. [Editor feasibility](EDITOR_FEASIBILITY.md) records a project-owned adapter/editor fallback using open components. Preserve the source DOCX package and untouched parts when implementing that fallback; define supported editable regions through evidence rather than silently dropping unsupported Word structures.

## Detection

- Use deterministic extraction of existing controls, explicit placeholders, and rule-based blank candidates; no AI or model inference is part of MVP.
- Preserve table and paragraph context. Text may span multiple Word runs.
- Record source revision and validated anchors for every candidate. A confidence score is a hint, not a guarantee.
- Detectors return validated proposals, never arbitrary replacement XML or executable instructions.
- Revalidate locations before applying suggestions. If the document changed, remap through verified editor APIs or rerun detection.
- Confirmed suggestions become editor-managed fields. Users can also create fields from their selection.
- Text-only extraction can support rule matching, but cannot become the canonical document used for export. Manual selection-to-field creation covers missed or ambiguous locations.
- Do not add provider interfaces, model credentials, external conversion calls, or AI allowance UI for the future Groq idea in MVP.

## File writes and jobs

All retained file writes use the shared Python storage/quota service described in [Storage quotas](STORAGE_QUOTAS.md). API and worker code may not write around it.

Commit durable job intent to PostgreSQL and enqueue through an outbox or equivalent recoverable dispatch step. Reconcile undispatched records after interruption. RQ retries require idempotent operations; retrying a job must not create duplicate versions, files, or quota charges.

Jobs carry identifiers and revision references rather than document bytes or credentials in queue payloads. A stale result does not mutate the current document automatically. API and worker containers use the same filesystem paths and compatible permissions.

## Operational boundaries

- Apply ownership checks to every read and mutation, including download URLs and job polling.
- Parse DOCX as untrusted ZIP/XML with compressed-size, expanded-size, entry-count, and processing-time limits. Disable external entity resolution and external resource fetching.
- Keep temporary files, filesystem capacity, parser resources, and job runtimes bounded.
- Use local synthetic documents in development and tests. Do not log document contents, entered field values, or credentials.
- Maintain isolated local and production data/configuration; CI uses disposable test stacks. Backups and persistent staging are outside MVP under D018.
- Verify restart/upgrade persistence and storage reconciliation in local/CI Docker before deployment. Redis may be rebuilt from durable job records where appropriate. Version history is application data on the same server and cannot recover server/disk loss.
- GitHub Actions is the CI and deployment orchestrator. CI coverage gates start in E01; E08 deploys the verified images to the user's server only after the earlier epics pass. See [CI and deployment](CI_CD.md).
- The supplied target hosts other services. Use new unused ports, isolated Compose resources, and the existing shared nginx without taking over its existing listeners or TLS. [Deployment target](DEPLOYMENT_TARGET.md) governs preflight, WEF discovery, validation, graceful reload, and checks for existing-service regressions.
- The configured HTTP origin requires a Fillable-specific HttpOnly/SameSite session cookie without Secure, plus CSRF and exact-origin checks including the port. HTTP traffic is unencrypted and cookies are not scoped by port; D019 records this limitation. Enable Secure for a future explicitly configured HTTPS origin.
