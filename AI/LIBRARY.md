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
