from copy import deepcopy
from pathlib import Path

import pytest
from test_document_package import archive, doc, walk

from app.documents.export import DocxExport
from app.documents.package import DocxPackage, InvalidDocument, W


def test_original_identity_and_edited_corpus_roundtrip():
    package = DocxPackage(
        Path("/fixtures/docx/v1/client-intake-uk-v1.docx").read_bytes()
    )
    exporter = DocxExport(package)
    assert exporter.render(deepcopy(package.model), package.digest) == package.original
    edited = deepcopy(package.model)
    fields = [node for node in walk(edited) if node["type"] == "field"]
    for field in fields:
        field["content"] = [
            {
                "type": "text",
                "text": "Ґанна Їжак\nЄва\tІлля",
                "marks": field["content"][0]["marks"],
            }
        ]
    first = next(node for node in walk(edited) if node["type"] == "text")
    first["text"] = "Передмова — " + first["text"]
    result = exporter.render(edited, package.digest)
    reopened = DocxPackage(result)
    restored = [node for node in walk(reopened.model) if node["type"] == "field"]
    assert [n["attrs"] for n in restored] == [n["attrs"] for n in fields]
    assert all(n["content"][0]["text"] == "Ґанна Їжак\nЄва\tІлля" for n in restored)
    for name, content in package.parts.items():
        if name != "word/document.xml":
            assert reopened.parts[name] == content
    for name in ("word/styles.xml", "word/numbering.xml"):
        assert reopened.parts[name] == package.parts[name]
    assert (
        reopened.roots["word/document.xml"].nsmap
        == package.roots["word/document.xml"].nsmap
    )
    assert exporter.render(edited, package.digest) == result


def test_create_delete_empty_control_and_source_formatting():
    package = DocxPackage(
        archive(
            doc(
                '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
                "<w:r><w:rPr><w:b/></w:rPr><w:t>Ім’я</w:t></w:r></w:p>"
            )
        )
    )
    model = deepcopy(package.model)
    paragraph = model["content"][0]["content"][0]
    original_text = paragraph["content"][0]
    identity = "a" * 32
    paragraph["content"] = [
        {
            "type": "field",
            "attrs": {"id": identity, "key": identity, "label": "Ім’я"},
            "content": [original_text],
        }
    ]
    saved = DocxPackage(DocxExport(package).render(model, package.digest))
    field = next(n for n in walk(saved.model) if n["type"] == "field")
    assert field["attrs"]["key"] == identity
    assert field["content"][0]["marks"][0]["attrs"]["bold"]
    empty = deepcopy(saved.model)
    next(n for n in walk(empty) if n["type"] == "field")["content"] = []
    blank = DocxPackage(DocxExport(saved).render(empty, saved.digest))
    assert next(n for n in walk(blank.model) if n["type"] == "field")["content"] == []
    deleted = deepcopy(saved.model)
    deleted["content"][0]["content"][0]["content"] = field["content"]
    unwrapped = DocxPackage(DocxExport(saved).render(deleted, saved.digest))
    assert not any(n["type"] == "field" for n in walk(unwrapped.model))
    assert (
        unwrapped.roots["word/document.xml"].find(".//" + W + "jc").get(W + "val")
        == "center"
    )


def test_rejects_stale_revision_and_invalid_models():
    package = DocxPackage(archive(doc("<w:p><w:r><w:t>value</w:t></w:r></w:p>")))
    exporter = DocxExport(package)
    with pytest.raises(InvalidDocument, match="stale_revision"):
        exporter.render(package.model, "wrong")
    for model in (
        {},
        {"type": "doc"},
        {"type": "doc", "content": []},
        {"type": "doc", "content": [None]},
    ):
        with pytest.raises(InvalidDocument):
            exporter.render(model, package.digest)
    altered = deepcopy(package.model)
    altered["content"][0]["content"][0]["attrs"]["id"] = "unknown"
    with pytest.raises(InvalidDocument):
        exporter.render(altered, package.digest)


def test_paragraph_splitting_deletion_and_section_protection():
    package = DocxPackage(
        archive(
            doc(
                '<w:p><w:pPr><w:jc w:val="right"/></w:pPr>'
                "<w:r><w:t>before after</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>delete</w:t></w:r></w:p>"
            )
        )
    )
    model = deepcopy(package.model)
    blocks = model["content"][0]["content"]
    created = deepcopy(blocks[0])
    created["attrs"]["id"] = "new:" + blocks[0]["attrs"]["id"] + ":" + "b" * 32
    blocks[0]["content"][0]["text"] = "before"
    created["content"][0]["text"] = "after"
    blocks[:] = [blocks[0], created]
    saved = DocxPackage(DocxExport(package).render(model, package.digest))
    assert [n["text"] for n in walk(saved.model) if n["type"] == "text"] == [
        "before",
        "after",
    ]
    assert all(
        n["attrs"]["align"] == "right"
        for n in walk(saved.model)
        if n["type"] == "paragraph"
    )
    created["attrs"]["id"] += "invalid"
    with pytest.raises(InvalidDocument, match="invalid_anchor"):
        DocxExport(package).render(model, package.digest)
    protected = DocxPackage(archive(doc("<w:p><w:pPr><w:sectPr/></w:pPr></w:p><w:p/>")))
    removed = deepcopy(protected.model)
    removed["content"][0]["content"].pop(0)
    with pytest.raises(InvalidDocument, match="unsupported_change"):
        DocxExport(protected).render(removed, protected.digest)


def test_invalid_edits_never_mutate_original_and_locked_content_cannot_disappear():
    package = DocxPackage(
        archive(
            doc(
                "<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>text</w:t></w:r>"
                "<w:hyperlink><w:r><w:t>locked</w:t></w:r></w:hyperlink></w:p>"
            )
        )
    )
    original = deepcopy(package.model)
    mutations = [
        lambda p: p["attrs"].update(align="center"),
        lambda p: p["content"].pop(),
        lambda p: p["content"][-1]["attrs"].update(label="changed"),
        lambda p: p["content"][0].update(text=""),
        lambda p: p["content"][0].update(text=10),
        lambda p: p["content"][0].update(marks=[{"type": "bold"}]),
        lambda p: p["content"][0]["marks"][0]["attrs"].update(bold=False),
        lambda p: p["content"][0].update(type="unknown"),
        lambda p: p["content"].append(deepcopy(p["content"][-1])),
    ]
    for mutate in mutations:
        model = deepcopy(original)
        mutate(model["content"][0]["content"][0])
        with pytest.raises(InvalidDocument):
            DocxExport(package).render(model, package.digest)
        assert package.model == original
    model = deepcopy(original)
    model["content"][0]["attrs"]["part"] = "word/header99.xml"
    with pytest.raises(InvalidDocument):
        DocxExport(package).render(model, package.digest)


def test_new_controls_collision_checks_and_invalid_nested_content():
    package = DocxPackage(archive(doc("<w:p><w:r><w:t>source</w:t></w:r></w:p>")))
    exporter = DocxExport(package)
    node = {
        "type": "field",
        "attrs": {"id": "c" * 32, "key": "c" * 32, "label": "Поле"},
        "content": [],
    }
    exporter.control_ids = {
        str(
            int(__import__("hashlib").sha256(("c" * 32).encode()).hexdigest()[:8], 16)
            % 2147483647
        )
    }
    reserved = set(exporter.control_ids)
    assert (
        exporter.new_field(node).find(W + "sdtPr/" + W + "id").get(W + "val")
        not in reserved
    )
    with pytest.raises(InvalidDocument):
        exporter.new_field(node)
    for attrs in ({"id": "invalid"}, {"key": "wrong"}, {"label": " "}, {"label": 10}):
        altered = deepcopy(node)
        altered["attrs"].update(attrs)
        with pytest.raises(InvalidDocument):
            DocxExport(package).new_field(altered)
    model = deepcopy(package.model)
    node["content"] = [{"type": "field"}]
    model["content"][0]["content"][0]["content"] = [node]
    with pytest.raises(InvalidDocument, match="invalid_field"):
        DocxExport(package).render(model, package.digest)


def test_new_paragraph_native_ids_do_not_duplicate_existing_ids():
    import hashlib

    from app.documents.export import W14

    package = DocxPackage(archive(doc("<w:p><w:r><w:t>one</w:t></w:r></w:p>")))
    model = deepcopy(package.model)
    original = model["content"][0]["content"][0]
    created = deepcopy(original)
    identity = "new:" + original["attrs"]["id"] + ":" + "d" * 32
    created["attrs"]["id"] = identity
    native = int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16) % 2147483647
    source = package.elements[original["attrs"]["id"]]
    source.set(W14 + "paraId", f"{native:08X}")
    source.set(W14 + "textId", "00000001")
    model["content"][0]["content"].append(created)
    saved = DocxPackage(DocxExport(package).render(model, package.digest))
    paragraphs = list(saved.roots["word/document.xml"].iter(W + "p"))
    assert len({p.get(W14 + "paraId") for p in paragraphs}) == 2
    assert paragraphs[1].get(W14 + "textId") is None


def test_nested_unsupported_control_is_preserved_as_one_locked_region():
    package = DocxPackage(
        archive(
            doc(
                "<w:p><w:sdt><w:sdtPr><w:text/></w:sdtPr>"
                '<w:sdtContent><w:r><w:br w:type="page"/></w:r></w:sdtContent></w:sdt>'
                "<w:r><w:t>after</w:t></w:r></w:p>"
            )
        )
    )
    assert len(package.unsupported) == 1
    model = deepcopy(package.model)
    next(n for n in walk(model) if n["type"] == "text")["text"] = "edited"
    saved = DocxPackage(DocxExport(package).render(model, package.digest))
    assert (
        saved.roots["word/document.xml"].find(".//" + W + "br").get(W + "type")
        == "page"
    )
