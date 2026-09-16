from copy import deepcopy

import pytest
from test_document_package import archive, doc, walk

from app.documents.export import DocxExport
from app.documents.package import DocxPackage, InvalidDocument, W
from app.documents.rebase import children, correspondence


def fixture():
    return DocxPackage(
        archive(
            doc(
                '<w:p><w:r><w:rPr><w:b/><w:u w:val="single"/>'
                '<w:color w:val="123456"/></w:rPr><w:t>Ґанна</w:t></w:r>'
                '<w:r><w:t> Їжак</w:t></w:r></w:p>'
            )
        )
    )


def test_formatting_roundtrip_preserves_source_and_unrelated_run_properties():
    package = fixture()
    model = deepcopy(package.model)
    texts = [node for node in walk(model) if node["type"] == "text"]
    texts[0]["marks"].append(
        {"type": "format", "attrs": {"bold": False, "italic": True, "underline": False}}
    )
    texts[1]["marks"].append(
        {"type": "format", "attrs": {"bold": True, "italic": None, "underline": True}}
    )
    saved = DocxPackage(DocxExport(package).render(model, package.digest))
    correspondence(model, saved)
    runs = list(saved.roots["word/document.xml"].iter(W + "r"))
    assert runs[0].find(W + "rPr/" + W + "color").get(W + "val") == "123456"
    assert runs[0].find(W + "rPr/" + W + "b").get(W + "val") == "0"
    assert runs[0].find(W + "rPr/" + W + "u").get(W + "val") == "none"
    assert runs[1].find(W + "rPr/" + W + "u").get(W + "val") == "single"
    assert DocxExport(package).render(package.model, package.digest) == package.original
    texts[1]["marks"] = [
        {"type": "format", "attrs": {"bold": True, "italic": False, "underline": None}}
    ]
    reopened = DocxPackage(DocxExport(package).render(model, package.digest))
    correspondence(model, reopened)


@pytest.mark.parametrize(
    "attrs", [None, {}, {"bold": "true", "italic": None, "underline": None}]
)
def test_invalid_formatting_is_rejected(attrs):
    package = fixture()
    model = deepcopy(package.model)
    text = next(node for node in walk(model) if node["type"] == "text")
    text["marks"].append({"type": "format", "attrs": attrs})
    with pytest.raises(InvalidDocument):
        DocxExport(package).render(model, package.digest)
    if attrs is not None:
        with pytest.raises(ValueError, match="copy_format_mismatch"):
            children({"content": [text]})
