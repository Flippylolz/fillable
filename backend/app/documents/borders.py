"""Bounded OOXML border presentation, including internal table edges."""

import re

from app.documents.package import W


def border_css(element):
    if element is None:
        return None
    kind = element.get(W + "val")
    if kind in {"nil", "none"}:
        return "none"
    try:
        width = int(element.get(W + "sz", "4")) / 8
    except ValueError:
        width = 0.5
    if not 0 <= width <= 12:
        width = 0.5
    color = element.get(W + "color", "000000")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        color = "000000"
    style = {
        "double": "double",
        "dotted": "dotted",
        "dashed": "dashed",
        "dashSmallGap": "dashed",
        "dotDash": "dashed",
    }.get(kind, "solid")
    return f"{width:g}pt {style} #{color}"


def edge(root, name):
    if root is None:
        return None
    node = root.find(W + name)
    if node is None and name in {"left", "right"}:
        node = root.find(W + ("start" if name == "left" else "end"))
    return node


def property_borders(root, result):
    if root is None:
        return
    run = border_css(root.find(W + "bdr"))
    if run is not None:
        result["border"] = run
    paragraph = root.find(W + "pBdr")
    for side in ("top", "bottom", "left", "right"):
        border = border_css(edge(paragraph, side))
        if border is not None:
            result["border-" + side] = border


def cell_borders(cell, table_properties):
    row = cell.getparent()
    rows = row.getparent().findall(W + "tr")
    cells = row.findall(W + "tc")
    internal = {
        "top": row is not rows[0],
        "bottom": row is not rows[-1],
        "left": cell is not cells[0],
        "right": cell is not cells[-1],
    }
    result = {}
    for side in internal:
        name = (
            ("insideH" if side in {"top", "bottom"} else "insideV")
            if internal[side]
            else side
        )
        for properties in table_properties:
            root = None if properties is None else properties.find(W + "tblBorders")
            border = border_css(edge(root, name))
            if border is not None:
                result["border-" + side] = border
        border = border_css(edge(cell.find(W + "tcPr/" + W + "tcBorders"), side))
        if border is not None:
            result["border-" + side] = border
    return result
