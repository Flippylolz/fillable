"""Bounded OOXML import with revision-local identities and retained source parts."""

import hashlib
import io
import re
from typing import Any
from xml.etree.ElementTree import Element
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
Node = dict[str, Any]


class InvalidDocument(ValueError):
    """The package is invalid or exceeds bounded prototype processing limits."""


class DocxPackage:
    def __init__(self, data: bytes):
        if len(data) > 10 * 1024 * 1024:
            raise InvalidDocument("archive_limit")
        try:
            with ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                names = [entry.filename for entry in entries]
                if (
                    len(entries) > 256
                    or len(names) != len(set(names))
                    or sum(e.file_size for e in entries) > 50 * 1024 * 1024
                    or any(e.flag_bits & 1 for e in entries)
                ):
                    raise InvalidDocument("package_limit")
                self.parts = {name: archive.read(name) for name in names}
            if "word/document.xml" not in self.parts:
                raise InvalidDocument("missing_document")
            self.roots = {
                name: ElementTree.fromstring(content, forbid_dtd=True)
                for name, content in self.parts.items()
                if name.endswith(".xml")
            }
        except (
            BadZipFile,
            KeyError,
            ElementTree.ParseError,
            DefusedXmlException,
            RuntimeError,
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
                self.positions = {id(el): str(i) for i, el in enumerate(root.iter())}
                content = self.blocks(parent)
                sections.append(
                    {"type": "section", "attrs": {"part": name}, "content": content}
                )
        self.model: Node = {"type": "doc", "content": sections}

    def identity(self, element: Element) -> str:
        key = self.part + ":" + self.positions[id(element)]
        self.elements[key] = element
        return key

    def locked(self, element: Element, inline: bool) -> Node:
        key = self.identity(element)
        self.unsupported.append(key)
        return {
            "type": "lockedInline" if inline else "lockedBlock",
            "attrs": {"id": key, "label": "".join(element.itertext())},
        }

    def blocks(self, parent: Element) -> list[Node]:
        result = []
        for el in parent:
            tag = el.tag.removeprefix(W)
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
            if el.tag == W + "pPr":
                continue
            if el.tag == W + "r":
                if any(child.tag not in {W + "rPr", W + "t"} for child in el):
                    result.append(self.locked(el, True))
                    continue
                text = "".join(t.text or "" for t in el.findall(W + "t"))
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
                children = [] if content is None else self.inlines(content)
                if any(node["type"] != "text" for node in children):
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
            else:
                result.append(self.locked(el, True))
        return result
