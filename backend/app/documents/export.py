"""Apply a validated editor revision to retained OOXML, entirely in memory."""

import hashlib
import io
from copy import deepcopy
from typing import Any
from zipfile import ZipFile

from lxml import etree

from app.documents.package import DocxPackage, InvalidDocument, Node, W

W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def comparable(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: comparable(item)
            for key, item in value.items()
            if not (key == "content" and item == [])
        }
    if isinstance(value, list):
        return [comparable(item) for item in value]
    return value


class DocxExport:
    def __init__(self, package: DocxPackage):
        self.package = package
        self.known: dict[str, Node] = {}
        self.seen: set[str] = set()
        self.locked: set[str] = set()
        self.control_ids: set[str] = set()
        self.paragraph_ids: set[str] = set()
        self.index(package.model)

    def index(self, node: Node) -> None:
        identity = node.get("attrs", {}).get("id")
        if identity:
            self.known[identity] = node
        for child in node.get("content", []):
            self.index(child)
        for mark in node.get("marks", []):
            self.known[mark["attrs"]["id"]] = mark

    def render(self, model: Node, digest: str) -> bytes:
        if digest != self.package.digest:
            raise InvalidDocument("stale_revision")
        self.seen.clear()
        self.locked.clear()
        self.control_ids = {
            element.get(W + "val", "")
            for root in self.package.roots.values()
            for element in root.iter(W + "id")
        }
        self.paragraph_ids = {
            element.get(W14 + "paraId", "").upper()
            for root in self.package.roots.values()
            for element in root.iter(W + "p")
        }
        try:
            if model.get("type") != "doc":
                raise InvalidDocument("invalid_model")
            sections = model["content"]
            originals = self.package.model["content"]
            if len(sections) != len(originals):
                raise InvalidDocument("invalid_structure")
            changed = {}
            for section, original in zip(sections, originals, strict=True):
                if (
                    section.get("type") != "section"
                    or section["attrs"] != original["attrs"]
                ):
                    raise InvalidDocument("invalid_structure")
                part = section["attrs"]["part"]
                root = deepcopy(self.package.roots[part])
                parent = root.find(W + "body") if part == "word/document.xml" else root
                self.blocks(parent, section["content"], original["content"], part)
                if comparable(section) != comparable(original):
                    changed[part] = etree.tostring(
                        root, xml_declaration=True, encoding="UTF-8", standalone=True
                    )
            if self.locked != set(self.package.unsupported):
                raise InvalidDocument("unsupported_change")
        except (
            KeyError,
            TypeError,
            AttributeError,
            ValueError,
            RecursionError,
        ) as error:
            if isinstance(error, InvalidDocument):
                raise
            raise InvalidDocument("invalid_model") from error
        if not changed:
            return self.package.original
        output = io.BytesIO()
        with (
            ZipFile(io.BytesIO(self.package.original)) as source,
            ZipFile(output, "w") as target,
        ):
            target.comment = source.comment
            for entry in source.infolist():
                target.writestr(
                    entry,
                    changed.get(entry.filename, self.package.parts[entry.filename]),
                )
        result = output.getvalue()
        DocxPackage(result)  # Reapply package bounds and parser invariants.
        return result

    def anchor(self, node: Node, part: str) -> Any:
        identity = node["attrs"]["id"]
        original = self.known.get(identity)
        if (
            original is None
            or original["type"] != node["type"]
            or original["attrs"] != node["attrs"]
            or not identity.startswith(part + ":")
            or identity in self.seen
        ):
            raise InvalidDocument("invalid_anchor")
        self.seen.add(identity)
        return deepcopy(self.package.elements[identity])

    def reviewed_field(self, node: Node, part: str) -> Any:
        original = self.known.get(node["attrs"]["id"])
        if original is None or original["type"] != "field":
            raise InvalidDocument("invalid_anchor")
        attrs = node["attrs"]
        # Only alias and explicit grouping key may change; identity stays immutable.
        anchored = {
            **node,
            "attrs": {
                **attrs,
                "key": original["attrs"]["key"],
                "label": original["attrs"]["label"],
            },
        }
        element = self.anchor(anchored, part)
        properties = element.find(W + "sdtPr")
        for name, tag, limit in (("key", "tag", 512), ("label", "alias", 256)):
            if attrs[name] == original["attrs"][name]:
                continue
            self.field_property(attrs[name], limit)
            matches = properties.findall(W + tag)
            if len(matches) > 1:
                raise InvalidDocument("invalid_field")
            prop = matches[0] if matches else etree.SubElement(properties, W + tag)
            prop.set(W + "val", attrs[name])
        return element

    @staticmethod
    def field_property(value: Any, limit: int) -> None:
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > limit
            or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value)
        ):
            raise InvalidDocument("invalid_field")

    def blocks(
        self, parent: Any, nodes: list[Node], originals: list[Node], part: str
    ) -> None:
        def fixed(items: list[Node]) -> list[str]:
            return [n["attrs"]["id"] for n in items if n["type"] != "paragraph"]

        if fixed(nodes) != fixed(originals):
            raise InvalidDocument("invalid_structure")
        allowed = {n["attrs"]["id"] for n in originals}
        retained = {n["attrs"]["id"] for n in nodes}
        for missing in allowed - retained:
            if (
                self.package.elements[missing].find(W + "pPr/" + W + "sectPr")
                is not None
            ):
                raise InvalidDocument("unsupported_change")
        rendered = []
        for node in nodes:
            identity = node["attrs"]["id"]
            kind = node["type"]
            if kind == "paragraph" and identity.startswith("new:"):
                source_id, suffix = identity[4:].rsplit(":", 1)
                original = self.known.get(source_id)
                if (
                    original is None
                    or original["type"] != "paragraph"
                    or source_id not in allowed
                    or len(suffix) != 32
                    or any(c not in "0123456789abcdef" for c in suffix)
                    or identity in self.seen
                    or {**node["attrs"], "id": source_id} != original["attrs"]
                ):
                    raise InvalidDocument("invalid_anchor")
                self.seen.add(identity)
                element = deepcopy(self.package.elements[source_id])
                native = (
                    int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16)
                    % 2147483647
                )
                while f"{native:08X}" in self.paragraph_ids:
                    native = (native + 1) % 2147483647
                self.paragraph_ids.add(f"{native:08X}")
                element.set(W14 + "paraId", f"{native:08X}")
                element.attrib.pop(W14 + "textId", None)
                # A duplicated paragraph must not duplicate a section boundary.
                for section in element.findall(W + "pPr/" + W + "sectPr"):
                    section.getparent().remove(section)
            else:
                if identity not in allowed:
                    raise InvalidDocument("invalid_structure")
                element = self.anchor(node, part)
                original = self.known[identity]
            if kind == "paragraph":
                self.replace_inlines(element, node.get("content", []), part)
            elif kind in {"table", "tableRow", "tableCell"}:
                self.blocks(element, node["content"], original["content"], part)
            else:
                self.preserve_locked(node, original)
            if comparable(node) == comparable(original):
                element = deepcopy(self.package.elements[identity])
            rendered.append(element)
        # Keep source container properties, including body section geometry.
        properties = {
            W + name for name in ("sectPr", "tblPr", "tblGrid", "trPr", "tcPr")
        }
        for child in list(parent):
            if child.tag not in properties:
                parent.remove(child)
        boundary = parent.find(W + "sectPr")
        for element in rendered:
            if boundary is None:
                parent.append(element)
            else:
                boundary.addprevious(element)

    def preserve_locked(self, node: Node, original: Node) -> None:
        if node != original:
            raise InvalidDocument("unsupported_change")
        self.locked.add(node["attrs"]["id"])

    def checkbox(self, node: Node, part: str) -> Any:
        """Emit the anchored checkbox SDT; only its checked state may change."""
        identity = node["attrs"]["id"]
        original = self.known.get(identity)
        attrs = node["attrs"]
        if (
            original is None
            or original["type"] != "checkbox"
            or set(attrs) != {"id", "checked"}
            or type(attrs["checked"]) is not bool
            or not identity.startswith(part + ":")
            or identity in self.seen
        ):
            raise InvalidDocument("invalid_anchor")
        self.seen.add(identity)
        if attrs["checked"] == original["attrs"]["checked"]:
            return deepcopy(self.package.elements[identity])
        element = deepcopy(self.package.elements[identity])
        control = element.find(W + "sdtPr/" + W14 + "checkbox")
        state = control.find(W14 + "checked")
        if state is None:
            state = etree.SubElement(control, W14 + "checked")
        state.set(W14 + "val", "1" if attrs["checked"] else "0")
        states = {}
        for name, default in (("checkedState", "2612"), ("uncheckedState", "2610")):
            marker = control.find(W14 + name)
            value = default if marker is None else (marker.get(W14 + "val") or default)
            if (
                not isinstance(value, str)
                or len(value) > 6
                or any(char not in "0123456789abcdefABCDEF" for char in value)
                or int(value, 16) > 0x10FFFF
            ):
                raise InvalidDocument("invalid_anchor")
            states[name] = value
        wanted = "checkedState" if attrs["checked"] else "uncheckedState"
        glyph = chr(int(states[wanted], 16))
        previous = chr(
            int(
                states["uncheckedState" if attrs["checked"] else "checkedState"],
                16,
            )
        )
        for text in element.iter(W + "t"):
            if text.text == previous:
                text.set(XML_SPACE, "preserve")
                text.text = glyph
        return element

    def replace_inlines(self, parent: Any, nodes: list[Node], part: str) -> None:
        for child in list(parent):
            if child.tag != W + "pPr":
                parent.remove(child)
        for node in nodes:
            kind = node["type"]
            if kind == "text":
                element = self.text(node, part)
            elif kind == "field":
                identity = node["attrs"]["id"]
                if identity in self.known:
                    element = self.reviewed_field(node, part)
                else:
                    element = self.new_field(node)
                if any(child["type"] != "text" for child in node.get("content", [])):
                    raise InvalidDocument("invalid_field")
                content_changed = identity not in self.known or comparable(
                    node.get("content", [])
                ) != comparable(self.known[identity].get("content", []))
                if content_changed:
                    content = element.find(W + "sdtContent")
                    if content is None:
                        content = etree.SubElement(element, W + "sdtContent")
                    self.replace_inlines(content, node.get("content", []), part)
                    if any(
                        "\n" in child["text"] or "\t" in child["text"]
                        for child in node.get("content", [])
                    ):
                        element.find(W + "sdtPr/" + W + "text").set(
                            W + "multiLine", "1"
                        )
                    placeholder = element.find(W + "sdtPr/" + W + "showingPlcHdr")
                    if placeholder is not None:
                        placeholder.getparent().remove(placeholder)
            elif kind == "lockedInline":
                element = self.anchor(node, part)
                self.preserve_locked(node, self.known[node["attrs"]["id"]])
            elif kind == "checkbox":
                element = self.checkbox(node, part)
            else:
                raise InvalidDocument("invalid_inline")
            parent.append(element)

    def text(self, node: Node, part: str) -> Any:
        value = node["text"]
        if not isinstance(value, str) or not value or len(value) > 1_000_000:
            raise InvalidDocument("invalid_text")
        marks = node.get("marks", [])
        element = etree.Element(W + "r")
        if marks:
            if len(marks) != 1 or marks[0].get("type") != "source":
                raise InvalidDocument("invalid_marks")
            mark = marks[0]
            identity = mark["attrs"]["id"]
            if self.known.get(identity) != mark or not identity.startswith(part + ":"):
                raise InvalidDocument("invalid_marks")
            element = deepcopy(self.package.elements[identity])
            for child in list(element):
                if child.tag != W + "rPr":
                    element.remove(child)
        for index, line in enumerate(value.split("\n")):
            if index:
                etree.SubElement(element, W + "br")
            for tab, text in enumerate(line.split("\t")):
                if tab:
                    etree.SubElement(element, W + "tab")
                if text:
                    child = etree.SubElement(element, W + "t")
                    child.set(XML_SPACE, "preserve")
                    child.text = text
        return element

    def new_field(self, node: Node) -> Any:
        attrs = node["attrs"]
        identity = attrs["id"]
        if (
            not isinstance(identity, str)
            or len(identity) != 32
            or any(char not in "0123456789abcdef" for char in identity)
            or identity in self.seen
            or set(attrs) != {"id", "key", "label"}
        ):
            raise InvalidDocument("invalid_field")
        self.field_property(attrs["key"], 512)
        self.field_property(attrs["label"], 256)
        self.seen.add(identity)
        native = int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16) % 2147483647
        while str(native) in self.control_ids:
            native = (native + 1) % 2147483647
        self.control_ids.add(str(native))
        element = etree.Element(W + "sdt")
        properties = etree.SubElement(element, W + "sdtPr")
        for name, value in [
            ("id", str(native)),
            ("tag", attrs["key"]),
            ("alias", attrs["label"]),
        ]:
            etree.SubElement(properties, W + name).set(W + "val", value)
        etree.SubElement(properties, W + "text").set(W + "multiLine", "1")
        return element
