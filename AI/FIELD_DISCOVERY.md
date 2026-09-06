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
