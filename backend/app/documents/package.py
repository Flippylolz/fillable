"""Bounded OOXML import with revision-local identities and retained source parts."""

import hashlib
import io
import re
import stat
import time
import zlib
from typing import Any
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from lxml import etree

Element = Any

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
Node = dict[str, Any]


class InvalidDocument(ValueError):
    """The package is invalid or exceeds bounded processing limits."""


ARCHIVE_BYTES = 10 * 1024 * 1024
EXPANDED_BYTES = 50 * 1024 * 1024
XML_ELEMENTS = 100_000
PROCESS_SECONDS = 5


def safe_part_name(name):
    return (
        bool(name)
        and len(name) <= 512
        and not any(ord(char) < 32 for char in name)
        and not any(char in name for char in "\\:%?#")
        and all(part not in {"", ".", ".."} for part in name.rstrip("/").split("/"))
    )


def parse_xml(content: bytes) -> Element:
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        huge_tree=False,
        remove_blank_text=False,
        strip_cdata=False,
        recover=False,
    )
    root = etree.fromstring(content, parser)
    if root.getroottree().docinfo.doctype:
        raise InvalidDocument("invalid_package")
    return root


class DocxPackage:
    def __init__(self, data: bytes):
        self.deadline = time.monotonic() + PROCESS_SECONDS
        if len(data) > ARCHIVE_BYTES:
            raise InvalidDocument("archive_limit")
        try:
            with ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                names = [entry.filename for entry in entries]
                if (
                    len(entries) > 256
                    or len(names) != len(set(names))
                    or sum(e.file_size for e in entries) > EXPANDED_BYTES
                    or any(e.flag_bits & 1 for e in entries)
                ):
                    raise InvalidDocument("package_limit")
                self.parts = {}
                total = 0
                for entry in entries:
                    if (
                        not safe_part_name(entry.filename)
                        or entry.orig_filename != entry.filename
                        or entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                        or stat.S_IFMT(entry.external_attr >> 16)
                        not in {0, stat.S_IFREG, stat.S_IFDIR}
                    ):
                        raise InvalidDocument("invalid_package")
                    chunks = []
                    with archive.open(entry) as source:
                        while chunk := source.read(
                            min(65536, EXPANDED_BYTES - total + 1)
                        ):
                            self.check_deadline()
                            total += len(chunk)
                            if total > EXPANDED_BYTES:
                                raise InvalidDocument("package_limit")
                            chunks.append(chunk)
                    self.parts[entry.filename] = b"".join(chunks)
            if "word/document.xml" not in self.parts:
                raise InvalidDocument("missing_document")
            self.roots = {}
            elements = 0
            for name, content in self.parts.items():
                if name.lower().endswith((".xml", ".rels")):
                    root = parse_xml(content)
                    for _ in root.iter():
                        elements += 1
                        if elements > XML_ELEMENTS:
                            raise InvalidDocument("package_limit")
                    self.roots[name] = root
                self.check_deadline()
        except (
            BadZipFile,
            KeyError,
            etree.XMLSyntaxError,
            RuntimeError,
            NotImplementedError,
            EOFError,
            UnicodeError,
            zlib.error,
        ) as error:
            raise InvalidDocument("invalid_package") from error
        self.digest = hashlib.sha256(data).hexdigest()
        self.original = data
        self.elements: dict[str, Element] = {}
        self.unsupported: list[str] = []
        sections = []
        for name in sorted(self.roots):
            if re.fullmatch(r"word/(document|header\d+|footer\d+)\.xml", name):
                root = self.roots[name]
                parent = root.find(W + "body") if name == "word/document.xml" else root
                if parent is None:
                    raise InvalidDocument("missing_body")
                self.part = name
                self.positions = {el: str(i) for i, el in enumerate(root.iter())}
                blocks = self.blocks(parent)
                sections.append(
                    {"type": "section", "attrs": {"part": name}, "content": blocks}
                )
        self.model: Node = {"type": "doc", "content": sections}

    def check_deadline(self):
        if time.monotonic() > self.deadline:
            raise InvalidDocument("processing_limit")

    def identity(self, element: Element) -> str:
        key = self.part + ":" + self.positions[element]
        self.elements[key] = element
        return key

    def locked(self, element: Element, inline: bool) -> Node:
        key = self.identity(element)
        self.unsupported.append(key)
        return {
            "type": "lockedInline" if inline else "lockedBlock",
            "attrs": {
                "id": key,
                "label": "".join(element.itertext())
                if isinstance(element.tag, str)
                else element.text or "",
            },
        }

    def blocks(self, parent: Element) -> list[Node]:
        result = []
        for el in parent:
            self.check_deadline()
            tag = el.tag.removeprefix(W) if isinstance(el.tag, str) else ""
            if tag in {"sectPr", "tblPr", "tblGrid", "trPr", "tcPr"}:
                continue
            attrs: dict[str, Any] = {"id": self.identity(el)}
            if tag == "p":
                align = el.find(W + "pPr/" + W + "jc")
                value = "" if align is None else align.get(W + "val", "")
                attrs["align"] = (
                    value if value in {"left", "center", "right", "both"} else "left"
                )
                attrs["numbered"] = el.find(W + "pPr/" + W + "numPr") is not None
                result.append(
                    {"type": "paragraph", "attrs": attrs, "content": self.inlines(el)}
                )
            elif tag in {"tbl", "tr", "tc"}:
                span = el.find(W + "tcPr/" + W + "gridSpan")
                try:
                    attrs["colspan"] = (
                        1 if span is None else int(span.get(W + "val", "1"))
                    )
                except ValueError as error:
                    raise InvalidDocument("invalid_span") from error
                if not 1 <= attrs["colspan"] <= 64:
                    raise InvalidDocument("invalid_span")
                if tag != "tc":
                    attrs.pop("colspan")
                result.append(
                    {
                        "type": {"tbl": "table", "tr": "tableRow", "tc": "tableCell"}[
                            tag
                        ],
                        "attrs": attrs,
                        "content": self.blocks(el),
                    }
                )
            else:
                result.append(self.locked(el, False))
        return result

    def inlines(self, parent: Element) -> list[Node]:
        result = []
        for el in parent:
            self.check_deadline()
            if el.tag == W + "pPr":
                continue
            if el.tag == W + "r":
                if any(
                    child.tag not in {W + "rPr", W + "t", W + "tab", W + "br"}
                    or (
                        child.tag == W + "br"
                        and child.get(W + "type", "textWrapping") != "textWrapping"
                    )
                    for child in el
                ):
                    result.append(self.locked(el, True))
                    continue
                text = "".join(
                    "\n"
                    if child.tag == W + "br"
                    else "\t"
                    if child.tag == W + "tab"
                    else child.text or ""
                    if child.tag == W + "t"
                    else ""
                    for child in el
                )
                if text:
                    attrs: dict[str, Any] = {"id": self.identity(el)}
                    for key, style_tag in [
                        ("bold", "b"),
                        ("italic", "i"),
                        ("underline", "u"),
                    ]:
                        prop = el.find(W + "rPr/" + W + style_tag)
                        attrs[key] = prop is not None and prop.get(W + "val") not in {
                            "0",
                            "false",
                            "none",
                        }
                    result.append(
                        {
                            "type": "text",
                            "text": text,
                            "marks": [{"type": "source", "attrs": attrs}],
                        }
                    )
            elif el.tag == W + "sdt" and el.find(W + "sdtPr/" + W + "text") is not None:
                if any(
                    el.find(W + "sdtPr/" + W + name) is not None
                    for name in ("dataBinding", "lock", "temporary")
                ):
                    result.append(self.locked(el, True))
                    continue
                content = el.find(W + "sdtContent")
                tag = el.find(W + "sdtPr/" + W + "tag")
                tag_value = "" if tag is None else tag.get(W + "val", "")
                alias = el.find(W + "sdtPr/" + W + "alias")
                key = self.identity(el)
                native_id = el.find(W + "sdtPr/" + W + "id")
                if native_id is not None:
                    key = self.part + ":control:" + native_id.get(W + "val", "")
                    if key in self.elements:
                        raise InvalidDocument("duplicate_control")
                    self.elements[key] = el
                previous_unsupported = len(self.unsupported)
                children = [] if content is None else self.inlines(content)
                if any(node["type"] != "text" for node in children):
                    del self.unsupported[previous_unsupported:]
                    result.append(self.locked(el, True))
                    continue
                result.append(
                    {
                        "type": "field",
                        "attrs": {
                            "id": key,
                            "key": tag_value if tag_value.strip() else key,
                            "label": "" if alias is None else alias.get(W + "val", ""),
                        },
                        "content": children,
                    }
                )
            elif (
                el.tag == W + "sdt"
                and el.find(W + "sdtPr/" + W14 + "checkbox") is not None
            ):
                # A native checkbox control keeps its state; the glyph is display only.
                content = el.find(W + "sdtContent")
                previous_unsupported = len(self.unsupported)
                children = [] if content is None else self.inlines(content)
                if any(node["type"] != "text" for node in children):
                    del self.unsupported[previous_unsupported:]
                    result.append(self.locked(el, True))
                    continue
                key = self.identity(el)
                state = el.find(W + "sdtPr/" + W14 + "checkbox/" + W14 + "checked")
                result.append(
                    {
                        "type": "checkbox",
                        "attrs": {
                            "id": key,
                            "checked": state is not None
                            and state.get(W14 + "val") in {"1", "true"},
                        },
                    }
                )
            else:
                result.append(self.locked(el, True))
        return result
