import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from test_document_package import archive, doc
from test_document_persistence import DATA

from app.documents.package import DocxPackage, W
from app.fields.discovery import extract


def package(text):
    return DocxPackage(archive(doc(text)))


def test_corpus_locations_are_found_without_auto_accepting_literal_tokens():
    source = DocxPackage(DATA)
    model = deepcopy(source.model)
    version = uuid4()
    expected = json.loads(
        Path("/fixtures/docx/v1/client-intake-uk-v1.expected.json").read_text()
    )
    result = extract(model, version)
    assert extract(model, version) == result
    assert model == source.model
    assert len(result.occurrences) == 23 and len(result.candidates) == 23
    native = [
        candidate
        for candidate in result.candidates
        if candidate.reason == "native_control"
    ]
    assert len(native) == 5 and len(result.decisions) == 5
    occurrences = {item.id: item for item in result.occurrences}
    actual = Counter()
    for candidate in result.candidates:
        occurrence = occurrences[candidate.occurrence_id]
        anchor = occurrence.anchor
        paragraph = source.elements[anchor.paragraph_id]
        actual[
            (anchor.part, paragraph.getroottree().getpath(paragraph), occurrence.value)
        ] += 1
    for occurrence in expected["occurrences"]:
        if occurrence["expected_action"] != "detect":
            continue
        part = occurrence["paragraph"]["part"]
        paragraph = source.roots[part].xpath(
            occurrence["paragraph"]["xpath"], namespaces={"w": W[1:-1]}
        )[0]
        key = (
            part,
            paragraph.getroottree().getpath(paragraph),
            occurrence["initial_text"],
        )
        assert actual[key] > 0, occurrence["id"]
        actual[key] -= 1
    assert (
        sum(actual.values()) == 1
    )  # The documented token-shaped literal is reviewable only.
    literal = next(
        candidate
        for candidate in result.candidates
        if candidate.source_key == "НЕ_ЗАПОВНЮВАТИ"
    )
    assert all(decision.candidate_id != literal.id for decision in result.decisions)
    assert len({item.anchor.part for item in result.occurrences}) == 3
    # Explicit native tags group, but retain their independent initial values.
    assert sorted(len(field.occurrence_ids) for field in result.fields) == [1, 1, 1, 2]


def test_unicode_keys_split_runs_and_plain_text_negatives_preserve_exact_source():
    source = package(
        "<w:p><w:r><w:t>😀 {{ІМ</w:t></w:r><w:r><w:rPr><w:b/></w:rPr>"
        "<w:t>ʼЯ_ЇЖАКА}} [[Електронна пошта]] {{Café}} {{AGREEMENT_REF}} "
        "[див. додаток] case_A_17 {{_}} {{ x }} {{evil/command}} "
        "{{line\nbreak}}</w:t></w:r></w:p>"
    )
    result = extract(source.model, uuid4())
    assert [candidate.source_key for candidate in result.candidates] == [
        "ІМʼЯ_ЇЖАКА",
        "Електронна пошта",
        "Café",
        "AGREEMENT_REF",
    ]
    assert result.occurrences[0].anchor.start == 2
    assert result.occurrences[0].value == "{{ІМʼЯ_ЇЖАКА}}"
    assert not result.fields and not result.decisions
    assert all(candidate.reason == "placeholder" for candidate in result.candidates)


def test_protected_and_existing_field_interiors_are_not_reinterpreted_as_tokens():
    source = package(
        "<w:p><w:r><w:t>{{НА</w:t></w:r><w:r><w:drawing/></w:r><w:r><w:t>ЗВА}}</w:t></w:r>"
        '<w:sdt><w:sdtPr><w:id w:val="5"/><w:tag w:val="ПОЛЕ"/>'
        '<w:alias w:val="ПІБ"/><w:text/></w:sdtPr><w:sdtContent>'
        "<w:r><w:t>{{НЕ_КАНДИДАТ}}</w:t></w:r></w:sdtContent></w:sdt>"
        '<w:r><w:t>{{ЕМ</w:t></w:r><w:sdt><w:sdtPr><w:id w:val="6"/>'
        "<w:text/></w:sdtPr><w:sdtContent/></w:sdt>"
        "<w:r><w:t>ПТІ}}</w:t></w:r></w:p>"
    )
    result = extract(source.model, uuid4())
    assert len(result.candidates) == 2
    assert all(candidate.reason == "native_control" for candidate in result.candidates)
    assert any(
        occurrence.value == "{{НЕ_КАНДИДАТ}}" for occurrence in result.occurrences
    )
    assert any(
        candidate.source_key is None and candidate.label == ""
        for candidate in result.candidates
    )


def test_equal_labels_never_link_unrelated_fields_and_context_is_bounded():
    source = package(
        "<w:p><w:r><w:t>"
        + "x" * 1200
        + "</w:t></w:r>"
        + "".join(
            f'<w:sdt><w:sdtPr><w:id w:val="{number}"/><w:tag w:val="{key}"/>'
            '<w:alias w:val="ПІБ"/><w:text/></w:sdtPr><w:sdtContent>'
            f"<w:r><w:t>{value}</w:t></w:r></w:sdtContent></w:sdt>"
            for number, key, value in [
                (1, "REPRESENTATIVE", "Єва"),
                (2, "APPROVER", "Ілля"),
            ]
        )
        + "</w:p>"
    )
    result = extract(source.model, uuid4())
    assert len(result.fields) == 2
    assert all(
        field.label == "ПІБ" and len(field.occurrence_ids) == 1
        for field in result.fields
    )
    assert all(len(candidate.context) == 1024 for candidate in result.candidates)


def test_candidates_and_native_values_are_bounded_without_truncating_document_content():
    source = package("<w:p><w:r><w:t>" + "{{NAME}} " * 2001 + "</w:t></w:r></w:p>")
    original = deepcopy(source.model)
    with pytest.raises(ValueError, match="field_candidate_limit"):
        extract(source.model, uuid4())
    assert source.model == original
    source = package(
        '<w:p><w:sdt><w:sdtPr><w:id w:val="1"/><w:text/></w:sdtPr>'
        "<w:sdtContent><w:r><w:t>"
        + "Ї" * 65537
        + "</w:t></w:r></w:sdtContent></w:sdt></w:p>"
    )
    with pytest.raises(ValueError):
        extract(source.model, uuid4())


def test_source_paragraph_order_and_protected_block_interior():
    source = package(
        "<w:p><w:r><w:t>{{FIRST}}</w:t></w:r></w:p>"
        "<w:customXml><w:p><w:r><w:t>{{HIDDEN}}</w:t></w:r></w:p></w:customXml>"
        "<w:p><w:r><w:t>{{SECOND}}</w:t></w:r></w:p>"
    )
    result = extract(source.model, uuid4())
    assert [candidate.source_key for candidate in result.candidates] == [
        "FIRST",
        "SECOND",
    ]


def test_anonymous_control_identity_cannot_collide_with_an_explicit_tag_group():
    source = package(
        '<w:p><w:sdt><w:sdtPr><w:id w:val="1"/><w:text/></w:sdtPr>'
        '<w:sdtContent/></w:sdt><w:sdt><w:sdtPr><w:id w:val="2"/>'
        '<w:tag w:val="word/document.xml:control:1"/><w:text/></w:sdtPr>'
        "<w:sdtContent/></w:sdt></w:p>"
    )
    result = extract(source.model, uuid4())
    assert len(result.fields) == 2


def test_proposals_and_native_groups_carry_deterministic_kinds():
    source = package(
        "<w:p><w:r><w:t>Дата: {{ДАТА_НАРОДЖЕННЯ}} Сума: {{СУМА_ДОГОВОРУ}} "
        "ПІБ: {{ПІБ_КЛІЄНТА}}</w:t></w:r></w:p>"
        '<w:p><w:sdt><w:sdtPr><w:id w:val="1"/><w:tag w:val="ДАТА_ПОДІЇ"/>'
        '<w:alias w:val="Дата події"/><w:text/></w:sdtPr><w:sdtContent/></w:sdt>'
        '<w:sdt><w:sdtPr><w:id w:val="2"/><w:tag w:val="NOTES"/>'
        '<w:alias w:val="Примітки"/><w:text/></w:sdtPr><w:sdtContent>'
        "<w:r><w:t>1 250,50</w:t></w:r></w:sdtContent></w:sdt></w:p>"
    )
    result = extract(source.model, uuid4())
    kinds = {
        candidate.source_key or candidate.label: candidate.type
        for candidate in result.candidates
    }
    assert kinds["ДАТА_НАРОДЖЕННЯ"] == "date"
    assert kinds["СУМА_ДОГОВОРУ"] == "number"
    assert kinds["ПІБ_КЛІЄНТА"] == "text"
    assert kinds["ДАТА_ПОДІЇ"] == "date" and kinds["NOTES"] == "number"
    fields = {field.label: field.type for field in result.fields}
    assert fields == {"Дата події": "date", "Примітки": "number"}


def test_native_group_kind_follows_its_first_source_occurrence():
    source = package(
        '<w:p><w:sdt><w:sdtPr><w:id w:val="1"/><w:tag w:val="NOTES"/>'
        "<w:text/></w:sdtPr><w:sdtContent><w:r><w:t>2026</w:t></w:r>"
        "</w:sdtContent></w:sdt>"
        '<w:sdt><w:sdtPr><w:id w:val="2"/><w:tag w:val="NOTES"/><w:text/>'
        "</w:sdtPr><w:sdtContent><w:r><w:t>текст</w:t></w:r>"
        "</w:sdtContent></w:sdt></w:p>"
    )
    result = extract(source.model, uuid4())
    assert len(result.fields) == 1
    assert result.fields[0].type == "number"
    assert [candidate.type for candidate in result.candidates] == ["number", "text"]
