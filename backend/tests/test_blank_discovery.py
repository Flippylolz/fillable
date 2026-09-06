import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from test_document_package import archive, doc
from test_document_persistence import DATA

from app.documents.package import DocxPackage, W
from app.fields.blanks import discover


def package(text):
    return DocxPackage(archive(doc(text)))


def test_all_five_labeled_blanks_are_unaccepted_and_negative_cells_are_unchanged():
    source = DocxPackage(DATA)
    before = deepcopy(source.model)
    result = discover(source.model, uuid4())
    expected = json.loads(
        Path("/fixtures/docx/v1/client-intake-uk-v1.expected.json").read_text()
    )
    occurrences = {item.id: item for item in result.occurrences}
    blanks = [
        candidate
        for candidate in result.candidates
        if candidate.reason.startswith("blank_")
    ]
    assert len(result.candidates) == 28 and len(blanks) == 5
    assert len(result.decisions) == 5
    for reference in (
        item for item in expected["occurrences"] if item["expected_action"] == "review"
    ):
        part = reference["paragraph"]["part"]
        paragraph = source.roots[part].xpath(
            reference["paragraph"]["xpath"], namespaces={"w": W[1:-1]}
        )[0]
        matching = [
            candidate
            for candidate in blanks
            if source.elements[occurrences[candidate.occurrence_id].anchor.paragraph_id]
            is paragraph
        ]
        assert len(matching) == 1
        occurrence = occurrences[matching[0].occurrence_id]
        assert (occurrence.anchor.start, occurrence.anchor.end, occurrence.value) == (
            reference["start"],
            reference["end"],
            reference["initial_text"],
        )
        assert matching[0].source_key is None
    assert source.model == before


def test_split_underlined_spaces_and_segmented_dates_preserve_unicode_offsets():
    source = package(
        "<w:p><w:r><w:t>😀 Телефон: </w:t></w:r>"
        '<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>  </w:t></w:r>'
        '<w:r><w:rPr><w:b/><w:u w:val="single"/></w:rPr><w:t>   </w:t></w:r>'
        "<w:r><w:t> кінець</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Дата: __ / __ / ____</w:t></w:r></w:p>"
    )
    result = discover(source.model, uuid4())
    assert [item.value for item in result.occurrences] == [" " * 5, "__ / __ / ____"]
    assert result.occurrences[0].anchor.start == len("😀 Телефон: ")
    assert [item.label for item in result.candidates] == ["😀 Телефон", "Дата"]
    assert not result.decisions


def test_prose_identifiers_ellipsis_plain_spaces_and_unlabeled_blanks_are_ignored():
    source = package(
        "".join(
            "<w:p><w:r><w:t>" + text + "</w:t></w:r></w:p>"
            for text in [
                "case____A",
                "Café____",
                "Wait.....",
                "________________",
                "   ",
                "Name: {{EXPLICIT____}}",
                "Text [________] with context",
            ]
        )
    )
    result = discover(source.model, uuid4())
    assert len(result.candidates) == 1 and result.candidates[0].reason == "placeholder"
    source = package("<w:p><w:r><w:t>Ім’я __________</w:t></w:r></w:p>")
    result = discover(source.model, uuid4())
    assert result.candidates[0].label == "Ім’я"


def test_empty_cell_rule_requires_an_unmerged_labeled_two_column_value_cell():
    source = package(
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Місце зустрічі</w:t></w:r></w:p>"
        "</w:tc><w:tc><w:p/></w:tc></w:tr>"
        "<w:tr><w:tc><w:p><w:r><w:t>[див. додаток]</w:t></w:r></w:p>"
        "</w:tc><w:tc><w:p/></w:tc></w:tr>"
        '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>'
        "<w:p><w:r><w:t>Заголовок</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p/></w:tc></w:tr>"
        "<w:tr><w:tc><w:p><w:r><w:t>Інше</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p/><w:p/></w:tc></w:tr></w:tbl>"
    )
    result = discover(source.model, uuid4())
    assert len(result.candidates) == 1
    assert result.candidates[0].label == "Місце зустрічі"
    assert result.candidates[0].reason == "blank_cell"


def test_protected_and_empty_native_controls_break_underlined_blank_ranges():
    source = package(
        "<w:p><w:r><w:t>Телефон: </w:t></w:r>"
        "<w:r><w:rPr><w:u/></w:rPr><w:t>  </w:t></w:r>"
        '<w:sdt><w:sdtPr><w:id w:val="1"/><w:text/></w:sdtPr>'
        "<w:sdtContent/></w:sdt>"
        "<w:r><w:rPr><w:u/></w:rPr><w:t>  </w:t></w:r>"
        "<w:r><w:drawing/></w:r></w:p>"
    )
    result = discover(source.model, uuid4())
    assert len(result.candidates) == 1
    assert result.candidates[0].reason == "native_control"


def test_combined_budget_and_long_context_are_bounded():
    source = package(
        "<w:p><w:r><w:t>" + "{{NAME}} " * 2000 + "</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Name: ______</w:t></w:r></w:p>"
    )
    with pytest.raises(ValueError, match="field_candidate_limit"):
        discover(source.model, uuid4())
    source = package("<w:p><w:r><w:t>" + "А" * 161 + ": ______</w:t></w:r></w:p>")
    assert not discover(source.model, uuid4()).candidates


def test_short_label_and_underlined_spaces_at_line_end_need_no_colon():
    source = package(
        "<w:p><w:r><w:t>Ім’я </w:t></w:r><w:r><w:rPr><w:u/></w:rPr>"
        "<w:t>     </w:t></w:r></w:p>"
    )
    result = discover(source.model, uuid4())
    assert len(result.candidates) == 1
    assert result.candidates[0].label == "Ім’я"
    assert result.occurrences[0].value == "     "
