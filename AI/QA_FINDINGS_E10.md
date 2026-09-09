# Manual QA findings — E10 input

Status: findings from a one-pass manual test; each finding needs its own fixing task in [Epics](EPICS.md) (epic E10). This document records what was tested, what passed, what failed, and what could not be checked. Evidence images live in [qa-evidence-e10](qa-evidence-e10).

## Scope and method

Black-box manual testing of the four MVP pages plus direct API probing, run on 2026-09-08 against the local development stack (`fillable-local` at `http://127.0.0.1:8180`) and, for API checks, the same stack's backend. The committed revision under test is `d816fe8` (origin/main at the time of testing). Dev stack behavior was cross-checked against committed sources where a finding depended on them.

Environment preparation (not part of the findings): two QA accounts (`qa-main`, `qa-second`) were provisioned with the shared browser fixture password, one template and one document were uploaded through the API to make workspace flows reachable, and test files (non-DOCX, empty, corrupt, oversized, valid-ZIP, long Cyrillic filename) were generated locally.

Two environment caveats affect interpretation and are recorded so the next agent can judge each finding:

1. **Shared working tree contamination.** During the session, another concurrent agent had uncommitted checkbox-feature changes in the same checkout (`frontend/src/editor/checkboxes.ts` and edits to `adapter.ts`, `DocumentEditor.tsx`, `model.ts`, `sourceNodes.ts`, `editor.css`, both locale catalogs, and four backend files). The dev server serves the working tree, so some frontend observations may include that in-progress code. Every finding below was therefore re-checked against committed sources where possible; findings that could not be re-verified against `main` are marked as needing confirmation. The production frontend build (`tsc --noEmit && vite build`) currently fails on that uncommitted tree with `TS2339` in `adapter.ts` (union `CheckboxOutcome` narrowing) — that build failure belongs to the in-progress work, not to `main`.
2. **Browser automation runtime failure.** The in-session browser's input pipeline (clicks and keyboard at all levels) died mid-session and did not recover in fresh tabs. GUI testing of some flows (profile page, delete confirmation, use-template click-through, history panel interactions, rename completion, English-locale flows, mobile viewport) could not be executed and is tracked as pending in epic E10. Backend behavior for most of those flows was still covered through the API.

## Findings

### F1 — Password minimum length is not enforced by the backend (high; contract violation)

**Resolution (E10.1, 2026-09-09): finding withdrawn — the repro evidence miscounted the password length.** `short9char` has ten characters (s‑h‑o‑r‑t‑9‑c‑h‑a‑r), so the observed `200`/`completed` outcomes are correct boundary behavior: passwords of exactly 10 characters are accepted. Enforcement of the 10–1024 range has existed on all three paths since E08.6 (PR #77, merged before this test pass): the profile endpoint's `new_password` field rejects shorter values with `422 invalid_request`, and `validate_password` gates both `provision` and `reset_password`. The `qa-minlen` account therefore demonstrates acceptance of a valid 10-character password, not a gap. E10.1 added the previously missing 9-reject/10-accept boundary tests for the provisioning and reset CLI paths, made the CLI print the specific `invalid_password` code instead of generic `invalid_input`, and replaced the profile form's native `minLength` bubble with a catalog-based inline minimum message in both languages. Merge evidence: [Epics](EPICS.md).

Original finding text (superseded):

`POST /api/profile/password` accepted a 9-character `new_password` and returned 200; the new password then logged in successfully. The provisioning CLI also accepts passwords shorter than 10 characters (`app.accounts.cli provision --password-stdin` created account `qa-minlen` with `short9char`).

- Contract: [Product](PRODUCT.md) — "New passwords require at least 10 characters"; [Local development](LOCAL_DEVELOPMENT.md) — "a password of at least 10 characters".
- Repro (API): rotate to `new_password: "short9char"` (9 chars) → 200; login with the 9-character password → 200. Repro (CLI): `printf 'short9char' | python -m app.accounts.cli provision ... --password-stdin` → `completed`.
- A wrong current password is correctly rejected (`400 current_password_invalid`), and password rotation correctly invalidates existing sessions (subsequent requests 401).
- The web form may enforce 10+ client-side (not verified — GUI input failed before this check); the backend must enforce it regardless.
- Direction: enforce the minimum in the password-change endpoint, the provisioning command, and the reset command; add backend tests for 9 (reject) and 10 (accept) characters on all three paths.

### F2 — Workspace settings panel loses its open state by itself (medium-high; UX/function)

**Resolution (E10.2, 2026-09-09): root cause identified as the contaminated dev tree, with a hardening change and the requested browser check.** The clean-`main` reproduction required by the epic did not reproduce a collapse: on an isolated dev stack built from `dc062be` in a separate worktree, a browser check held the expanded panel open for 65+ seconds across two real autosaves and multiple 20-second editing-lease renewals while the native `<details>` element kept `open` throughout. Code review of committed `main` finds no closure path: the panel's open state lives in the DOM (`<details>`), `Workspace` re-renders but never remounts it during lease renewal (state update only), processing polling (state update only), or autosave (prop update only), and nothing sets `open` programmatically. The QA session ran while the concurrent agent was actively editing the very working tree that the dev server served; Vite hot updates and React Fast-Refresh remounts from those unrelated file saves recreate components and reset native `<details>` state — matching the observed ≤5 s/8 s variable timing and the rename draft loss. E10.2 still hardened the panel: `WorkspaceSettings` now receives its `open` state from `Workspace`, so even a component remount (the actual collapse mechanism observed) can no longer collapse it mid-work. `frontend/e2e/settings-panel.spec.ts` holds the panel open 60+ seconds with autosave and lease-renewal activity and asserts the in-progress title draft survives. Merge evidence: [Epics](EPICS.md).

Original finding text (context for the resolution above):

The "Налаштування робочого простору" section collapses spontaneously while the user is working: it was observed closed seconds after being opened (measured once at ≤5 s, once still open after 8 s — timing varies), and it closed twice during a rename attempt. During one collapse the panel body existed in the DOM (`workspace-settings-body`) at zero size, and the title input flipped between visible and hidden between consecutive checks.

- Consequence: rename and other settings flows are unreliable; the rename could not be completed through the GUI in several attempts. The typed title also survived in the unrelated "Назва нового поля" input during one attempt, showing that focus/draft handling around the collapse is fragile.
- Suspected direction (for the fixing agent): a periodic background refetch (editing-lease renewal, processing poll, or storage usage poll) remounts `WorkspaceSettings` or its parent and resets the collapsed state. Candidate files: [WorkspaceSettings.tsx](../frontend/src/workspace/WorkspaceSettings.tsx), [Workspace.tsx](../frontend/src/workspace/Workspace.tsx), [useEditingLease.ts](../frontend/src/workspace/useEditingLease.ts).
- Needs confirmation on a clean `main` checkout (see contamination caveat) — `WorkspaceSettings.tsx` itself was not among the concurrent agent's modified files, so committed code is the likely source.
- Evidence: [t07-workspace-toolbar.png](qa-evidence-e10/t07-workspace-toolbar.png) and the DOM observations described above.

### F3 — Undo/redo buttons are enabled with empty history (low; UI state)

**Resolution (E10.3, 2026-09-09): fixed.** The editor adapter's presentation now carries `canUndo`/`canRedo` derived from the ProseMirror history plugin state (`done`/`undone` event counts), and the toolbar gates the "Скасувати"/"Повторити" buttons on them in addition to `readOnly`. The buttons are disabled on a fresh open, enable after an applicable edit, flip correctly across undo/redo, stay consistent through autosave, and reset when a history restore remounts the editor. Covered by a component test asserting the full cycle in both locales and by `frontend/e2e/undo-redo.spec.ts` (desktop + mobile) covering fresh-open, edit, autosave, undo/redo, and post-restore states. Merge evidence: [Epics](EPICS.md).

Original finding text (context for the resolution above):

On a freshly opened document (no edits), both "Скасувати" and "Повторити" are enabled. [DocumentEditor.tsx](../frontend/src/editor/DocumentEditor.tsx) on committed `main` gates them only by `readOnly` and never consults ProseMirror's `canUndo`/`canRedo`, so the buttons do not reflect history availability. Clicking them with empty stacks is a no-op, but the enabled state misleads users (and screen-reader users) about available actions.

- Direction: track history state in the editor presentation and disable the buttons accordingly; cover with a component test and a browser assertion.

### F4 — Login error alert is placed far from the sign-in card (low; UX)

A failed login renders the localized alert at the top-left of the page viewport, disconnected from the centered card the user is interacting with, and the card shifts down when the alert inserts.

- Evidence: [t03-login-wrong-credentials.png](qa-evidence-e10/t03-login-wrong-credentials.png).
- Direction: render the alert inside or directly above the sign-in card and reserve space or animate to avoid the layout jump.

### F5 — Empty-submit login feedback relies on native browser bubbles (low; i18n/UX)

Both login inputs are `required`, so submitting empty fields shows the browser-native validation bubble, which follows the browser's locale rather than the application's Ukrainian/English catalogs, and is invisible in some environments.

- The i18n contract ([I18N](I18N.md)) requires application copy in catalogs; validation feedback shown to users should follow the active UI language.
- Direction: validate in the form (localized inline messages) while keeping the server-side contract unchanged.

### F6 — Storage audit trail has gaps (low; backend observability)

`storage_audit` recorded `revision_saved` and deletion events during the session, but:

- original uploads, use-template copies, and restores produced no audit rows;
- `document_deletion_requested` / `deletion_completed` rows have `actor_id` NULL even when an authenticated user session issued the DELETE (only `owner_id` is recorded).

An operator therefore cannot attribute upload/copy/restore events or identify who requested a deletion. Direction: extend audit coverage to allocation-backed operations and record the acting session's user on deletion requests.

### F7 — 422 `invalid_request` responses do not identify the offending parameter (informational; API ergonomics)

Schema violations (for example, `GET /api/documents` without the required `kind` query parameter, empty display name, unknown fields) all return `{"error":{"code":"invalid_request","parameters":{}}}` with empty `parameters`. The OpenAPI contract documents the constraints, but clients and the localized UI can only show a generic message. Direction: include a machine-readable parameter name/reason in `parameters` where safe (no submitted values), and surface it in the localized error text.

### F8 — Favicon is SVG-only (informational)

The app ships `<link rel="icon" type="image/svg+xml" href="/favicon.svg">`; `GET /favicon.ico` returns 404. Older clients and some tools request `/favicon.ico` by convention and get a 404. Direction: add a small `.ico`/`.png` fallback as part of the favicon task (E09.4).

## Verified working (no action needed)

The following were exercised and behaved correctly; listed so the next agent does not redo them.

- **Login/auth**: wrong-credentials localized alert; `/` redirects to `/login` signed-out; protected page redirects to `/login` after session loss; login name + password form with proper autocomplete attributes; version badge present on login/library/workspace pages (`version: development` on the dev stack); Ukrainian default UI; centered sign-in card on desktop.
- **Library**: Templates/Documents tabs with correct per-kind cards; actions per kind (Open/Download/Delete for documents; plus Use template for templates); localized date, size, and storage meter (1.19 МБ / 1.07 ГБ matched actual bytes); quota-exceeding upload rejected at the API with `409 quota_exceeded` and no leaked reservation (`reserved_bytes` returned to 0).
- **Workspace**: DOCX renders in the editable canvas with tables, Cyrillic text, and field marks; sidebar→document sync (typing in a sidebar field updates the document, including linked repeated occurrences of a grouped field); document→sidebar sync (editing field text in the canvas updates the sidebar value); field navigation (prev/next buttons and per-field "go to field" update the location indicator and move the document cursor); field highlighting toggle on/off; zoom select applies; save button reflects dirty state; autosave created revisions during editing and status strings correctly distinguish saved/unsaved ("Завантаження DOCX містить лише збережену версію" while dirty); download button distinguishes saved output; reload restores the saved state without losing autosaved edits.
- **History/restore (API)**: version list ordered with current marker and `restored_from` provenance; restore as a new revision preserved all later revisions; the restored revision's download is byte-identical (same SHA-256) to the source revision; duplicate restore with the same idempotency key returned the same result without creating a revision; restore without a current lease is rejected.
- **API validation matrix**: text-renamed-`.docx`, zero-byte, random-bytes, and valid-ZIP-but-not-DOCX uploads → `422 invalid_document`; >10 MiB → `413 file_too_large`; missing/invalid metadata, invalid kind, whitespace title, invalid idempotency key → `422 invalid_request`; title rename enforces optimistic concurrency (`409 operation_conflict` on stale `source_version_id`), length limits, and non-empty title; editing lease acquire/renew/release are idempotent and `renew` after `release` → `409 lease_lost`.
- **Authorization**: cross-user reads of another user's document/template/content/download/versions/fields → `404` (no existence leak); cross-user copy → `404`; unauthenticated API → `401`; bad/missing CSRF token or foreign Origin on mutations → `403`; invalid UUID → `422`; all-zero UUID → `404`.
- **Account security**: failed logins rate-limited (`429 rate_limited` from the 6th consecutive failure, including for the correct password — brute-force protection working); password change requires the current password; password rotation invalidates existing sessions.
- **Quota service**: lowered per-user override enforced immediately; exceeded upload rejected with `409 quota_exceeded`; `used_bytes` matched the sum of retained files; reservation cleaned up after rejection; `inherit` restores the default allowance.

## Pending manual checks (tracked in E10)

Blocked by the browser-runtime failure; the fixing agent should complete them as part of E10.7 and move any newly found issues into this document. Note for local runs: replaying the CI browser suite on an arm64 host fails most login-dependent tests because the arm64 Chromium build omits the `Origin` header on same-origin POSTs, which the API's exact-origin check (by design) rejects with `403 forbidden`; the same suite passes in the x64 GitHub Actions runner (verified green on `d816fe8`, run 34275710322). Complete these checks through CI artifacts or an x64 environment:

- Profile page GUI: display-name edit feedback, password-change form (including the 10-character minimum message), language switcher persistence across refresh and re-login, logout from the profile.
- Delete confirmation dialog (cancel and confirm paths) for templates and documents.
- Use-template click-through from the library into the workspace (independent copy, template label in the workspace).
- History panel GUI: open panel, read-only historical preview, historical download, restore with unsaved-work resolution.
- Manual save button flow and save-failure presentation (API save path verified only at contract level).
- English-locale rendering of library and workspace (including localized dates) and mobile-viewport layout of all four pages.
- GUI file-upload dialog itself (runtime does not support file choosers; validated at the API instead).

## Evidence artifacts

- Screenshots: [qa-evidence-e10](qa-evidence-e10) (login default, empty submit, wrong credentials, library after login, workspace toolbar, field navigation/highlight).
- API transcripts reproduced in this document were run against `http://127.0.0.1:8180` with `qa-main`/`qa-second` sessions; the accounts remain available (`qa-main` password was rotated to a private value after the shared fixture was used by another process; `qa-minlen` demonstrates the short-password acceptance).
