"""Read-only, bounded source layout. Never part of the editable/save model."""

import re
from typing import Any

from app.documents.drawing_presentation import display
from app.documents.package import DocxPackage, W


def number(value, divisor=20, lower=0, upper=4000):
    try:
        result = int(value) / divisor
        return result if lower <= result <= upper else None
    except (TypeError, ValueError):
        return None


def value(element, path, attribute="val"):
    child = (
        None
        if element is None
        else element.find("/".join(W + p for p in path.split("/")))
    )
    return None if child is None else child.get(W + attribute)


def length(style, name, raw, divisor=20, lower=0):
    parsed = number(raw, divisor, lower)
    if parsed is not None:
        style[name] = f"{parsed:g}pt"


def properties(root, style):
    if root is None:
        return
    font = value(root, "rFonts", "ascii") or value(root, "rFonts", "hAnsi")
    if font and re.fullmatch(r"[\w -]{1,80}", font):
        style["font-family"] = f'"{font}"'
    length(style, "font-size", value(root, "sz"), 2)
    for tag, name, on, off in [
        ("b", "font-weight", "bold", "normal"),
        ("i", "font-style", "italic", "normal"),
        ("u", "text-decoration", "underline", "none"),
    ]:
        el = root.find(W + tag)
        if el is not None:
            style[name] = off if el.get(W + "val") in {"0", "false", "none"} else on
    color = value(root, "color")
    if color and re.fullmatch(r"[0-9a-fA-F]{6}", color):
        style["color"] = "#" + color
    for tag, attr, name in [
        ("spacing", "before", "margin-top"),
        ("spacing", "after", "margin-bottom"),
        ("ind", "left", "margin-left"),
        ("ind", "right", "margin-right"),
        ("ind", "firstLine", "text-indent"),
    ]:
        length(style, name, value(root, tag, attr))
    hanging = number(value(root, "ind", "hanging"))
    if hanging is not None:
        style["text-indent"] = f"{-hanging:g}pt"
    line = value(root, "spacing", "line")
    rule = value(root, "spacing", "lineRule")
    if line is not None:
        parsed = number(line, 240 if rule in {None, "auto"} else 20)
        if parsed is not None:
            style["line-height"] = f"{parsed:g}" + (
                "" if rule in {None, "auto"} else "pt"
            )
    align = value(root, "jc")
    if align in {"left", "center", "right", "both"}:
        style["text-align"] = "justify" if align == "both" else align
    for tag, name, on in [
        ("caps", "text-transform", "uppercase"),
        ("smallCaps", "font-variant", "small-caps"),
    ]:
        node = root.find(W + tag)
        if node is not None:
            style[name] = (
                ("none" if tag == "caps" else "normal")
                if node.get(W + "val") in {"0", "false"}
                else on
            )
    if root.find(W + "pageBreakBefore") is not None:
        style["break-before"] = "page"


class Layout:
    def __init__(self, package):
        self.package = package
        self.float_end = 0.0
        root = package.roots.get("word/styles.xml")
        self.styles = (
            {}
            if root is None
            else {s.get(W + "styleId"): s for s in root.findall(W + "style")}
        )
        self.defaults = {
            "font-family": '"Times New Roman"',
            "font-size": "11pt",
            "color": "#000000",
            "line-height": "1.15",
        }
        if root is not None:
            for path in ("docDefaults/rPrDefault/rPr", "docDefaults/pPrDefault/pPr"):
                properties(
                    root.find("/".join(W + p for p in path.split("/"))), self.defaults
                )
        self.default_paragraph = next(
            (
                key
                for key, s in self.styles.items()
                if s.get(W + "default") == "1" and s.get(W + "type") == "paragraph"
            ),
            None,
        )

    def cascade(self, key, result):
        chain: list[Any] = []
        seen = set()
        while key in self.styles and key not in seen and len(chain) < 32:
            seen.add(key)
            node = self.styles[key]
            chain.append(node)
            key = value(node, "basedOn")
        for node in reversed(chain):
            properties(node.find(W + "pPr"), result)
            properties(node.find(W + "rPr"), result)

    def style(self, element):
        self.package.check_deadline()
        result = {}
        tag = element.tag.removeprefix(W)
        if tag == "p":
            result = {
                "margin-top": "0pt",
                "margin-bottom": "0pt",
                "position": "relative",
            }
            self.cascade(value(element, "pPr/pStyle") or self.default_paragraph, result)
            properties(element.find(W + "pPr"), result)
            if any(e.text for e in element.iter(W + "t")):
                result["clear"] = "both"
        if tag == "r":
            parent = element.getparent()
            while parent is not None and parent.tag != W + "p":
                parent = parent.getparent()
            self.cascade(value(parent, "pPr/pStyle") or self.default_paragraph, result)
            self.cascade(value(element, "rPr/rStyle"), result)
            properties(element.find(W + "rPr"), result)
            result = {
                k: v
                for k, v in result.items()
                if k.startswith("font-")
                or k in {"color", "text-decoration", "text-transform"}
            }
        if tag == "tbl":
            result = {"border-collapse": "collapse", "table-layout": "fixed"}
            length(result, "width", value(element, "tblPr/tblW", "w"))
            grid = element.find(W + "tblGrid")
            if grid is not None:
                widths = [number(c.get(W + "w")) for c in grid]
                if widths and all(w is not None for w in widths):
                    result["width"] = f"{sum(widths):g}pt"
            floating = element.find(W + "tblPr/" + W + "tblpPr")
            if floating is not None:
                section = self.package.roots["word/document.xml"].find(
                    W + "body/" + W + "sectPr"
                )
                page = number(value(section, "pgSz", "w")) or 595.3
                left = number(value(section, "pgMar", "left")) or 0
                right = number(value(section, "pgMar", "right")) or 0
                width = float(result.get("width", "0pt")[:-2])
                x = number(floating.get(W + "tblpX")) or 0
                if floating.get(W + "horzAnchor") == "page":
                    x -= left
                if floating.get(W + "tblpXSpec") == "center":
                    x = (page - left - right - width) / 2
                previous = element.getprevious()
                while (
                    previous is not None
                    and previous.tag == W + "p"
                    and not any(e.text for e in previous.iter(W + "t"))
                ):
                    previous = previous.getprevious()
                if (
                    previous is None
                    or previous.find(W + "tblPr/" + W + "tblpPr") is None
                ):
                    self.float_end = 0.0
                result.update(
                    {
                        "display": "inline-table",
                        "float": "left",
                        "vertical-align": "top",
                        "margin-left": f"{max(0, x - self.float_end):g}pt",
                    }
                )
                length(result, "margin-top", floating.get(W + "tblpY"))
                # Word permits anchored tables to extend into the page margin.
                # CSS floats otherwise wrap at the content edge (including rounding).
                result["margin-right"] = (
                    f"{min(0, page - left - right - x - width - 2):g}pt"
                )
                self.float_end = x + width
        if tag == "tr":
            length(result, "height", value(element, "trPr/trHeight"))
        if tag == "tc":
            result = {"vertical-align": "top", "padding": "0pt", "border": "none"}
            length(result, "width", value(element, "tcPr/tcW", "w"))
            align = value(element, "tcPr/vAlign")
            if align in {"center", "bottom"}:
                result["vertical-align"] = "middle" if align == "center" else align
            table = element.getparent().getparent()
            grid = table.find(W + "tblGrid")
            if grid is not None:
                cells = list(element.getparent())
                preceding = [
                    c for c in cells[: cells.index(element)] if c.tag == W + "tc"
                ]
                start = sum(int(value(c, "tcPr/gridSpan") or 1) for c in preceding)
                span = int(value(element, "tcPr/gridSpan") or 1)
                widths = [
                    number(c.get(W + "w")) for c in list(grid)[start : start + span]
                ]
                if len(widths) == span and all(w is not None for w in widths):
                    result["width"] = f"{sum(widths):g}pt"
            for side in ("top", "bottom", "left", "right"):
                for root, path in [
                    (table, "tblPr/tblCellMar"),
                    (element, "tcPr/tcMar"),
                ]:
                    length(
                        result, "padding-" + side, value(root, path + "/" + side, "w")
                    )
                for root, path in [
                    (table, "tblPr/tblBorders"),
                    (element, "tcPr/tcBorders"),
                ]:
                    border = root.find(
                        "/".join(W + p for p in (path + "/" + side).split("/"))
                    )
                    if border is None and side in {"left", "right"}:
                        edge = "start" if side == "left" else "end"
                        border = root.find(
                            "/".join(W + p for p in (path + "/" + edge).split("/"))
                        )
                    if border is not None:
                        kind = border.get(W + "val")
                        size = number(border.get(W + "sz"), 8, 0, 12)
                        color = border.get(W + "color", "000000")
                        color = (
                            color
                            if re.fullmatch(r"[0-9a-fA-F]{6}", color)
                            else "000000"
                        )
                        result["border-" + side] = (
                            "none"
                            if kind in {"nil", "none"}
                            else f"{size or 0.5:g}pt solid #{color}"
                        )
        if (
            tag == "tc"
            and element.getparent().getparent().find(W + "tblPr/" + W + "tblpPr")
            is not None
        ):
            result["width"] = "auto"
        if tag in {"tbl", "tc"}:
            result["box-sizing"] = "border-box"
        return result

    def render(self):
        nodes = {key: self.style(el) for key, el in self.package.elements.items()}
        section = dict(self.defaults)
        section.update(
            {
                "box-sizing": "border-box",
                "background": "white",
                "margin": "0 auto",
                "padding": "72pt",
                "width": "595.3pt",
                "min-height": "841.9pt",
            }
        )
        body = self.package.roots["word/document.xml"].find(W + "body")
        sect = body.find(W + "sectPr")
        length(section, "width", value(sect, "pgSz", "w"))
        length(section, "min-height", value(sect, "pgSz", "h"))
        for side in ("top", "bottom", "left", "right"):
            length(section, "padding-" + side, value(sect, "pgMar", side))
        locked = {
            key: display(self.package.elements[key]) for key in self.package.unsupported
        }
        return {"nodes": nodes, "section": section, "locked": locked}


def presentation(owner, original_file_id):
    from app.documents.package import ARCHIVE_BYTES
    from app.storage.configuration import configured

    with configured().read(owner, original_file_id) as stream:
        package = DocxPackage(stream.read(ARCHIVE_BYTES + 1))
    return Layout(package).render()
