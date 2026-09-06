import json
import runpy
import sys
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import pytest
from test_document_package import archive, doc
from test_document_persistence import DATA

from app.documents.package import DocxPackage, W
from app.fields.blanks import discover
from app.fields.evaluation import evaluate, projection, reference_key, resolve
from app.fields.schema import FieldSnapshot

MANIFEST = Path("/fixtures/docx/v1/client-intake-uk-v1.expected.json")
REPORT = Path("/fixtures/docx/reports/client-intake-uk-v1.discovery.json")


def baseline():
    package = DocxPackage(DATA)
    return (
        package,
        json.loads(MANIFEST.read_text()),
        discover(package.model, UUID(int=0)),
    )


def test_report_is_reproducible_and_counts_literal_proposal_separately():
    package, expected, snapshot = baseline()
    report = evaluate(package, expected, snapshot)
    assert report == json.loads(REPORT.read_text())
    assert report == evaluate(package, expected, discover(package.model, UUID(int=1)))
    explicit = report["detectors"]["placeholder"]
    assert (
        explicit["true_positives"],
        explicit["false_positives"],
        explicit["false_negatives"],
    ) == (17, 1, 0)
    assert explicit["precision"] == 0.944444 and explicit["recall"] == 1
    assert not report["incorrect_confirmed_candidate_ids"]
    assert not report["inferred_confirmed_candidate_ids"]
    assert report["negative_cases"][4]["review_proposals_allowed"]
    assert (
        report["negative_cases"][4]["candidate_ids"] == explicit["extra_candidate_ids"]
    )
    assert all(not item["accepted_candidate_ids"] for item in report["negative_cases"])
    serialized = json.dumps(report, ensure_ascii=False)
    assert "НЕ_ЗАПОВНЮВАТИ" not in serialized and "ПІБ" not in serialized


def test_missing_and_misclassified_results_are_not_hidden_by_total_counts():
    package, expected, snapshot = baseline()
    data = snapshot.model_dump()
    candidates = [
        item for item in data["candidates"] if item["reason"] == "placeholder"
    ]
    removed = candidates[0]
    data["candidates"].remove(removed)
    data["occurrences"] = [
        item for item in data["occurrences"] if item["id"] != removed["occurrence_id"]
    ]
    candidates[1]["reason"] = "blank_line"
    report = evaluate(package, expected, FieldSnapshot.model_validate(data))
    assert report["detectors"]["placeholder"]["false_negatives"] == 2
    assert len(report["detectors"]["placeholder"]["missed_ids"]) == 2
    assert report["detectors"]["blank_line"]["false_positives"] == 1
    empty = FieldSnapshot(source_version_id=UUID(int=0))
    metrics = evaluate(package, expected, empty)["detectors"]
    assert all(
        item["precision"] is None and item["recall"] == 0 for item in metrics.values()
    )
    no_gold = {**expected, "occurrences": []}
    assert all(
        item["recall"] is None
        for item in evaluate(package, no_gold, snapshot)["detectors"].values()
    )


def test_incorrectly_accepted_literal_is_reported_as_confirmed_false_positive():
    package, expected, snapshot = baseline()
    data = snapshot.model_dump()
    literal = next(
        item for item in data["candidates"] if item["source_key"] == "НЕ_ЗАПОВНЮВАТИ"
    )
    data["fields"].append(
        {
            "id": "incorrect",
            "label": "bad",
            "occurrence_ids": [literal["occurrence_id"]],
        }
    )
    data["decisions"].append(
        {"candidate_id": literal["id"], "status": "accepted", "field_id": "incorrect"}
    )
    report = evaluate(package, expected, FieldSnapshot.model_validate(data))
    assert report["incorrect_confirmed_candidate_ids"] == [literal["id"]]
    assert report["inferred_confirmed_candidate_ids"] == [literal["id"]]
    assert report["negative_cases"][4]["accepted_candidate_ids"] == [literal["id"]]


@pytest.mark.parametrize(
    "change, message",
    [
        ("hash", "fixture_digest_mismatch"),
        ("locator", "ambiguous_fixture_locator"),
        ("text", "fixture_text_mismatch"),
        ("negative", "fixture_text_mismatch"),
        ("duplicate", "duplicate_fixture_location"),
    ],
)
def test_invalid_answer_keys_fail_instead_of_producing_successful_scores(
    change, message
):
    package, expected, snapshot = baseline()
    expected = deepcopy(expected)
    if change == "hash":
        expected["sha256"] = "0" * 64
    elif change == "locator":
        expected["occurrences"][0]["paragraph"]["xpath"] = "/w:document/w:body/w:p"
    elif change == "text":
        expected["occurrences"][0]["initial_text"] = "wrong"
    elif change == "negative":
        expected["negative_cases"][0]["initial_text"] = "wrong"
    else:
        expected["occurrences"].append(deepcopy(expected["occurrences"][0]))
    with pytest.raises(ValueError, match=message):
        evaluate(package, expected, snapshot)


def test_projection_accounts_for_tabs_breaks_and_locked_text_without_searching():
    package = DocxPackage(
        archive(
            doc(
                "<w:p><w:r><w:t>😀</w:t><w:tab/><w:br/><w:t>Ї</w:t></w:r>"
                "<w:r><w:t>hidden</w:t><w:drawing/></w:r>"
                "<w:r><w:rPr><w:b/></w:rPr><w:t>{{ІМ</w:t></w:r>"
                "<w:r><w:t>ʼЯ}} {{ІМʼЯ}}</w:t></w:r></w:p>"
            )
        )
    )
    node = package.model["content"][0]["content"][0]
    paragraph = package.elements[node["attrs"]["id"]]
    mapped, length = projection(package, paragraph, node)
    assert mapped[0] == 0 and mapped[1] == 3
    assert all(index not in mapped for index in range(2, 8))
    assert mapped[8] == 5 and length == 22
    locator = {"part": "word/document.xml", "xpath": "/w:document/w:body/w:p"}
    reference = {
        "paragraph": locator,
        "kind": "placeholder",
        "start": 8,
        "end": 16,
        "initial_text": "{{ІМʼЯ}}",
    }
    nodes = {node["attrs"]["id"]: node}
    assert reference_key(package, reference, nodes)[-2:] == (5, 13)
    reference.update(start=17, end=25)
    assert reference_key(package, reference, nodes)[-2:] == (14, 22)
    reference.update(start=2, end=8, initial_text="hidden")
    with pytest.raises(ValueError, match="protected_fixture_location"):
        reference_key(package, reference, nodes)
    reference.update(start=0, end=0, initial_text="")
    with pytest.raises(ValueError, match="nonempty_fixture_location"):
        reference_key(package, reference, nodes)
    assert resolve(package, locator) is paragraph
    assert paragraph.tag == W + "p"


def test_cli_prints_the_same_report(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluation", "/fixtures/docx/v1/client-intake-uk-v1.docx", str(MANIFEST)],
    )
    monkeypatch.delitem(sys.modules, "app.fields.evaluation")
    runpy.run_module("app.fields.evaluation", run_name="__main__")
    assert json.loads(capsys.readouterr().out) == json.loads(REPORT.read_text())


def test_native_value_before_placeholder_uses_model_offsets_without_control_tokens():
    package = DocxPackage(
        archive(
            doc(
                '<w:p><w:sdt><w:sdtPr><w:id w:val="7"/><w:text/></w:sdtPr>'
                "<w:sdtContent><w:r><w:t>😀</w:t><w:tab/><w:t>Ї</w:t></w:r>"
                "</w:sdtContent></w:sdt><w:r><w:t> {{НАЗВА}}</w:t></w:r></w:p>"
            )
        )
    )
    node = package.model["content"][0]["content"][0]
    reference = {
        "paragraph": {"part": "word/document.xml", "xpath": "/w:document/w:body/w:p"},
        "kind": "placeholder",
        "start": 3,
        "end": 12,
        "initial_text": "{{НАЗВА}}",
    }
    key = reference_key(package, reference, {node["attrs"]["id"]: node})
    assert key[-2:] == (4, 13)
    snapshot = discover(package.model, UUID(int=0))
    occurrence = next(
        item for item in snapshot.occurrences if item.anchor.kind == "span"
    )
    assert (occurrence.anchor.start, occurrence.anchor.end) == key[-2:]
