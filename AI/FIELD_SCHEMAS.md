# Revision-bound text-field schemas

E04.1 defines the shared Python contract in `app/fields/schema.py` and the model-anchor
validator in `app/fields/validation.py`. This task defines and validates proposals;
detectors, persistence/API wiring and review controls follow in E04.2–E04.5. It does
not claim discovery accuracy or add a second live editor state.

## Records

A `FieldSnapshot` has schema version 1, a saved source-version UUID, logical text
fields, occurrences, candidates and explicit review decisions. A field names its
occurrence IDs and keeps its user-facing label separately from its opaque identity.
Each occurrence preserves its own exact value; repeated conflicting prefilled values
are never collapsed to a single arbitrary winner. A candidate records its occurrence,
proposed label, original source key, bounded supporting context and machine-readable
reason (native control, placeholder, blank line/cell, or manual). No AI provenance is
supported. A review decision accepts into an existing logical field or dismisses;
unreviewed candidates have no decision. Dismissal cannot leave that occurrence assigned
to an active field. Candidate provenance must match the anchor kind.

All records reject unknown properties. Identity, label, value, context and collection
sizes are bounded; offsets are strict nonnegative integers. Duplicate record IDs,
repeated occurrence assignment, unknown references, conflicting decisions and invalid
review assignments fail validation. Type is text only; verified support for other
field types requires a subsequent explicit schema change. Labels, source keys, values
and context remain user data in their original Unicode, never translation keys or
instructions. Blank labels can be displayed through a localized fallback without
changing saved metadata. Individual source values above 65,536 code points exceed
this schema's bounded text-field support; detection must surface that limitation,
not truncate content. Ordinary document text remains governed by the DOCX limits.

## Location and revision validation

`validate_snapshot` validates the records and exact source version before checking
locations against the known editor model. A control anchor names its package part,
paragraph ID and stable control ID. A span names part/paragraph and an end-exclusive
Unicode code-point interval over concatenated supported text runs. Existing controls
and protected inline content are barriers for inferred spans; a zero-width span is
allowed only in a genuinely empty paragraph, supporting empty table-cell proposals.
Protected block interiors never enter the candidate-location index. Unknown parts,
paragraphs, controls, stale revisions, duplicate/overlapping anchors and mismatching source text
fail closed. Supplied XPath, XML fragments or global matching instructions are not
accepted locations. This validator assumes a source model already admitted by the
DOCX/editor adapter; it is not a replacement for DOCX admission or export validation.

Offsets include model tabs/newlines, unlike the fixture's raw `w:t`-only XPath helper
contract. Detector evaluation must convert explicitly. JavaScript editor integration
must convert code-point offsets to UTF-16 positions and account for editor node tokens;
raw Python offsets are never ProseMirror positions. The index includes the source
part, so headers/footers are counted once per stored part, independently of pagination.
Index traversal and total text have explicit 100,000-node and 52,428,800-code-point bounds. Supported
native fields keep their values and IDs, including empty controls.

## Verification

Tests validate every native control in the Ukrainian corpus, exact Ukrainian letters,
apostrophe variants, split runs and an astral Unicode character; preserve conflicting
occurrence values across serialization; and check empty table cells, protected ranges,
stale/unknown locations, identity/reference/review/provenance failures and resource
bounds. Validation never mutates the model or input records. No new UI or DOCX
transformation is introduced by this schema task; subsequent detectors and review
integration supply their own API, browser and accuracy evidence.
