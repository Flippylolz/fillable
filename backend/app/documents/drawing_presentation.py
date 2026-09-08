"""Safe display data for retained simple DrawingML rectangles, never executable XML."""

import re

from app.documents.package import W

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


def display(element):
    # AlternateContent carries duplicate fallback text. Use one representation.
    texts = [
        e.text or ""
        for e in element.iter(W + "t")
        if not any(p.tag == MC + "Fallback" for p in e.iterancestors())
    ]
    shapes = []
    for anchor in element.iter(WP + "anchor"):
        geometry = anchor.find(".//" + A + "prstGeom")
        extent = anchor.find(WP + "extent")
        if geometry is None or geometry.get("prst") != "rect" or extent is None:
            continue
        coordinates = []
        for axis in ("H", "V"):
            position = anchor.find(WP + "position" + axis)
            offset = None if position is None else position.find(WP + "posOffset")
            coordinates.append("0" if offset is None else offset.text)
        try:
            x, y, width, height = [
                int(v) / 12700
                for v in [*coordinates, extent.get("cx"), extent.get("cy")]
            ]
        except (ValueError, TypeError):
            continue
        if (
            not all(-2000 <= v <= 2000 for v in (x, y, width, height))
            or width <= 0
            or height <= 0
        ):
            continue
        fill = anchor.find(".//" + A + "solidFill/" + A + "srgbClr")
        color = "FFFFFF" if fill is None else fill.get("val", "FFFFFF")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            color = "FFFFFF"
        shapes.append(
            {"x": x, "y": y, "width": width, "height": height, "fill": "#" + color}
        )
        if len(shapes) == 32:
            break
    return {"text": "".join(texts), "shapes": shapes}
