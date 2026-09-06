# Synthetic document baseline

E00.1 provides a Ukrainian-first regression fixture while representative user files are unavailable. The user selected the Legal Memorandum visual template. The document is a fictional client intake form; it contains no private user documents, real client records, or deployment details.

## Files

- [Ukrainian client intake DOCX](../fixtures/docx/v1/client-intake-uk-v1.docx): the editable input fixture, not a filled result.
- [Expected outcomes](../fixtures/docx/v1/client-intake-uk-v1.expected.json): field definitions, sample values, source locators, negative cases, structural expectations, and future editing scenarios.

Fixture ID: `client-intake-uk-v1`. Its SHA-256 is recorded in the JSON and must match before applying fixture-specific locators. Keep v1 unchanged after publication; later sample revisions receive a new version and reviewed expectations.

## Baseline inventory

| Item | Count or behavior |
| --- | --- |
| Pages in the verified LibreOffice render | 3 |
| Logical text fields | 19 |
| Stored field occurrences | 27 |
| Explicit token/native-control occurrences | 22 expected deterministic detections |
| Blank candidates | 5 requiring review |
| Native Word plain-text controls | 5, including two prefilled values and a repeated client tag |
| Negative cases | 6 |
| Tables | 2, including a three-column merged cell and intentionally empty cells |
| Word sections | 1, Letter portrait, one-inch margins |
| Numbered list items | 3 using real Word numbering |

The first page holds contact details, native controls, a Cyrillic email placeholder split into three runs with mixed emphasis, an underlined nonbreaking-space blank, an empty response cell, and an underscore blank. The second page holds a long existing Ukrainian value, a document/event table, and a numbered list with repeated fields. The third page holds confirmation, distinct representative/approver fields both labeled `ПІБ`, a segmented date blank, dotted initials, and literal/non-field text. Header and footer placeholders repeat visually on each page but are stored once each.

Ukrainian coverage includes labels, control aliases/tags, Cyrillic placeholder keys, Ґґ/Єє/Іі/Її, and U+0027, U+2019, and U+02BC apostrophes. The reviewer token itself contains U+02BC. A Latin `AGREEMENT_REF` token, a fictional `.test` email, and mixed-language reference text check coexistence. Dates, phone numbers, and initials are text values in this baseline, not promises of date-picker or checkbox support. The sample phone is deliberately non-routable and is not an E.164 validation fixture.

## Expected detection behavior

`detect` marks an explicit token or native text control. `review` marks one of the five semantic blank candidates: phone, meeting location, client reference, target date, and approver initials. These require confirmation before field creation. Prefilled native values remain editable fields and must not be discarded simply because they are nonempty.

Use each field's `source_key` and the listed occurrence relationships. `CLIENT_NAME`, for example, is a test-data identifier mapped to the actual source key `ПІБ_КЛІЄНТА`; it is not an English token secretly present in the DOCX. Repeated explicit tokens/tags describe the intended group, while the two unrelated `ПІБ` labels remain independent. Ordinary narrative text matching a sample name must never be changed by global replacement.

The six negative cases cover a matching narrative name, a bracketed cross-reference, an inapplicable empty cell, ordinary Unicode/underscore text, a quoted token-shaped literal, and a whitespace-only layout paragraph. The quoted literal may appear as an unaccepted review candidate; it must not be silently turned into a confirmed field. Score such suggestions separately from confirmed false positives.

The JSON is an external answer key. No fixture bookmarks, answer-key custom XML, or hidden production identifiers are embedded to make detection succeed artificially. Its XPaths and Unicode-code-point offsets address this exact input revision, not general-purpose editor identities. A parser must join Word run text for matching and retain a mapping back to its original locations; do not replace or normalize source text merely to simplify matching.

## How to use it

1. Verify the file hash and source structure before interpreting the answer key.
2. Evaluate explicit detection and heuristic proposals separately. Report occurrence recall, incorrect proposals, and incorrect confirmed fields with the fixture/version. E04.4 records the measured detector results in [Field discovery](FIELD_DISCOVERY.md) and its committed report; these counts remain the independent answer key.
3. Exercise sidebar/direct edits, linked fields, selection, insertion before a field, deletion, undo/redo, multiline values, save, download, and reopen. The JSON supplies sample values and precise expected relationships.
4. Verify Unicode, unedited narrative, tables/merged cells, numbering, headers/footers, and native controls after export. Allow page count to grow when long values are entered; three pages is the original render baseline, not a fixed pagination requirement after edits.
5. Use the save/preview/restore scenario once application history exists. This fixture alone does not test quota concurrency, authentication, malformed ZIP protection, or storage recovery.

Keep the expected outcomes independent of the detector implementation. When the real document arrives, inspect its structure and add sanitized cases or a new synthetic approximation. Do not remove this baseline or weaken expectations just to match a parser's mistakes. Additional scripts, RTL content, image-only documents, tracked changes, comments, shapes, encrypted files, rich controls, and malformed packages need separate fixtures if they enter the supported scope.

## Verification performed for E00.1

- Authored by patching the selected reference package; its retained source is unchanged. Four template pages were inspected before authoring, then the completed three-page Ukrainian fixture was rendered with the bundled LibreOffice and every final page was inspected at full image resolution.
- Verified ZIP integrity, parseable XML, internal relationship targets, absence of external relationships, every one of the 27 source locators, split-run boundaries/emphasis, all five control IDs/tags, six negative-case locations, and all required Ukrainian/apostrophe characters.
- Verified source section geometry, real numbering, two tables, the merged cell, expandable rows, header/footer references, and the footer `PAGE` field. All 14 package parts outside the intended document/header/footer/settings edits remain byte-identical to the template.
- Section/style audits were rerun. Direct formatting and bold metadata labels are intentional template features; they are not detector outputs. The source title now uses Word's `Title` style while keeping its typography. Template sample prose was replaced with Ukrainian form content, and two explicit page breaks and the requested tables/controls were added.
- `w:updateFields=true` requests field refresh on opening. Microsoft Word was not used, and no selected browser editor or application save/reopen flow has been tested. LibreOffice visual QA and structural checks are the evidence available at this stage.

This task delivers fixture data and documentation, not application code or an automated test suite. The authoring/QA helpers and image/PDF intermediates are task-local tools, not application runtime dependencies. E01 still establishes Docker test commands and the mandatory 90% coverage gate before application PRs merge.
