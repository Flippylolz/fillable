from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_document_persistence import DATA

from app.documents.package import DocxPackage
from app.fields import validation
from app.fields.schema import FieldSnapshot
from app.fields.validation import paragraphs, validate_snapshot

VERSION = uuid4()
MODEL = {
    "type": "doc",
    "content": [
        {
            "type": "section",
            "attrs": {"part": "word/document.xml"},
            "content": [
                {
                    "type": "paragraph",
                    "attrs": {"id": "p1"},
                    "content": [
                        {"type": "text", "text": "Їжак😀 "},
                        {"type": "text", "text": "Ім’я {{Ґанна}}"},
                        {
                            "type": "field",
                            "attrs": {"id": "control"},
                            "content": [{"type": "text", "text": "Єва"}],
                        },
                        {
                            "type": "lockedInline",
                            "attrs": {"id": "locked", "label": "private"},
                        },
                    ],
                },
                {
                    "type": "table",
                    "content": [
                        {
                            "type": "tableRow",
                            "content": [
                                {
                                    "type": "tableCell",
                                    "content": [
                                        {
                                            "type": "paragraph",
                                            "attrs": {"id": "empty"},
                                            "content": [],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
                {
                    "type": "lockedBlock",
                    "content": [
                        {"type": "paragraph", "attrs": {"id": "hidden"}, "content": []}
                    ],
                },
            ],
        }
    ],
}


def payload():
    return {
        "source_version_id": str(VERSION),
        "occurrences": [
            {
                "id": "o1",
                "anchor": {
                    "kind": "span",
                    "part": "word/document.xml",
                    "paragraph_id": "p1",
                    "start": 0,
                    "end": 5,
                },
                "value": "Їжак😀",
            },
            {
                "id": "o2",
                "anchor": {
                    "kind": "control",
                    "part": "word/document.xml",
                    "paragraph_id": "p1",
                    "control_id": "control",
                },
                "value": "Єва",
            },
        ],
        "fields": [{"id": "f1", "label": "ПІБ", "occurrence_ids": ["o1", "o2"]}],
        "candidates": [
            {
                "id": "c1",
                "occurrence_id": "o1",
                "label": "Ім’я",
                "reason": "placeholder",
                "context": "Їжак😀 Ім’я {{Ґанна}}",
                "source_key": "ІМʼЯ",
            }
        ],
        "decisions": [{"candidate_id": "c1", "status": "accepted", "field_id": "f1"}],
    }


def test_unicode_offsets_and_conflicting_values_roundtrip_without_mutation():
    data = payload()
    before = deepcopy(data)
    model = deepcopy(MODEL)
    snapshot = validate_snapshot(data, VERSION, model)
    assert [item.value for item in snapshot.occurrences] == ["Їжак😀", "Єва"]
    assert snapshot.fields[0].label == "ПІБ"
    assert snapshot.candidates[0].source_key == "ІМʼЯ"
    assert FieldSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert data == before and model == MODEL
    dismissed = payload()
    dismissed["fields"] = []
    dismissed["decisions"] = [{"candidate_id": "c1", "status": "dismissed"}]
    assert (
        validate_snapshot(dismissed, VERSION, MODEL).decisions[0].status == "dismissed"
    )
    blank = payload()
    blank["occurrences"] = [
        {
            "id": "o1",
            "anchor": {
                "kind": "span",
                "part": "word/document.xml",
                "paragraph_id": "empty",
                "start": 0,
                "end": 0,
            },
            "value": "",
        }
    ]
    blank["fields"][0]["occurrence_ids"] = ["o1"]
    blank["candidates"][0]["reason"] = "blank_cell"
    assert validate_snapshot(blank, VERSION, MODEL).occurrences[0].value == ""


def test_real_corpus_native_anchors_preserve_all_five_controls_and_prefilled_values():
    package = DocxPackage(DATA)
    occurrences = []
    for (part, paragraph), (_text, controls, _blocked) in paragraphs(
        package.model
    ).items():
        for identity, value in controls.items():
            occurrences.append(
                {
                    "id": identity,
                    "anchor": {
                        "kind": "control",
                        "part": part,
                        "paragraph_id": paragraph,
                        "control_id": identity,
                    },
                    "value": value,
                }
            )
    result = validate_snapshot(
        {"source_version_id": VERSION, "occurrences": occurrences},
        VERSION,
        package.model,
    )
    assert len(result.occurrences) == 5
    assert sum(bool(item.value.strip()) for item in result.occurrences) >= 2


@pytest.mark.parametrize(
    "target,key,value",
    [
        ("root", "schema_version", 2),
        ("root", "schema_version", True),
        ("root", "extra", "ignored?"),
        ("field", "type", "checkbox"),
        ("field", "occurrence_ids", []),
        ("field", "occurrence_ids", ["o1", "o1"]),
        ("field", "occurrence_ids", ["missing"]),
        ("field", "label", "x" * 513),
        ("occurrence", "value", "x" * 65537),
        ("candidate", "occurrence_id", "missing"),
        ("candidate", "reason", "ai"),
        ("candidate", "context", "x" * 1025),
        ("decision", "candidate_id", "missing"),
        ("decision", "field_id", None),
        ("decision", "field_id", "missing"),
        ("decision", "status", "dismissed"),
        ("anchor", "start", True),
        ("anchor", "start", -1),
        ("anchor", "start", 7),
        ("anchor", "kind", "xpath"),
    ],
)
def test_invalid_contracts_fail_closed(target, key, value):
    data = payload()
    container = (
        data
        if target == "root"
        else data[
            {
                "field": "fields",
                "occurrence": "occurrences",
                "candidate": "candidates",
                "decision": "decisions",
                "anchor": "occurrences",
            }[target]
        ][0]
    )
    if target == "anchor":
        container = container["anchor"]
    container[key] = value
    with pytest.raises(ValidationError):
        FieldSnapshot.model_validate(data)


@pytest.mark.parametrize(
    "collection", ["fields", "occurrences", "candidates", "decisions"]
)
def test_duplicate_identities_are_rejected(collection):
    data = payload()
    data[collection].append(deepcopy(data[collection][0]))
    with pytest.raises(ValidationError):
        FieldSnapshot.model_validate(data)


def test_review_assignments_and_duplicate_proposals_are_validated():
    data = payload()
    data["decisions"] = [{"candidate_id": "c1", "status": "dismissed"}]
    with pytest.raises(ValidationError, match="dismissed_field_occurrence"):
        FieldSnapshot.model_validate(data)
    data = payload()
    data["fields"][0]["occurrence_ids"] = ["o2"]
    with pytest.raises(ValidationError, match="invalid_review_field"):
        FieldSnapshot.model_validate(data)
    data = payload()
    data["candidates"].append({**data["candidates"][0], "id": "c2"})
    with pytest.raises(ValidationError, match="invalid_candidate_occurrence"):
        FieldSnapshot.model_validate(data)


@pytest.mark.parametrize(
    "changes,value,code",
    [
        ({"part": "external.xml"}, "Їжак😀", "unknown_field_anchor"),
        ({"paragraph_id": "hidden"}, "Їжак😀", "unknown_field_anchor"),
        ({"end": 100}, "Їжак😀", "invalid_field_range"),
        ({"start": 0, "end": 0}, "", "invalid_field_range"),
        ({"start": 19, "end": 22}, "Єва", "invalid_field_range"),
        ({"start": 23, "end": 24}, "\ufffc", "invalid_field_range"),
        ({}, "Transliterated", "field_text_mismatch"),
    ],
)
def test_unknown_stale_or_protected_locations_cannot_be_applied(changes, value, code):
    data = payload()
    data["occurrences"][0]["anchor"].update(changes)
    data["occurrences"][0]["value"] = value
    with pytest.raises(ValueError, match=code):
        validate_snapshot(data, VERSION, MODEL)


def test_revision_control_identity_duplicate_ranges_and_empty_controls():
    with pytest.raises(ValueError, match="stale_field_snapshot"):
        validate_snapshot(payload(), uuid4(), MODEL)
    data = payload()
    data["occurrences"][1]["anchor"]["control_id"] = "unknown"
    with pytest.raises(ValueError, match="unknown_field_control"):
        validate_snapshot(data, VERSION, MODEL)
    data = payload()
    data["occurrences"][1] = {**deepcopy(data["occurrences"][0]), "id": "o2"}
    with pytest.raises(ValueError, match="duplicate_field_anchor"):
        validate_snapshot(data, VERSION, MODEL)
    model = deepcopy(MODEL)
    model["content"][0]["content"][0]["content"][2]["content"] = []
    data = payload()
    data["occurrences"][1]["value"] = ""
    assert validate_snapshot(data, VERSION, model).occurrences[1].value == ""
    data["occurrences"][0]["anchor"].update(start=19, end=21)
    with pytest.raises(ValueError, match="invalid_field_range"):
        validate_snapshot(data, VERSION, model)


def test_model_identity_and_resource_bounds(monkeypatch):
    model = deepcopy(MODEL)
    model["content"][0]["content"].append(deepcopy(model["content"][0]["content"][0]))
    with pytest.raises(ValueError, match="invalid_paragraph_identity"):
        paragraphs(model)
    model = deepcopy(MODEL)
    children = model["content"][0]["content"][0]["content"]
    children.append(deepcopy(children[2]))
    with pytest.raises(ValueError, match="duplicate_control_identity"):
        paragraphs(model)
    monkeypatch.setattr(validation, "MODEL_NODES", 2)
    with pytest.raises(ValueError, match="field_model_limit"):
        paragraphs(MODEL)
    monkeypatch.setattr(validation, "MODEL_NODES", 5)
    with pytest.raises(ValueError, match="field_model_limit"):
        paragraphs(
            {
                "type": "section",
                "attrs": {"part": "part"},
                "content": [MODEL["content"][0]["content"][0]],
            }
        )
    monkeypatch.setattr(validation, "MODEL_NODES", 100000)
    monkeypatch.setattr(validation, "MODEL_TEXT", 3)
    with pytest.raises(ValueError, match="field_model_limit"):
        paragraphs(MODEL)


def test_candidate_provenance_must_match_the_anchor_kind():
    data = payload()
    data["candidates"][0]["reason"] = "native_control"
    with pytest.raises(ValidationError, match="invalid_candidate_anchor"):
        FieldSnapshot.model_validate(data)
    data["candidates"][0]["occurrence_id"] = "o2"
    assert FieldSnapshot.model_validate(data).candidates[0].reason == "native_control"
    data["candidates"][0]["reason"] = "blank_line"
    with pytest.raises(ValidationError, match="invalid_candidate_anchor"):
        FieldSnapshot.model_validate(data)


def test_overlapping_ranges_fail_and_adjacent_split_runs_remain_valid():
    data = payload()
    data["occurrences"][1] = {
        "id": "o2",
        "anchor": {**data["occurrences"][0]["anchor"], "start": 4, "end": 6},
        "value": "😀 ",
    }
    with pytest.raises(ValueError, match="overlapping_field_anchors"):
        validate_snapshot(data, VERSION, MODEL)
    data["occurrences"][1]["anchor"].update(start=5, end=7)
    data["occurrences"][1]["value"] = " І"
    assert validate_snapshot(data, VERSION, MODEL).occurrences[1].value == " І"
