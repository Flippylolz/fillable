import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.documents.export import DocxExport
from app.documents.package import DocxPackage
from app.fields import working
from app.fields.discovery import metadata

FIXTURE = json.loads(Path("/fixtures/docx/v1/working-review.json").read_text())
SOURCE = UUID(FIXTURE["attrs"]["review"]["sourceVersion"])


def paragraph(*children):
    return {"type": "paragraph", "attrs": {"id": "p"}, "content": list(children)}


def text(value):
    return {"type": "text", "text": value}


def field(identity="control", label="Поле", key="key"):
    return {
        "type": "field",
        "attrs": {"id": identity, "label": label, "key": key},
        "content": [],
    }


def item(location=None, **changes):
    return dict(
        id="candidate",
        occurrenceId="occurrence",
        reason="placeholder",
        sourceKey="key",
        context="Синтетичний контекст",
        label="Поле",
        key="key",
        type="text",
        decision="proposed",
        missing=False,
        location=location or {"kind": "span", "from": 3, "to": 5, "text": "🙂"},
        **changes,
    )


def model(*paragraphs, items=None, origin=SOURCE):
    result = {
        "type": "doc",
        "content": [
            {
                "type": "section",
                "attrs": {"part": "word/document.xml"},
                "content": list(paragraphs),
            }
        ],
    }
    if items is not None:
        result["attrs"] = {
            "review": {"sourceVersion": str(origin) if origin else None, "items": items}
        }
    return result


def control_item(**changes):
    result = item({"kind": "control", "id": "control"})
    result.update(reason="native_control", decision="accepted", **changes)
    return result


def test_real_editor_fixture_is_detached_and_preserves_accepted_and_missing_origins():
    candidate = deepcopy(FIXTURE)
    document, review = working.validate_working(candidate, SOURCE)
    assert review == FIXTURE["attrs"]["review"]
    assert "attrs" not in document
    assert sum(entry["missing"] for entry in review["items"]) == 2
    assert any(
        entry["reason"] == "placeholder" and entry["decision"] == "accepted"
        for entry in review["items"]
    )
    assert any(
        entry["reason"] == "manual" and not entry["missing"]
        for entry in review["items"]
    )
    assert any(entry["decision"] == "dismissed" for entry in review["items"])
    document["content"][0]["content"].clear()
    review["items"].clear()
    assert candidate == FIXTURE


def test_fixture_still_exports_against_immutable_original_and_reopens_unicode_fields():
    document, review = working.validate_working(FIXTURE, SOURCE)
    original = Path("/fixtures/docx/v1/client-intake-uk-v1.docx").read_bytes()
    package = DocxPackage(original)
    exported = DocxExport(package).render(document, package.digest)
    reopened = DocxPackage(exported)
    controls = metadata(reopened.model)
    assert len(controls) == 6
    assert any(
        attrs["key"] == "reviewer-fixture" and attrs["label"] == "Рецензент Їжак"
        for attrs in controls.values()
    )
    assert "Ґанна Їжак 🙂" in json.dumps(reopened.model, ensure_ascii=False)
    assert sum(entry["missing"] for entry in review["items"]) == 2
    assert package.original == original


def test_source_binding_accepts_only_current_or_trusted_previous_origin():
    with pytest.raises(ValueError, match="stale_working_review"):
        working.validate_working(FIXTURE, uuid4())
    assert (
        working.validate_working(FIXTURE, uuid4(), SOURCE)[1]
        == FIXTURE["attrs"]["review"]
    )
    local = model(paragraph(field()), items=[control_item()], origin=None)
    assert working.validate_working(local, SOURCE)[1]["sourceVersion"] is None
    unbound = deepcopy(FIXTURE)
    unbound["attrs"]["review"]["sourceVersion"] = None
    with pytest.raises(ValueError, match="unbound_working_origin"):
        working.validate_working(unbound, SOURCE)
    assert (
        working.validate_working(model(paragraph(text("Без перегляду"))), SOURCE)[1]
        is None
    )


def test_utf16_spans_empty_paragraphs_and_sticky_missing_ranges_are_exact():
    current = model(paragraph(text("A🙂B")), items=[item()])
    assert (
        working.validate_working(current, SOURCE)[1]["items"][0]["location"]["text"]
        == "🙂"
    )
    missing = item({"kind": "span", "from": 1000, "to": 999, "text": "old"})
    missing["missing"] = True
    assert (
        working.validate_working(model(paragraph(), items=[missing]), SOURCE)[1][
            "items"
        ][0]["missing"]
        is True
    )
    empty = item({"kind": "span", "from": 2, "to": 2, "text": ""})
    assert working.validate_working(model(paragraph(), items=[empty]), SOURCE)[1]
    for location in (
        {"kind": "span", "from": 3, "to": 4, "text": "x"},
        {"kind": "span", "from": 4, "to": 5, "text": "x"},
        {"kind": "span", "from": 0, "to": 1, "text": "A"},
        {"kind": "span", "from": 2, "to": 7, "text": "A🙂Bx"},
        {"kind": "span", "from": 4, "to": 3, "text": ""},
        {"kind": "span", "from": 2, "to": 2, "text": ""},
        {"kind": "span", "from": 3, "to": 5, "text": "xx"},
        {"kind": "span", "from": 3, "to": 5, "text": "x"},
    ):
        current["attrs"]["review"]["items"][0]["location"] = location
        with pytest.raises(ValueError):
            working.validate_working(current, SOURCE)


def test_spans_cannot_cross_controls_locked_nodes_or_paragraph_boundaries():
    for obstacle in (
        field(),
        {"type": "lockedInline", "attrs": {"id": "locked", "label": "Kept"}},
    ):
        items = [item({"kind": "span", "from": 2, "to": 5, "text": "xxx"})]
        if obstacle["type"] == "field":
            tracked = control_item()
            tracked.update(id="native", occurrenceId="native")
            items.append(tracked)
        with pytest.raises(ValueError, match="protected_working_span"):
            working.validate_working(
                model(paragraph(text("A"), obstacle, text("B")), items=items), SOURCE
            )
    with pytest.raises(ValueError, match="invalid_working_span"):
        working.validate_working(
            model(
                paragraph(text("A")),
                paragraph(text("B")),
                items=[item({"kind": "span", "from": 2, "to": 6, "text": "AxxB"})],
            ),
            SOURCE,
        )


def test_control_presence_properties_and_complete_tracking_match_document():
    current = model(paragraph(field()), items=[control_item()])
    assert working.validate_working(current, SOURCE)[1]
    for change in (
        {"missing": True},
        {"label": "Wrong"},
        {"key": "Wrong"},
        {"decision": "dismissed"},
    ):
        altered = deepcopy(current)
        altered["attrs"]["review"]["items"][0].update(change)
        with pytest.raises(ValueError):
            working.validate_working(altered, SOURCE)
    current["attrs"]["review"]["items"] = []
    with pytest.raises(ValueError, match="untracked_working_control"):
        working.validate_working(current, SOURCE)
    missing = control_item(missing=True)
    assert working.validate_working(model(paragraph(), items=[missing]), SOURCE)[1]
    missing["missing"] = False
    with pytest.raises(ValueError, match="working_presence_mismatch"):
        working.validate_working(model(paragraph(), items=[missing]), SOURCE)
    legacy = "Давній тег" * 100
    assert working.validate_working(
        model(
            paragraph(field(label="", key=legacy)),
            items=[{**control_item(), "label": "", "key": legacy}],
        ),
        SOURCE,
    )[1]


def test_duplicate_and_overlapping_records_and_invalid_types_are_rejected():
    for second in (
        item(),
        {**item(), "id": "other"},
        {**item(), "id": "other", "occurrenceId": "other"},
    ):
        with pytest.raises(ValueError):
            working.validate_working(
                model(paragraph(text("A🙂B")), items=[item(), second]), SOURCE
            )
    duplicate = {**control_item(), "id": "other", "occurrenceId": "other"}
    with pytest.raises(ValueError, match="duplicate_working_control"):
        working.validate_working(
            model(paragraph(field()), items=[control_item(), duplicate]), SOURCE
        )
    with pytest.raises(ValueError, match="invalid_working_control"):
        working.validate_working(model(paragraph(field(), field())), SOURCE)
    for changes in (
        {"type": "number"},
        {"missing": 1},
        {"reason": "manual"},
        {"decision": "accepted"},
        {"unexpected": "value"},
    ):
        with pytest.raises(ValueError):
            working.validate_working(
                model(paragraph(text("A🙂B")), items=[{**item(), **changes}]), SOURCE
            )
    for change in ({"from": True}, {"from": -1}, {"to": 1.5}, {"text": "x" * 65537}):
        candidate = item()
        candidate["location"].update(change)
        with pytest.raises(ValueError):
            working.validate_working(
                model(paragraph(text("A🙂B")), items=[candidate]), SOURCE
            )
    with pytest.raises(ValueError):
        working.validate_working(model(paragraph(), items=[item()] * 2001), SOURCE)


def test_malformed_models_are_private_value_errors_and_budgets_include_metadata(
    monkeypatch,
):
    for bad in (
        None,
        [],
        {"type": "doc", "attrs": None},
        {"type": "doc", "attrs": {"extra": "data"}},
        model(paragraph({"type": "unknown"})),
        model(paragraph(text(""))),
        model(paragraph({"type": "field"})),
        model(paragraph({"type": "text", "text": "x", "extra": "x"})),
        model(paragraph({"type": "text", "text": "x", "content": [text("x")]})),
        model(paragraph({"type": "lockedInline", "content": [text("x")]})),
        model(paragraph({"type": "field", "attrs": {"id": None}, "content": []})),
        model(paragraph({"type": "field", "content": [paragraph()]})),
        {"type": "doc", "content": "invalid"},
        model(paragraph(text("\ud800"))),
    ):
        with pytest.raises(ValueError):
            working.validate_working(bad, SOURCE)
    with pytest.raises(ValueError):
        working.bounded({"float": float("nan")})
    deep = []
    for _ in range(101):
        deep = [deep]
    with pytest.raises(ValueError, match="working_model_limit"):
        working.bounded(deep)
    monkeypatch.setattr(working, "MODEL_TEXT", 8)
    working.bounded("🙂🙂")
    with pytest.raises(ValueError, match="working_model_limit"):
        working.bounded("🙂🙂🙂")
    monkeypatch.setattr(working, "MODEL_NODES", 2)
    with pytest.raises(ValueError, match="working_model_limit"):
        working.index(model(paragraph(text("bounded"))))
    with pytest.raises(ValueError, match="working_model_limit"):
        working.bounded([None] * 41)
