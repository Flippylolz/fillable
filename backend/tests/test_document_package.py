import io
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from app.documents.package import DocxPackage, InvalidDocument, W


def archive(xml, extra=None):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as output:
        output.writestr("word/document.xml", xml)
        for name, content in (extra or {}).items():
            output.writestr(name, content)
    return buffer.getvalue()


def doc(body):
    return f'<w:document xmlns:w="{W[1:-1]}"><w:body>{body}</w:body></w:document>'


def walk(node):
    yield node
    for child in node.get("content", []):
        yield from walk(child)


def test_corpus_mapping_preserves_source_and_native_identity():
    data = Path("/fixtures/docx/v1/client-intake-uk-v1.docx").read_bytes()
    package = DocxPackage(data)
    nodes = list(walk(package.model))
    assert package.original == data
    assert package.model == DocxPackage(data).model
    assert len([n for n in nodes if n["type"] == "paragraph"]) == 63
    assert len([n for n in nodes if n["type"] == "table"]) == 2
    fields = [n for n in nodes if n["type"] == "field"]
    assert len(fields) == 5
    assert len({n["attrs"]["id"] for n in fields}) == 5
    assert len({n["attrs"]["key"] for n in fields}) == 4
    assert all(n["attrs"]["id"] in package.elements for n in fields)
    text = "".join(n.get("text", "") for n in nodes)
    assert all(char in text for char in "ҐґЄєІіЇїʼ’")
    assert any(n["attrs"].get("colspan") == 3 for n in nodes if "attrs" in n)
    assert len(package.unsupported) > 0  # Original PAGE field stays locked.
    with ZipFile(io.BytesIO(data)) as original:
        assert package.parts == {
            name: original.read(name) for name in original.namelist()
        }


def test_empty_runs_missing_control_metadata_and_unsupported_structures():
    package = DocxPackage(
        archive(
            doc("""
      <w:p><w:pPr><w:jc w:val="unknown"/></w:pPr><w:r><w:t/></w:r>
      <w:r><w:rPr><w:b w:val="0"/><w:i w:val="false"/><w:u w:val="none"/>
      </w:rPr><w:t>text</w:t></w:r>
      <w:hyperlink><w:r><w:t>preserved link</w:t></w:r></w:hyperlink>
      <w:sdt><w:sdtPr><w:text/></w:sdtPr></w:sdt>
      <w:sdt><w:sdtPr><w:text/><w:alias/><w:tag/></w:sdtPr><w:sdtContent/></w:sdt>
      </w:p><w:altChunk/>
    """)
        )
    )
    nodes = list(walk(package.model))
    run = next(n for n in nodes if n["type"] == "text")
    assert run["marks"][0]["attrs"]["bold"] is False
    assert run["marks"][0]["attrs"]["italic"] is False
    assert run["marks"][0]["attrs"]["underline"] is False
    fields = [n for n in nodes if n["type"] == "field"]
    assert all(n["content"] == [] for n in fields)
    assert all(n["attrs"]["key"] == n["attrs"]["id"] for n in fields)
    assert [n["type"] for n in nodes][-1] == "lockedBlock"
    assert len(package.unsupported) == 2


@pytest.mark.parametrize(
    "data",
    [
        b"bad zip",
        archive("<broken"),
        archive("<root/>"),
        archive('<!DOCTYPE x [<!ENTITY a "boom">]><x>&a;</x>'),
        archive(
            doc(
                '<w:tbl><w:tr><w:tc><w:tcPr><w:gridSpan w:val="65"/>'
                "</w:tcPr></w:tc></w:tr></w:tbl>"
            )
        ),
        b"0" * (10 * 1024 * 1024 + 1),
    ],
)
def test_rejects_invalid_or_unsafe_packages(data):
    with pytest.raises(InvalidDocument):
        DocxPackage(data)


def test_limits_missing_parts_duplicate_entries_and_reader_failures():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as output:
        output.writestr("other.xml", "<x/>")
    with pytest.raises(InvalidDocument, match="missing_document"):
        DocxPackage(buffer.getvalue())
    with ZipFile(buffer, "w") as output:
        for index in range(257):
            output.writestr(str(index), "")
    with pytest.raises(InvalidDocument, match="package_limit"):
        DocxPackage(buffer.getvalue())
    with ZipFile(buffer, "w") as output:
        output.writestr("duplicate", "")
        with pytest.warns(UserWarning):
            output.writestr("duplicate", "")
    with pytest.raises(InvalidDocument, match="package_limit"):
        DocxPackage(buffer.getvalue())
    data = archive(doc("<w:p/>"))
    for changes in [{"file_size": 51 * 1024 * 1024}, {"flag_bits": 1}]:
        with ZipFile(io.BytesIO(data)) as output:
            entries = output.infolist()
        for key, value in changes.items():
            setattr(entries[0], key, value)
        with patch("app.documents.package.ZipFile.infolist", return_value=entries):
            with pytest.raises(InvalidDocument, match="package_limit"):
                DocxPackage(data)
    with patch("app.documents.package.ZipFile.read", side_effect=RuntimeError):
        with pytest.raises(InvalidDocument, match="invalid_package"):
            DocxPackage(data)


def test_control_ids_survive_surrounding_structure_and_rich_content_is_locked():
    control = """<w:sdt><w:sdtPr><w:text/><w:id w:val="42"/></w:sdtPr>
    <w:sdtContent><w:r><w:t>value</w:t></w:r></w:sdtContent></w:sdt>"""
    before = DocxPackage(archive(doc("<w:p>" + control + "</w:p>")))
    after = DocxPackage(
        archive(doc("<w:p><w:r><w:t>prefix</w:t></w:r>" + control + "</w:p>"))
    )

    def field_id(package):
        return next(
            n["attrs"]["id"] for n in walk(package.model) if n["type"] == "field"
        )

    assert field_id(before) == field_id(after)
    with pytest.raises(InvalidDocument, match="duplicate_control"):
        DocxPackage(archive(doc("<w:p>" + control + control + "</w:p>")))
    rich = DocxPackage(
        archive(
            doc("<w:p>" + control.replace("<w:t>value</w:t>", "<w:tab/>") + "</w:p>")
        )
    )
    assert not any(n["type"] == "field" for n in walk(rich.model))
    assert any(n["type"] == "lockedInline" for n in walk(rich.model))
    with pytest.raises(InvalidDocument, match="invalid_span"):
        DocxPackage(
            archive(
                doc(
                    "<w:tbl><w:tr><w:tc><w:tcPr>"
                    '<w:gridSpan w:val="invalid"/>'
                    "</w:tcPr></w:tc></w:tr></w:tbl>"
                )
            )
        )


def test_empty_tags_do_not_link_unrelated_controls():
    control = '<w:sdt><w:sdtPr><w:text/><w:tag w:val=" "/></w:sdtPr></w:sdt>'
    package = DocxPackage(archive(doc("<w:p>" + control + control + "</w:p>")))
    fields = [node for node in walk(package.model) if node["type"] == "field"]
    assert len({node["attrs"]["key"] for node in fields}) == 2
