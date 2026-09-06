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

## E04.3 conservative blank suggestions

`discover` combines the explicit extractor with unaccepted blank proposals. Supported
signals are underlined ordinary/nonbreaking spaces (including split runs), long
underscore/dot runs and segmented underscore dates. Dates are one span, not several
overlapping fields. A nearby table label or short colon-ended prefix supplies context;
short labels at the end of a line also support underscore/underlined-space blanks.
Dots require the stronger colon/table-label context, avoiding ordinary ellipses.
Identifiers and adjacent word/combining characters block blank interpretation.

A genuinely empty paragraph in an unmerged two-column label/value row may be suggested
when the neighboring label is short and meaningful. Multi-column reference rows,
merged cells, multiple empty padding paragraphs, ordinary spacing and ambiguous
bracketed labels are deliberately excluded from this empty-cell rule. These are
conservative heuristics, not universal form understanding. Inherited underline styles
that the current adapter does not resolve can be missed; manual selection remains the
fallback. The rules read actual model structure and formatting, never fixture XPath
or expected label names.

Existing controls, protected content and explicit proposals remain barriers. Empty
native controls break whitespace-run merging. Combined results obey the 2,000-proposal
limit and complete revision/location validation. No blank is grouped or accepted
automatically, and no DOCX/editor content is changed. The worker/result/copy pipeline
now stores the combined snapshot through the existing fenced completion path.

The fixed corpus produces 28 proposals: the prior 23 explicit/native proposals plus
all five labeled blank suggestions. Their exact paragraph, offsets and source text
match the independent fixture locators. The intentionally empty reference cell and
spacing paragraph produce no blanks. Regression tests cover generalized positive and
negative cases, Unicode offsets, split formatting, protected/overlapping locations,
empty-cell boundaries and the combined budget. Detector-specific precision/misses
are reported in E04.4; this observation is not a universal accuracy guarantee.

## Measured corpus accuracy (E04.4)

The offline evaluator in `app.fields.evaluation` compares source-revision proposals
with the unchanged, SHA-verified v1 answer key. The committed
[report](../fixtures/docx/reports/client-intake-uk-v1.discovery.json) is reproduced
and compared exactly by the required backend test suite. Production discovery
never reads the answer key or report.

| Detector | Labeled occurrences | Proposals | Correct | Extra proposals | Misses | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native controls | 5 | 5 | 5 | 0 | 0 | 100% | 100% |
| Explicit placeholders | 17 | 18 | 17 | 1 | 0 | 94.44% | 100% |
| Blank lines | 4 | 4 | 4 | 0 | 0 | 100% | 100% |
| Empty form cells | 1 | 1 | 1 | 0 | 0 | 100% | 100% |

The extra placeholder is N05's quoted literal: an allowed **unaccepted** review
proposal. It is still counted as a proposal false positive against the 27 labeled
positive locations. Incorrect confirmed fields: **0**. Inferred proposals confirmed
automatically: **0**; only the five controls already present in the source are
accepted. Every negative case records its candidate IDs and accepted IDs separately.
These measurements concern one synthetic Ukrainian fixture, not general document
accuracy. Generalized Unicode, formatting, protected-region and blank-rule tests
supplement this corpus but are not folded into its precision/recall denominator.

Precision is TP/(TP+FP); recall is TP/(TP+FN), rounded to six decimals in JSON.
An empty denominator is null, not a fabricated perfect score. Misses retain answer-key
occurrence IDs; extras retain revision-local candidate IDs. Matching includes the
specific detector and exact source location, so a wrong classification records both
a miss and an extra. Reports contain counts, fixture hashes and IDs, not source text.

The evaluator resolves exactly one source XML element per fixture XPath and checks
the expected raw `w:t` slice before interpreting offsets. It maps raw Unicode code
points through the parser's source-run identities to model code points: tabs and line
breaks count only in the model, protected inline regions occupy one model position,
and protected interiors cannot become expected editable spans. Native controls match
the exact source element. Equal text elsewhere cannot substitute for a missing anchor.
The answer key is trusted offline test input; this is not an upload endpoint.

Reproduce the report on stdout in Docker after building the backend test image:

```sh
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps backend-test \
  python -m app.fields.evaluation \
  /fixtures/docx/v1/client-intake-uk-v1.docx \
  /fixtures/docx/v1/client-intake-uk-v1.expected.json
```

Review any report change together with detector behavior; do not rewrite the v1
answer key to accommodate mistakes. Tests deliberately remove and misclassify results,
accept a literal, alter hashes/text/locators, and exercise Unicode/tab/line-break and
locked-region projection to verify that the report detects these failures.

## Reviewed metadata export (E04.5a)

The source-preserving DOCX adapter permits explicit changes to a known plain-text
control's alias (`label`) and grouping tag (`key`). Its control identity, source part,
other attributes, protected regions and source formatting remain validated. New
controls retain unique identities but may share an explicit group key with each
other or an existing control. Grouping alone does not overwrite conflicting values;
equal labels alone do not group anything.

Changed/new labels must be nonblank strings of at most 256 Unicode code points;
changed/new keys are nonblank strings of at most 512. Control characters are rejected.
Unchanged legacy metadata remains intact, including empty or longer aliases. Editing
an ambiguous duplicate tag/alias fails rather than guessing which property Word uses.
New control attributes are limited to `id`, `key`, and `label`.

When only metadata changes, the adapter retains the original control content and
properties, including the placeholder-display flag. Actual value edits rebuild only
supported runs and clear that flag, as before. Existing control IDs survive reopening;
new controls receive collision-checked Word IDs. Unchanged package parts remain
byte-identical; XML namespace serialization within a changed part may differ.

This subtask provides the export operation required by review. Editor transactions
and localized review UI follow in E04.5b/c; production revision saves remain E06.
It does not itself persist a review decision or expose a new editing endpoint.
