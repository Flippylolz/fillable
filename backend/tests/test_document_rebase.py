from copy import deepcopy
from uuid import uuid4

import pytest
from test_document_package import archive, doc, walk
from test_document_persistence import DATA
from test_working_review import FIXTURE, SOURCE, control_item

from app.documents.export import DocxExport
from app.documents.package import DocxPackage
from app.documents.rebase import correspondence, prepare, rebase_discovery
from app.fields.blanks import discover
from app.fields.working import validate_working


def exported():
    source = DocxPackage(DATA)
    document, _ = validate_working(FIXTURE, SOURCE)
    return DocxPackage(DocxExport(source).render(document, source.digest))


def test_real_working_tree_rebases_independently_with_review_and_exact_no_edit_bytes():
    package = exported()
    original = deepcopy(FIXTURE)
    target = uuid4()
    prepared = prepare(FIXTURE, package, SOURCE)
    copied = prepared.bind(target)
    document, review = validate_working(copied, target)
    assert document == package.model
    assert DocxExport(package).render(document, package.digest) == package.original
    assert FIXTURE == original
    assert review["sourceVersion"] == str(target)
    for old, new in zip(
        original["attrs"]["review"]["items"], review["items"], strict=True
    ):
        for key in (
            "id",
            "occurrenceId",
            "reason",
            "decision",
            "missing",
            "sourceKey",
            "context",
        ):
            assert old[key] == new[key]
        if old["location"]["kind"] == "span":
            assert old["location"] == new["location"]
        elif old["missing"]:
            assert new["location"]["id"].startswith("missing:")
        else:
            assert new["location"]["id"] == prepared.identities[old["location"]["id"]]
    field = next(node for node in walk(document) if node["type"] == "field")
    field["content"] = [{"type": "text", "text": "Незалежна Єва 🙂\nЇжак"}]
    reopened = DocxPackage(DocxExport(package).render(document, package.digest))
    assert any(
        node.get("text") == "Незалежна Єва 🙂\nЇжак" for node in walk(reopened.model)
    )
    assert package.model != document


def test_discovery_anchors_follow_structural_correspondence_without_rediscovery():
    package = exported()
    source, _ = validate_working(FIXTURE, SOURCE)
    detected = discover(source, SOURCE).model_dump(mode="json")
    target = uuid4()
    mapping = correspondence(source, package)
    copied = rebase_discovery(detected, SOURCE, source, target, package.model, mapping)
    assert copied.source_version_id == target
    assert copied.candidates == discover(source, SOURCE).candidates
    assert copied.fields == discover(source, SOURCE).fields
    for old, new in zip(detected["occurrences"], copied.occurrences, strict=True):
        assert new.anchor.paragraph_id == mapping[old["anchor"]["paragraph_id"]]
        assert new.value == old["value"]
    assert detected["source_version_id"] == str(SOURCE)


def test_untagged_control_fallback_key_changes_but_missing_identity_never_reattaches():
    package = DocxPackage(
        archive(
            doc(
                "<w:p><w:r><w:t>Їжак</w:t></w:r>"
                "<w:sdt><w:sdtPr><w:text/></w:sdtPr><w:sdtContent/></w:sdt></w:p>"
            )
        )
    )
    target = deepcopy(package.model)
    control = next(node for node in walk(target) if node["type"] == "field")
    current = control["attrs"]["id"]
    control["attrs"].update(id="old-control", key="old-control")
    live = control_item(
        location={"kind": "control", "id": "old-control"}, key="old-control", label=""
    )
    missing = control_item(
        location={"kind": "control", "id": current},
        missing=True,
        id="missing",
        occurrenceId="missing",
    )
    target["attrs"] = {
        "review": {"sourceVersion": str(SOURCE), "items": [live, missing]}
    }
    identity = uuid4()
    copied = prepare(target, package, SOURCE).bind(identity)
    _, review = validate_working(copied, identity)
    assert review["items"][0]["key"] == current
    assert review["items"][0]["location"]["id"] == current
    assert review["items"][1]["location"]["id"] != current
    assert review["items"][1]["missing"]
    assert target["attrs"]["review"]["items"][1]["location"]["id"] == current


def test_adjacent_run_boundaries_can_change_without_changing_formatting_or_text():
    package = DocxPackage(archive(doc("<w:p><w:r><w:t>Їжак🙂</w:t></w:r></w:p>")))
    model = deepcopy(package.model)
    paragraph = model["content"][0]["content"][0]
    paragraph["content"] = [
        {"type": "text", "text": value} for value in ("Ї", "жак", "🙂")
    ]
    assert prepare(model, package, SOURCE).bind(uuid4()) == package.model
    paragraph["content"][1]["text"] = "гак"
    with pytest.raises(ValueError, match="copy_text_mismatch"):
        prepare(model, package, SOURCE)


@pytest.mark.parametrize(
    "change",
    [
        "type",
        "order",
        "property",
        "identity",
        "mark",
        "mark_shape",
        "mark_bool",
        "style",
    ],
)
def test_structural_and_format_mismatches_fail_without_mutating_source(change):
    package = DocxPackage(DATA)
    source = deepcopy(package.model)
    nodes = list(walk(source))
    paragraphs = [node for node in nodes if node["type"] == "paragraph"]
    text = next(node for node in nodes if node["type"] == "text")
    if change == "type":
        source["content"][0]["content"][0] = {
            "type": "lockedBlock",
            "attrs": {"id": "foreign", "label": ""},
        }
    elif change == "order":
        source["content"][0]["content"].reverse()
    elif change == "property":
        paragraphs[0]["attrs"]["align"] = "right"
    elif change == "identity":
        paragraphs[1]["attrs"]["id"] = paragraphs[0]["attrs"]["id"]
    elif change == "mark":
        text["marks"][0]["type"] = "foreign"
    elif change == "mark_shape":
        text["marks"][0]["attrs"]["unknown"] = True
    elif change == "mark_bool":
        text["marks"][0]["attrs"]["bold"] = 1
    else:
        text["marks"][0]["attrs"]["bold"] = not text["marks"][0]["attrs"]["bold"]
    before = deepcopy(source)
    with pytest.raises(ValueError, match="copy_"):
        prepare(source, package, SOURCE)
    assert source == before
    assert package.model == DocxPackage(DATA).model


def test_explicit_grouping_key_is_never_reinterpreted_as_a_location_fallback():
    package = DocxPackage(
        archive(
            doc(
                '<w:p><w:sdt><w:sdtPr><w:text/><w:id w:val="17"/>'
                '<w:tag w:val="word/document.xml:control:17"/></w:sdtPr>'
                "<w:sdtContent/></w:sdt></w:p>"
            )
        )
    )
    source = deepcopy(package.model)
    control = next(node for node in walk(source) if node["type"] == "field")
    control["attrs"].update(id="previous", key="previous")
    with pytest.raises(ValueError, match="copy_property_mismatch"):
        prepare(source, package, SOURCE)
    control["attrs"]["key"] = "word/document.xml:control:17"
    assert prepare(source, package, SOURCE).bind(uuid4()) == package.model


def test_removed_structure_and_absent_source_identity_are_not_guessed():
    package = DocxPackage(DATA)
    source = deepcopy(package.model)
    source["content"][0]["content"].pop()
    with pytest.raises(ValueError, match="copy_structure_mismatch"):
        prepare(source, package, SOURCE)
    source = deepcopy(package.model)
    source["content"][0]["content"][0]["attrs"].pop("id")
    with pytest.raises(ValueError, match="copy_identity_mismatch"):
        prepare(source, package, SOURCE)
