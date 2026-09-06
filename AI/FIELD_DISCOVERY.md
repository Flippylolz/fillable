# Deterministic field discovery

E04.2a adds a pure detector that returns the [field snapshot](FIELD_SCHEMAS.md) for
one saved source version. It does not change the editor model, DOCX bytes or files.
Processing persistence/API integration is E04.2b, blank rules are E04.3, measured
accuracy reporting is E04.4 and workspace review is E04.5. No fixture answer key,
external service, model call or global replacement is part of production extraction.

## Supported explicit sources

Supported native plain-text controls retain their existing values, labels, anchors
and exact explicit tags. They are recorded as already accepted because the field
already exists in the source. Only exact nonblank source tags group their occurrences;
anonymous controls have independent identities. Equal display labels never imply
linking, and differing values in an explicit repeated group remain separate values.
Anonymous identities and explicit tag values use separate grouping namespaces.

`{{KEY}}` and `[[KEY]]` patterns become unaccepted proposals across supported text
runs in one paragraph. Keys have 1–128 code points, include at least one Unicode
letter/number, and permit Unicode letters/numbers/combining marks, internal spaces,
underscores, hyphens and the supported apostrophe forms. Outer whitespace, path-like
punctuation and line breaks are not key syntax. Source text/key Unicode is preserved
without normalization or transliteration. Single brackets and ordinary names or
underscores in prose do not become explicit-token proposals.

The detector cannot distinguish every token-shaped literal from a request for input.
It therefore never auto-accepts a placeholder, including the corpus's documented
literal `{{НЕ_ЗАПОВНЮВАТИ}}`. Review can dismiss it without changing content. Native
control interiors and protected inline/block regions are never reinterpreted as
tokens. Empty native controls remain barriers even though their text width is zero.
Header/footer occurrences are indexed once per stored part. Paragraph traversal keeps
source order; native fields are recorded before text proposals within each paragraph.

IDs are deterministic hashes of explicit grouping identity or known source anchors,
not translated labels. Source-version validation still applies; IDs do not authorize
applying a result to another revision. Candidate count is capped at 2,000. The shared
index bounds document traversal/text, and the complete result passes strict snapshot
and location validation before it is returned. Over-limit field values fail rather
than truncating document contents. Supporting context is bounded user data and must
not be logged or treated as instructions by downstream consumers.

## Current evidence

The fixed Ukrainian corpus yields 23 proposals: all 22 labeled explicit detections
(five native controls and 17 tokens), plus one permitted unaccepted token-shaped
literal. Five native decisions preserve existing fields; no placeholder is accepted.
Expected paragraph/source text matches are tested against the fixture's own XML
locators, independently of detector implementation. This is a regression observation,
not a universal precision claim; E04.4 reports detector-specific accuracy and misses.
Additional tests cover split runs, an astral Unicode character, combining marks,
Ukrainian/apostrophe/mixed-script keys, negative syntax, protected content, repeated
and anonymous identities, bounded context/candidate/value sizes and input immutability.

## E04.2b durable results and API

Migration `0007_field_results` adds a nullable JSON result to the existing owned
source-version job. Downgrade refuses to drop non-null results. Existing documents
and files are unchanged; a legacy completed inspection without proposals can be
explicitly submitted for discovery with a fresh bounded attempt budget. The migration
does not enqueue all historical documents or discard failures.

The worker extracts/validates the snapshot from the verified saved DOCX, then publishes
integer summary and proposal JSON together under current-resource, source-version,
attempt and live-lease fences. The RQ payload still contains only opaque identifiers;
proposal content is never returned through RQ logs or the compact status polling API.
`GET /api/documents/{id}/fields` returns owned current-revision status and an optional
typed snapshot in one coherent resource/job read, with no-store responses. It exposes
results only for completed discovery; legacy completed count-only inspection reports
`not_started` here. Unknown ownership is 404, and invalid stored revision metadata
fails safely. Workspace review consumes this endpoint in E04.5; no auto-acceptance of
placeholder text is introduced.

A template copy clones a valid completed snapshot into a new completed job, with its
own owner/document/job/version identifiers and rebased snapshot source-version UUID.
It copies the JSON independently and does not enqueue redundant processing or consume
queued-job admission. If the source has no completed result, the copy uses ordinary
processing intent. This all commits with the new quota-checked file/version. Invalid
source result metadata aborts and cleans up the attempted copy. Deletion clears all
proposal JSON for the deleted resource in the same tombstone transaction that clears
its saved editor models; a copy's separate result remains available. Retention must
respect or explicitly remove the job's existing source-version FK in E06.

Real PostgreSQL/worker tests cover owned/current results, source UUID validation,
atomic publication, expired/mismatched attempts, legacy migration/retry behavior,
independent completed-result cloning without dispatch, source deletion cleanup and
copy survival, and safe malformed-metadata failures without quota leakage. The real
Docker verifier checks the 23-proposal/five-native-decision corpus result before and
after service recreation. Desktop/mobile copy flows verify cloned results and their
survival after source deletion, alongside unchanged saved bytes.
