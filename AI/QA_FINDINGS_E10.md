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

**Resolution (E10.4, 2026-09-09): fixed.** The invalid-credentials alert now renders inside the sign-in card in a reserved feedback row (stable card geometry — asserted by bounding-box checks in the browser spec), directly under the card heading. Desktop/mobile screenshots in both locales are captured by `frontend/e2e/authentication.spec.ts` and retained in the CI browser artifacts. Merge evidence: [Epics](EPICS.md).

Original finding text (context for the resolution above):

A failed login renders the localized alert at the top-left of the page viewport, disconnected from the centered card the user is interacting with, and the card shifts down when the alert inserts.

- Evidence: [t03-login-wrong-credentials.png](qa-evidence-e10/t03-login-wrong-credentials.png).
- Direction: render the alert inside or directly above the sign-in card and reserve space or animate to avoid the layout jump.

### F5 — Empty-submit login feedback relies on native browser bubbles (low; i18n/UX)

**Resolution (E10.4, 2026-09-09): fixed.** The sign-in inputs no longer use native `required` bubbles: empty submits validate in the form and show `auth.loginRequired`/`auth.passwordRequired` inline under each field in the active UI language (with `aria-invalid`/`aria-describedby` wiring), and no request is sent. Component tests cover both catalogs; the browser spec asserts the messages and captures screenshots in both locales and viewports. The server-side contract is unchanged. Merge evidence: [Epics](EPICS.md).

Original finding text (context for the resolution above):

Both login inputs are `required`, so submitting empty fields shows the browser-native validation bubble, which follows the browser's locale rather than the application's Ukrainian/English catalogs, and is invisible in some environments.

- The i18n contract ([I18N](I18N.md)) requires application copy in catalogs; validation feedback shown to users should follow the active UI language.
- Direction: validate in the form (localized inline messages) while keeping the server-side contract unchanged.

### F6 — Storage audit trail has gaps (low; backend observability)

`storage_audit` recorded `revision_saved` and deletion events during the session, but:

- original uploads, use-template copies, and restores produced no audit rows;
- `document_deletion_requested` / `deletion_completed` rows have `actor_id` NULL even when an authenticated user session issued the DELETE (only `owner_id` is recorded).

An operator therefore cannot attribute upload/copy/restore events or identify who requested a deletion. Direction: extend audit coverage to allocation-backed operations and record the acting session's user on deletion requests.

### F7 — 422 `invalid_request` responses do not identify the offending parameter (informational; API ergonomics)

**Resolution (E10.6, 2026-09-09): fixed.** Schema-validation 422s now carry `{"parameter": <name>, "reason": <machine-readable reason>}` in `parameters` (for example `kind`/`missing` for the documented repro). Only names and bounded machine reasons leave the server — submitted values, exception text and internal messages are never included; request-supplied names are bounded to 64 printable characters. The OpenAPI/TypeScript contract was regenerated (byte-identical — `parameters` was already typed `dict[string|integer]`, so no schema drift exists and CI's drift check confirms it). The frontend interpolates the name where available: `errors.invalid_request_parameter` ("Перевірте значення поля {{parameter}}." / "Check the {{parameter}} field.") is used by the profile forms when the API names a parameter, with the generic catalog message remaining the fallback everywhere else. Covered by error-contract and profile component tests in both languages. Merge evidence: [Epics](EPICS.md).

Original finding text (context for the resolution above):

Schema violations (for example, `GET /api/documents` without the required `kind` query parameter, empty display name, unknown fields) all return `{"error":{"code":"invalid_request","parameters":{}}}` with empty `parameters`. The OpenAPI contract documents the constraints, but clients and the localized UI can only show a generic message. Direction: include a machine-readable parameter name/reason in `parameters` where safe (no submitted values), and surface it in the localized error text.

### F8 — Favicon is SVG-only (informational)

**Resolution (E10.7, 2026-09-09): fixed.** The document icon is now also shipped as a 32×32 `favicon.png` (279 bytes) and a `favicon.ico` (301 bytes, PNG-in-ICO container) rendered from `favicon.svg`, and `index.html` declares both as `alternate icon` fallbacks behind the SVG. `GET /favicon.ico` and `GET /favicon.png` return 200 with image content types (asserted in `smoke.spec.ts` alongside the index.html links). E09.4 had delivered only the SVG, so the fallback landed here as the epic allows. Merge evidence: [Epics](EPICS.md).

Original finding text (context for the resolution above):

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

**Executed 2026-09-09 (E10.7).** The checks below were completed on a clean checkout through the required CI `browser` job (x64, production images) and the local production-style stacks, which run the same pinned Playwright suite; each pending item now has explicit automated coverage and its evidence joins the `browser-evidence`/`development-reports` artifacts. The earlier arm64-browser caveat remains accurate for CI-suite replays on arm64 hosts (Origin omission on same-origin POSTs); local runs here used the API-request-context login pattern that sidesteps it. Results per item:

- Profile page GUI — **passed**: display-name edit feedback, wrong-current-password rejection, password rotation with other-session revocation, language persistence and logout are covered by `e2e/profile.spec.ts`; the 10-character minimum inline message is now asserted in the browser (E10.1/E10.7 addition).
- Delete confirmation dialog — **passed**: cancel and confirm paths for templates and documents are covered by `e2e/library.spec.ts` (including a localized confirmation screenshot) and `e2e/review.spec.ts`.
- Use-template click-through — **passed**: `e2e/mvp-acceptance.spec.ts` exercises the real GUI file input, Use-template navigation into the workspace, template/document independence and source restoration end to end.
- History panel GUI — **passed**: open panel, read-only preview, historical download byte-identity and restore with unsaved-work resolution (dismiss and confirm) are covered by `e2e/history.spec.ts`.
- Manual save button flow and save-failure presentation — **passed**: `e2e/manual-save.spec.ts` covers exact-edit acknowledgment, lost-response uncertainty with exact retry, and quota-failure presentation with the draft preserved.
- English-locale rendering and mobile-viewport layout — **passed**: the required suite runs desktop and mobile projects with Ukrainian-default and English-locale assertions across login, library, profile, workspace, history and saves; localized dates/sizes are asserted in-library and in-profile.
- GUI file-upload dialog — **passed**: Playwright sets files on the real `input[type=file]` (`setInputFiles`), covering the browser path the original manual runtime could not drive.

One new issue surfaced during this pass and was fixed within E10.4: the sign-in form's submit button could sit enabled while the handler still refused submissions (`childBusy`/`recovering` guards), silently swallowing a click during the sign-out transition; the button now reflects the same guards and a successful sign-out resets the recovery state. No other new issues were found.

## Evidence artifacts

- Screenshots: [qa-evidence-e10](qa-evidence-e10) (login default, empty submit, wrong credentials, library after login, workspace toolbar, field navigation/highlight).
- API transcripts reproduced in this document were run against `http://127.0.0.1:8180` with `qa-main`/`qa-second` sessions; the accounts remain available (`qa-main` password was rotated to a private value after the shared fixture was used by another process; `qa-minlen` demonstrates the short-password acceptance).
