"""Safe display data for retained simple DrawingML rectangles, never executable XML."""

import re

from lxml import etree

from app.documents.borders import border_css
from app.documents.package import W

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
V = "{urn:schemas-microsoft-com:vml}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"

SHAPES_LIMIT = 32


def _offset(anchor, axis):
    position = anchor.find(WP + "position" + axis)
    offset = None if position is None else position.find(WP + "posOffset")
    return "0" if offset is None else offset.text


def _shape(geometry, extent):
    """Bounded rectangle geometry and border for one prstGeom rect."""
    if geometry is None or geometry.get("prst") != "rect" or extent is None:
        return None
    try:
        width, height = [
            int(v) / 12700 for v in [extent.get("cx"), extent.get("cy")]
        ]
    except (ValueError, TypeError):
        return None
    x = y = 0.0
    if not all(-2000 <= v <= 2000 for v in (x, y, width, height)) or width <= 0 or height <= 0:
        return None
    shape_properties = geometry.getparent()
    fill = shape_properties.find(A + "solidFill/" + A + "srgbClr")
    color = "FFFFFF" if fill is None else fill.get("val", "FFFFFF")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        color = "FFFFFF"
    shape = {"width": width, "height": height, "fill": "#" + color}
    if shape_properties.find(A + "noFill") is not None:
        shape["fill"] = "transparent"
    line = shape_properties.find(A + "ln")
    if line is not None:
        border = etree.Element(W + "border")
        border.set(W + "val", "none" if line.find(A + "noFill") is not None else "single")
        try:
            border.set(W + "sz", str(round(int(line.get("w", "6350")) / 12700 * 8)))
        except ValueError:
            border.set(W + "sz", "4")
        stroke = line.find(A + "solidFill/" + A + "srgbClr")
        if stroke is not None:
            border.set(W + "color", stroke.get("val", "000000"))
        shape["border"] = border_css(border)
    return shape


def _vml_shape(rect):
    """Bounded VML rectangle geometry; legacy fallback for converted forms."""
    style = rect.get("style", "")
    dimensions = {}
    for name in ("width", "height"):
        found = re.search(rf"(?:^|;)\s*{name}\s*:\s*([0-9.]+)(pt|px)\s*(?:;|$)", style)
        if not found:
            return None
        value = float(found.group(1)) * (1 if found.group(2) == "pt" else 0.75)
        if not 0 < value <= 2000:
            return None
        dimensions[name] = value
    fill = rect.get("fillcolor", "")
    shape = {
        "width": dimensions["width"],
        "height": dimensions["height"],
        "fill": "#" + fill.lstrip("#").lower() if re.fullmatch(r"#?[0-9a-fA-F]{6}", fill) else "transparent",
    }
    if rect.get("stroked", "t") == "f":
        shape["border"] = "none"
    else:
        stroke = rect.get("strokecolor", "#000000")
        color = stroke if re.fullmatch(r"#[0-9a-fA-F]{6}", stroke) else "#000000"
        shape["border"] = f"0.5pt solid {color}"
    return shape


def display(element):
    # AlternateContent carries duplicate fallback text. Use one representation.
    texts = [
        e.text or ""
        for e in element.iter(W + "t")
        if not any(p.tag == MC + "Fallback" for p in e.iterancestors())
    ]
    shapes = []
    for anchor in element.iter(WP + "anchor"):
        shape = _shape(anchor.find(".//" + A + "prstGeom"), anchor.find(WP + "extent"))
        if shape is None:
            continue
        try:
            shape["x"], shape["y"] = [
                int(_offset(anchor, axis)) / 12700 for axis in ("H", "V")
            ]
        except (ValueError, TypeError):
            continue
        if not all(-2000 <= v <= 2000 for v in (shape["x"], shape["y"])):
            continue
        shape["placement"] = "absolute"
        shapes.append(shape)
        if len(shapes) == SHAPES_LIMIT:
            return {"text": "".join(texts), "shapes": shapes}
    for inline in element.iter(WP + "inline"):
        shape = _shape(inline.find(".//" + A + "prstGeom"), inline.find(WP + "extent"))
        if shape is None:
            continue
        # Word renders inline drawings in the text flow at the anchor position.
        shape["placement"] = "inline"
        shapes.append(shape)
        if len(shapes) == SHAPES_LIMIT:
            return {"text": "".join(texts), "shapes": shapes}
    for rect in element.iter(V + "rect"):
        shape = _vml_shape(rect)
        if shape is None:
            continue
        shape["placement"] = "inline"
        shapes.append(shape)
        if len(shapes) == SHAPES_LIMIT:
            break
    return {"text": "".join(texts), "shapes": shapes}
