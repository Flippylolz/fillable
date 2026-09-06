import io
import stat
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from lxml import etree

from app.documents import package as source
from app.documents.package import DocxPackage, InvalidDocument, W
from app.documents.validation import CONTENT, MAIN_TYPE, OFFICE, REL, validate_upload


def parts():
    return {
        "[Content_Types].xml": (
            f'<Types xmlns="{CONTENT[1:-1]}">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            f'<Override PartName="/word/document.xml" ContentType="{MAIN_TYPE}"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'<Relationships xmlns="{REL[1:-1]}"><Relationship Id="rId1" '
            f'Type="{OFFICE}officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": (
            f'<w:document xmlns:w="{W[1:-1]}"><w:body><w:p><w:r>'
            "<w:t>Ґанна Їжак</w:t></w:r></w:p></w:body></w:document>"
        ),
    }


def archive(values, compression=ZIP_DEFLATED):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=compression) as output:
        for name, value in values.items():
            output.writestr(name, value)
    return buffer.getvalue()


def test_valid_corpus_and_minimal_package_preserve_every_source_byte():
    corpus = Path("/fixtures/docx/v1/client-intake-uk-v1.docx").read_bytes()
    for data in (corpus, archive(parts())):
        package = validate_upload(data, "Заява Ґанни.DOCX")
        assert package.original == data
        assert package.digest == DocxPackage(data).digest
        with ZipFile(io.BytesIO(data)) as original:
            assert package.parts == {
                name: original.read(name) for name in original.namelist()
            }
    values = parts()
    values["word/"] = ""
    values["word/_rels/document.xml.rels"] = (
        f'<Relationships xmlns="{REL[1:-1]}"><Relationship Id="x" '
        f'Type="{OFFICE}hyperlink" TargetMode="External" '
        'Target="https://example.invalid/private"/><Relationship Id="y" '
        f'Type="{OFFICE}customXml" Target="../custom.xml"/></Relationships>'
    )
    values["custom.xml"] = "<root/>"
    assert validate_upload(archive(values), "x.docx").parts["custom.xml"] == b"<root/>"
    values["word/_rels/document.xml.rels"] = values[
        "word/_rels/document.xml.rels"
    ].replace("../custom.xml", "/custom.xml")
    assert validate_upload(archive(values), "x.docx")


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "x.doc",
        "x.docm",
        "x.dotx",
        "x.pdf",
        "x.docx.exe",
        "../x.docx",
        "C:\\x.docx",
        "x\n.docx",
        "x" * 256 + ".docx",
    ],
)
def test_rejects_unsupported_or_unsafe_names(filename):
    with pytest.raises(InvalidDocument, match="unsupported_document"):
        validate_upload(archive(parts()), filename)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.pop("[Content_Types].xml"),
        lambda p: p.update({"[Content_Types].xml": "<Types/>"}),
        lambda p: p.update({"_rels/.rels": "<Relationships/>"}),
        lambda p: p.pop("_rels/.rels"),
        lambda p: p.update(
            {"word/document.xml": f'<wrong xmlns:w="{W[1:-1]}"><w:body/></wrong>'}
        ),
        lambda p: p.update(
            {
                "word/document.xml": f'<w:document xmlns:w="{W[1:-1]}">'
                "<w:body/><w:body/></w:document>"
            }
        ),
        lambda p: p.update({"undeclared.bin": b"data"}),
        lambda p: p.update(
            {
                "word/settings.xml": f'<w:settings xmlns:w="{W[1:-1]}">'
                "<w:documentProtection/></w:settings>"
            }
        ),
        lambda p: p.update({"word/embeddings/item.xml": "<x/>"}),
        lambda p: p.update(
            {
                "word/document.xml": p["word/document.xml"].replace(
                    "<w:p>", "<w:altChunk/><w:p>"
                )
            }
        ),
    ],
)
def test_rejects_missing_malformed_or_unsupported_structure(mutation):
    values = parts()
    mutation(values)
    with pytest.raises(InvalidDocument):
        validate_upload(archive(values), "x.docx")


@pytest.mark.parametrize(
    "change",
    [
        lambda root: root[0].set("ContentType", ""),
        lambda root: root[2].set(
            "ContentType", "application/vnd.ms-word.document.macroEnabled.main+xml"
        ),
        lambda root: root[2].set("ContentType", "application/xml"),
        lambda root: root[2].set("PartName", "/missing.xml"),
        lambda root: root[2].set("PartName", "word/document.xml"),
        lambda root: root[0].set("Extension", ""),
        lambda root: root.append(etree.fromstring(etree.tostring(root[0]))),
        lambda root: setattr(root[0], "tag", CONTENT + "Unknown"),
    ],
)
def test_content_type_contract(change):
    values = parts()
    root = etree.fromstring(values["[Content_Types].xml"])
    change(root)
    values["[Content_Types].xml"] = etree.tostring(root)
    with pytest.raises(InvalidDocument):
        validate_upload(archive(values), "x.docx")


@pytest.mark.parametrize(
    "attributes",
    [
        {"Target": "../../outside.xml"},
        {"Target": "missing.xml"},
        {"Target": "https://example.invalid/x"},
        {"Target": "//host/x"},
        {"Target": "word/document.xml?query"},
        {"Target": "word\\document.xml"},
        {"Target": "http://[broken"},
        {"TargetMode": "External"},
        {"TargetMode": "unknown"},
        {"Id": ""},
        {"Type": ""},
        {"Target": ""},
        {"Type": OFFICE + "vbaProject"},
        {"Type": OFFICE + "attachedTemplate"},
        {"Type": OFFICE + "oleObject"},
        {"Type": OFFICE + "aFChunk"},
        {"Type": OFFICE + "package"},
        {"Type": OFFICE + "other"},
    ],
)
def test_relationship_targets_and_active_content_are_rejected(attributes):
    values = parts()
    root = etree.fromstring(values["_rels/.rels"])
    root[0].attrib.update(attributes)
    values["_rels/.rels"] = etree.tostring(root)
    with pytest.raises(InvalidDocument):
        validate_upload(archive(values), "x.docx")


def test_relationship_identity_location_and_xml_safety():
    values = parts()
    root = etree.fromstring(values["_rels/.rels"])
    root.append(etree.fromstring(etree.tostring(root[0])))
    values["_rels/.rels"] = etree.tostring(root)
    with pytest.raises(InvalidDocument):
        validate_upload(archive(values), "x.docx")
    for name, content in (
        ("word/bad.rels", f'<Relationships xmlns="{REL[1:-1]}"/>'),
        ("word/_rels/missing.xml.rels", f'<Relationships xmlns="{REL[1:-1]}"/>'),
        (
            "_rels/.rels",
            '<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><x>&x;</x>',
        ),
    ):
        with pytest.raises(InvalidDocument):
            validate_upload(archive({**parts(), name: content}), "x.docx")


def test_xml_relationship_references_must_exist_on_the_same_source_part():
    values = parts()
    values["word/document.xml"] = values["word/document.xml"].replace(
        "<w:p>",
        '<w:p><w:hyperlink xmlns:r="' + OFFICE.rstrip("/") + '" r:id="link"/>',
    )
    with pytest.raises(InvalidDocument, match="invalid_package"):
        validate_upload(archive(values), "x.docx")
    values["word/_rels/document.xml.rels"] = (
        f'<Relationships xmlns="{REL[1:-1]}"><Relationship Id="link" '
        f'Type="{OFFICE}hyperlink" TargetMode="External" '
        'Target="https://example.invalid"/></Relationships>'
    )
    assert validate_upload(archive(values), "x.docx")


def test_zip_limits_are_enforced_on_real_expansion_paths_and_parser_work():
    values = parts()
    values["huge.xml"] = "<x>" + "a" * (51 * 1024 * 1024) + "</x>"
    with pytest.raises(InvalidDocument, match="package_limit"):
        validate_upload(archive(values), "x.docx")
    values = parts()
    values["many.xml"] = "<x>" + "<y/>" * source.XML_ELEMENTS + "</x>"
    with pytest.raises(InvalidDocument, match="package_limit"):
        validate_upload(archive(values), "x.docx")
    values["many.xml"] = "<x>" * 300 + "</x>" * 300
    with pytest.raises(InvalidDocument):
        validate_upload(archive(values), "x.docx")
    with patch.object(source.time, "monotonic", side_effect=[0, 6]):
        with pytest.raises(InvalidDocument, match="processing_limit"):
            validate_upload(archive(parts()), "x.docx")
    with pytest.raises(InvalidDocument):
        validate_upload(archive(parts(), ZIP_BZIP2), "x.docx")
    for path in (
        "../bad",
        "/absolute",
        "a//b",
        "a/./b",
        "a\\b",
        "a%2fb",
        "a:b",
        "a\nb",
    ):
        with pytest.raises(InvalidDocument):
            validate_upload(archive({**parts(), path: ""}), "x.docx")
    entry = ZipInfo("symlink")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(InvalidDocument):
        validate_upload(archive({**parts(), entry: "target"}), "x.docx")


def test_corrupt_truncated_encrypted_and_disguised_binary_packages_fail_closed():
    import struct
    from zipfile import ZIP_STORED

    data = archive(parts(), ZIP_STORED)
    corrupt = data.replace("Ґанна".encode(), "Єанна".encode(), 1)
    encrypted = bytearray(data)
    struct.pack_into("<H", encrypted, encrypted.index(b"PK\x01\x02") + 8, 1)
    for invalid in (
        corrupt,
        data[:-20],
        bytes(encrypted),
        b"\xd0\xcf\x11\xe0" + b"EncryptedPackage",
    ):
        with pytest.raises(InvalidDocument):
            validate_upload(invalid, "looks-valid.docx")
    values = parts()
    values["[Content_Types].xml"] = values["[Content_Types].xml"].replace(
        "</Types>",
        '<Default Extension="bin" ContentType="application/octet-stream"/></Types>',
    )
    values["word/vbaProject.bin"] = b"disguised active content"
    with pytest.raises(InvalidDocument, match="unsupported_document"):
        validate_upload(archive(values), "x.docx")


def test_actual_expansion_budget_does_not_trust_declared_entry_size():
    data = archive(parts())
    # Simulate a ZIP reader returning more than its declared metadata: allocation
    # remains capped and the package is rejected before retaining the extra chunk.
    with (
        patch.object(source, "EXPANDED_BYTES", 1024),
        patch.object(source.ZipFile, "open", return_value=io.BytesIO(b"x" * 1025)),
    ):
        with pytest.raises(InvalidDocument, match="package_limit"):
            DocxPackage(data)
