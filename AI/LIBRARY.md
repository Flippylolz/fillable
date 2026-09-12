# Document library

E03.1 connects `/documents` to the owned-resource upload/list API described in
[Document persistence](DOCUMENT_PERSISTENCE.md). Templates and individual documents
have separate keyboard-accessible tabs and cursor pagination. Cards show saved state,
original filename, current size, localized modification time and the truthful initial
processing state. Processing submission, downloads, deletion and workspace actions
remain E03.4–E03.6 and later workspace tasks.

Upload sends the original File bytes with the typed API metadata and CSRF headers.
The 10 MiB and filename/title checks give early feedback; server validation and quota
reservation remain authoritative. A random attempt key survives ambiguous network
failures and in-progress retries. Terminal aborted/conflicting operations require a
new key. Successful saves clear the draft and refresh both library and profile usage;
errors retain the file and title. No success or quota value is fabricated on failure.
The key uses `crypto.getRandomValues`, which [supports HTTP contexts](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/getRandomValues),
as required by the accepted deployment origin. `randomUUID` requires a secure context.

Authenticated navigation uses `/documents` and `/profile`, with `/login` for an
anonymous session. Library and profile remain mounted while hidden so successful
language changes preserve upload and profile drafts. In-flight uploads block ordinary
navigation and logout; pending files install a browser leave warning. Browser history
navigation preserves mounted drafts. Both catalogs contain the application copy;
native file-picker text follows the browser's language. User titles and filenames
remain literal data. The shared version badge is unchanged.

Verification includes real raw File bytes, UTF-8 metadata, idempotent retries, quota
failures, stale-response cancellation, cursor failure recovery/deduplication, keyboard
tabs, draft preservation and busy coordination. Production browser tests upload both
kinds through the real HTTP gateway, retry an interrupted request, change language,
reload and verify persisted source digests. The explicit synthetic browser account
exists only in QA provisioning, never ordinary startup.

The final E03.1 local run passed 55 frontend tests and full-source coverage gates:
466/471 lines (98.94%) and 374/399 branches (93.73%). The fresh staged checkout passed
3 development and 14 production browser checks, including persistence after Compose
recreation. Ukrainian desktop and English mobile screenshots were visually inspected.
All isolated volumes were preserved. Backend application code is unchanged from E03.3;
required CI reruns its 140 tests and independent coverage gate before merge.

## Requested visual follow-up (E03.1b)

The user requested a visual direction similar to Google Docs. The library now uses
a compact document-brand header, quiet navigation, rounded upload controls and a
grid of document cards. Their paper illustrations are decorative generic icons,
not previews of document contents. All existing upload, retry, profile and language
behavior remains available. The shared version badge retains its original styling.

E09.14 made each card itself the open affordance after user feedback that the
standalone "Open" link was not discoverable: the card title is an accessible link
stretched over the whole card, so clicking anywhere outside the real controls opens
the template or document in the workspace, while download, use-template, processing
retry and delete keep their own click targets. Middle-click and modified clicks keep
the browser's native link semantics; a blocked (busy/disabled) session swallows the
activation; deletion-pending cards keep a plain-text title and never open.

E09.16 adds the same copy path to template workspaces: a "Save to documents" action
prompts for the new document's title (defaulting to the template name plus the first
filled field's value) and creates the copy through the same idempotent, quota-checked
endpoint and independence rules described above; the card's "Use template" action is
unchanged. The workspace contract lives in [Workspace](WORKSPACE.md).

Library sizes and profile usage share a locale-aware formatter: values below 1000
retain byte plurals; larger values use decimal kB/MB/GB/TB/PB with at most two decimal
places. For example, 1,073,741,824 bytes displays as 1.07 GB in English. These are
rounded display values only; quotas, meter values, API responses and accounting
continue to use exact integer bytes. Decimal units avoid labeling binary quantities
as MB or GB. Zero availability remains visibly zero.

## Tactile Document Gallery shell (E09.22)

The user's redesign plan ([Redesign plan](REDESIGN_PLAN.md), recorded as P04) is now
implemented for the authenticated application. Signed-in pages render a left rail in
the locked ink color with the brand, section links (Мої документи, Шаблони, the open
workspace when one exists, Профіль), the storage meter and sign-out; on narrow
screens the rail becomes an off-canvas drawer opened from the menu bar and closed by
Escape, the scrim, or a selection. The library page carries the gallery composition:
a top bar with the title, a client-side search field, refresh and the prominent DOCX
upload button; tabs and a sort control (newest, oldest, or by title) sit above a
responsive grid of tactile document cards. Search filters the loaded cards by title
or original filename and reports a localized empty result; sorting orders the visible
cursor page client-side. The upload form keeps its file/title/kind fields and exact
idempotent behavior behind the toolbar toggle; the quota section moved into the
sidebar, and deletion-pending cards keep their retry control in the actions row.

The locked palette (#F7F8FA, #172033, #2563EB, #DCE6F7), interface fonts and the
120–180ms motion band are semantic CSS custom properties in `base.css`. Manrope and
Sora are self-hosted through pinned @fontsource-variable packages (no runtime CDN);
Sora ships Latin only, so Ukrainian headings fall back to Manrope, which carries the
full Cyrillic set. `prefers-reduced-motion` renders state changes immediately.
Workspace, profile and login keep their layouts and inherit the global tokens; page
metadata (description and social previews) lives in `index.html`. The shared version
badge keeps its exact D022 styling.
