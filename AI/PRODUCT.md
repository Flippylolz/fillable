# Product and MVP scope

## Purpose

A person uploads an existing `.docx`, discovers the places that need information, fills them through a sidebar, and can also edit the document directly. Changes to a field appear in both views. The result is downloadable as an editable DOCX.

Ordinary documents are in scope, including documents without predefined template tags. Detection is assistive: a blank area is not necessarily a field, and users can correct suggestions.

MVP discovery is deterministic: existing Word controls, explicit placeholders, and rule-based blank detection, plus manual field creation. AI is outside MVP. The editor must use free components, with a project-owned implementation allowed if needed; this does not remove direct document editing or version history from scope.

Documents are primarily Ukrainian. Detection must handle Ukrainian labels, Cyrillic placeholder names and native tags, including text split across Word runs. Editing/export must preserve Ukrainian letters, apostrophes, and mixed-language content without transliteration. The UI defaults to Ukrainian and also supports English under the [Localization contract](I18N.md). Use the synthetic baseline in [Test corpus](TEST_CORPUS.md) until representative user files are available.

## Four MVP pages

The user defined these four pages as the MVP boundary and explicitly retained version-history UI. History, settings, and review live within these pages. Paths and the detailed defaults below are proposed implementation choices.

| Page | Proposed route | Main purpose |
| --- | --- | --- |
| Login | `/login` | Authenticate and enter the document library |
| Document library | `/documents` | Upload DOCX files, manage templates and processed documents, and download files |
| Profile | `/profile` | Basic account information, UI language, and storage usage |
| Document workspace | `/editor/:id` | Render and edit a template or document with settings, field sidebar, and version history |

### 1. Login

- Email and password, submit/loading state, and clear invalid-credentials feedback.
- Successful login opens the library. An expired session opens inline sign-in recovery while preserving the mounted workspace; returning to the login page or switching accounts requires explicit resolution of unsaved work.
- Protect library, profile, workspace, and file APIs behind authentication.
- Sign in with a login name and password. New passwords require at least 10 characters.
- MVP accounts are provisioned by an operator through a containerized maintenance command. Public registration and email-based password recovery are deferred.

### 2. Document library

- One page with **Templates** and **Documents** tabs. Documents contains individual working copies and saved processed results.
- An upload button accepts DOCX and lets the user choose a reusable template or a one-off document.
- Show name, last updated time, processing/save state, and relevant actions. Include empty, loading, failure, and quota-exceeded states.
- Template actions: **Edit template**, **Use template**, **Download**, and **Delete**.
- Document actions: **Open**, **Download**, and **Delete**.
- Use template creates a separate document and opens it in the same workspace used for direct uploads.
- Download retrieves the latest successfully saved DOCX, clearly distinguished from unsaved work. Show a link when a valid saved file is available; processing must not expose partial files.
- Show the user's storage meter. Deletion uses a confirmation dialog and the backend cleanup path; a separate trash page is deferred.

### 3. Simple profile

- Show account login and allow changing the display name.
- Allow password change after verifying the current password, and provide logout.
- Include a language switcher: **Українська** (`uk`, default) and **English** (`en`). Save the account preference, apply it across the app without losing active state, and restore it after refresh or a new login. A failed save leaves the previous language selected and shows a recoverable localized error.
- Show used storage, allowance, and remaining space. Users cannot change their own quota.
- Keep quota administration, account provisioning, and password-reset support in operator commands for MVP; no administrator dashboard is required.

### 4. Document workspace

- Render the uploaded DOCX inside a real editor and allow editing supported document content directly.
- Include a small toolbar with back-to-library, document title, save, download, history, and visible saving/saved/error state.
- Keep settings within this page: rename, zoom, and field highlighting are the initial defaults. Do not add a separate settings page.
- Display detected fields in a sidebar with labels, inputs, and review state. Users can rename, dismiss, or manually add a missing field from a selection.
- Sidebar edits update the document; direct edits to document fields update the sidebar.
- Selecting a sidebar field navigates to its document location, and selecting a document field selects its sidebar entry.
- Editing a template is clearly labeled. Filling a template starts a separate document rather than changing its source.
- Include a **version-history panel** for templates and documents: list retained revisions with time and current-version indicator, open a historical revision read-only, download it, and restore it as a new current revision.
- Restoring preserves later retained revisions and restores document content and field metadata together. Resolve unsaved work explicitly before preview or restoration; a failed restore leaves the current document intact.
- Advanced visual diffs, branching, and change attribution are deferred; basic version history is part of MVP.
- Handle unsupported files, missing field locations, stale sessions, unsaved navigation, and failed saves within the workspace.

## Templates and processed documents

- A **template** is a reusable DOCX and its saved field definitions. Initial templates are private to their owner; a shared catalogue is deferred.
- A **document** is an individual editable result created from a template or uploaded directly. It retains its own content and field values.
- A new document uses a snapshot of the template's saved revision. Later changes to, restoration of, or deletion of the template do not alter existing documents.
- Templates and documents share the editor, history UI, and storage service. Both consume the owner's configurable allowance, including independent copies and retained revisions.
- Processing status describes background work; it does not prove a document has been fully filled. The library must distinguish processing, failure, and saved/unsaved state without claiming all fields are complete.

## Requirements across all pages

- Keep all application labels/messages in Ukrainian and English i18n catalogs, including errors, tooltips, accessibility text, editor controls, sidebar/settings, and history states. Every UI feature supplies both translations; translation completeness is a required CI check.
- UI language changes do not translate document content, filenames/titles, extracted/custom field labels, or field values, and do not create document revisions. Format interface dates/numbers/storage values for the selected locale while preserving canonical data.
- Show a small fixed [Git version badge](VERSION_BADGE.md) across all four pages: `version: <first seven deployed-commit characters>` or `version: development`. Preserve the supplied translucent colors, safe-area-aware bottom-right placement and bottom offset on desktop/mobile, with monospace value and click-through behavior. It has no icon, link, tooltip, or interaction; its text remains catalog-based under D022.
- Start with text fields; add checkbox, date, and choice fields only where the selected editor has verified support.
- Inferred fields are correctable. Repeated occurrences share a logical field only when their relationship is explicit or user-confirmed.
- Saved files and their field metadata describe the same revision and preserve supported formatting.
- Store documents and application data on the local server. Run development and deployment through Docker Compose.
- Keep local development and production data separate. No backups or persistent staging environment are required for MVP; version history stays on the same server.
- Enforce configurable per-user storage allowances for templates, documents, copies, saves, restorations, and retained outputs.
- Retention is an explicit operator policy, communicated in history UI. Do not silently remove versions to resolve a failing save.
- Backend permissions, bounded processing, safe saves, and cleanup are required infrastructure, not additional product pages.
- CI blocks coverage below 90%; the measurement contract is in [CI and deployment](CI_CD.md).
- Deployment is the final task, through GitHub Actions to the supplied server at `https://<DEPLOY_HOST>:3200` under D024. Fillable’s TCP relay alone publishes host 3200; existing shared nginx terminates TLS and forwards to the private gateway while preserving other services; see [Deployment target](DEPLOYMENT_TARGET.md). Local Docker development is independent of live-server access.

## Deferred beyond MVP

- AI field detection and provider integrations. Possible later direction: Groq with a visible free allowance/usage display, subject to future evaluation.
- Backups, backup/restore drills, replication, and a persistent staging environment.

- Administrator screens, analytics dashboards, public signup, email recovery, shared template catalogues, and organization/team management.
- A trash browser, advanced history diffs, branching, and advanced retention controls in the UI.
- Real-time collaboration, PDF export, billing, e-signatures, cloud connectors, mobile apps, and bulk generation.
- Legacy `.doc`, macro-enabled files, encrypted documents, unsupported protected content, and OCR of image-only documents.
- Perfect compatibility with every Word feature is not promised; E00 establishes the tested support matrix.

## MVP success evidence

- Login → upload template → review fields → use template → edit in both views → save → download → reopen works across the four pages.
- Direct document upload works without requiring creation of a reusable template.
- Filling a new document leaves its source template unchanged; subsequent template edits/restoration/deletion leave that document usable.
- History preview/download selects the requested retained revision. Restore creates a new revision with matching fields, preserves later retained history, and enforces quotas.
- Profile edits persist, password changes work, and usage matches the quota service.
- Ukrainian is the initial UI language. The four pages and history/settings/sidebar flows work in both languages; the profile choice persists across sessions without altering document content or losing unsaved work. Missing translations fail the planned CI gate.
- Field locations survive supported surrounding edits, and sidebar updates do not lose input or loop.
- Concurrent allocations cannot bypass quotas, and users cannot access each other's files or historical versions.
- A fresh checkout runs and tests through Docker without host Python or Node installations.
- The complete MVP passes mandatory CI, including the independent 90% coverage gates, before its final GitHub Actions deployment.
- The version badge remains unobtrusive across desktop/mobile and themes, allows clicks through, and identifies the deployed artifact's source commit. Missing metadata uses the documented development fallback; a controlled production release must provide and verify its commit.
