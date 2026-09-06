from copy import deepcopy
from pathlib import Path

import pytest
from lxml import etree
from test_document_package import archive, doc, walk

from app.documents.export import DocxExport
from app.documents.package import DocxPackage, InvalidDocument, W


def native(value="first", properties=""):
    return (
        '<w:sdt><w:sdtPr><w:id w:val="9"/><w:text/>'
        + properties
        + "</w:sdtPr><w:sdtContent><w:r><w:rPr><w:b/></w:rPr><w:t>"
        + value
        + "</w:t></w:r></w:sdtContent></w:sdt>"
    )


def fields(model):
    return [node for node in walk(model) if node["type"] == "field"]


def test_corpus_review_changes_only_explicit_aliases_and_tags_in_native_controls():
    package = DocxPackage(
        Path("/fixtures/docx/v1/client-intake-uk-v1.docx").read_bytes()
    )
    model = deepcopy(package.model)
    controls = fields(model)
    before = deepcopy(controls)
    controls[0]["attrs"].update(label="Імʼя Ґанни", key="СПІЛЬНЕ_ІМʼЯ")
    controls[1]["attrs"].update(label="Інша мітка", key="СПІЛЬНЕ_ІМʼЯ")
    controls[2]["attrs"].update(label="Імʼя Ґанни")  # Equal label does not group.
    data = DocxExport(package).render(model, package.digest)
    reopened = DocxPackage(data)
    after = fields(reopened.model)
    assert [item["attrs"] for item in after] == [item["attrs"] for item in controls]
    assert after[2]["attrs"]["key"] != after[0]["attrs"]["key"]
    assert [item["content"] for item in controls] == [
        item["content"] for item in before
    ]
    assert [item["attrs"]["id"] for item in controls] == [
        item["attrs"]["id"] for item in before
    ]
    assert controls[0]["content"] != controls[1]["content"]
    for original, changed in zip(before, controls, strict=True):
        identity = original["attrs"]["id"]
        expected = deepcopy(package.elements[identity])
        for name, tag in (("key", "tag"), ("label", "alias")):
            if original["attrs"][name] != changed["attrs"][name]:
                expected.find(W + "sdtPr/" + W + tag).set(
                    W + "val", changed["attrs"][name]
                )
        assert etree.tostring(
            reopened.elements[identity], method="c14n", exclusive=True
        ) == etree.tostring(expected, method="c14n", exclusive=True)
    for part, content in package.parts.items():
        if part != "word/document.xml":
            assert reopened.parts[part] == content
    assert package.model != model
    assert DocxExport(package).render(package.model, package.digest) == package.original
    assert DocxExport(reopened).render(reopened.model, reopened.digest) == data


def test_new_controls_share_explicit_unicode_key_but_keep_ids_values_and_marks():
    package = DocxPackage(
        archive(
            doc(
                "<w:p>"
                + native(properties="<w:showingPlcHdr/>")
                + "<w:r><w:rPr><w:i/></w:rPr><w:t>second</w:t></w:r></w:p>"
            )
        )
    )
    model = deepcopy(package.model)
    paragraph = model["content"][0]["content"][0]
    existing, text = paragraph["content"]
    existing["attrs"].update(label="Спільне поле", key="ІМʼЯ_ЇЖАКА")
    paragraph["content"][1] = {
        "type": "field",
        "attrs": {
            "id": "a" * 32,
            "key": "ІМʼЯ_ЇЖАКА",
            "label": "Другий підпис",
        },
        "content": [text],
    }
    reopened = DocxPackage(DocxExport(package).render(model, package.digest))
    controls = fields(reopened.model)
    assert len({item["attrs"]["id"] for item in controls}) == 2
    assert {item["attrs"]["key"] for item in controls} == {"ІМʼЯ_ЇЖАКА"}
    assert [item["content"][0]["text"] for item in controls] == ["first", "second"]
    assert controls[0]["content"][0]["marks"][0]["attrs"]["bold"]
    assert controls[1]["content"][0]["marks"][0]["attrs"]["italic"]
    original_id = existing["attrs"]["id"]
    assert (
        reopened.elements[original_id].find(W + "sdtPr/" + W + "showingPlcHdr")
        is not None
    )
    edited = deepcopy(reopened.model)
    fields(edited)[0]["content"][0]["text"] = "actual edit"
    updated = DocxPackage(DocxExport(reopened).render(edited, reopened.digest))
    assert (
        updated.elements[original_id].find(W + "sdtPr/" + W + "showingPlcHdr") is None
    )


@pytest.mark.parametrize(
    "attrs",
    [
        {"id": "unknown"},
        {"extra": "unsupported"},
        {"key": " "},
        {"label": ""},
        {"key": 3},
        {"label": []},
        {"key": "x" * 513},
        {"label": "x" * 257},
        {"key": "bad\nkey"},
        {"label": "bad\x00label"},
        {"key": "bad\x7f"},
    ],
)
def test_review_rejects_invalid_metadata_and_identity_changes(attrs):
    package = DocxPackage(
        archive(
            doc("<w:p>" + native(properties='<w:alias w:val="Original"/>') + "</w:p>")
        )
    )
    original = deepcopy(package.model)
    model = deepcopy(original)
    fields(model)[0]["attrs"].update(attrs)
    with pytest.raises(InvalidDocument):
        DocxExport(package).render(model, package.digest)
    assert package.model == original
    node = {
        "type": "field",
        "attrs": {"id": "c" * 32, "key": "valid", "label": "valid"},
        "content": [],
    }
    node["attrs"].update(attrs)
    with pytest.raises(InvalidDocument):
        DocxExport(package).new_field(node)


def test_unchanged_legacy_metadata_is_preserved_and_ambiguous_changes_are_rejected():
    package = DocxPackage(
        archive(
            doc(
                "<w:p>"
                + native(
                    properties='<w:alias w:val="'
                    + "x" * 300
                    + '"/><w:tag w:val="legacy"/>'
                    '<w:tag w:val="duplicate"/>'
                )
                + "</w:p>"
            )
        )
    )
    assert DocxExport(package).render(package.model, package.digest) == package.original
    model = deepcopy(package.model)
    fields(model)[0]["attrs"]["key"] = "new"
    with pytest.raises(InvalidDocument, match="invalid_field"):
        DocxExport(package).render(model, package.digest)
    forged = deepcopy(model["content"][0]["content"][0])
    forged["type"] = "field"
    with pytest.raises(InvalidDocument, match="invalid_anchor"):
        DocxExport(package).reviewed_field(forged, "word/document.xml")
