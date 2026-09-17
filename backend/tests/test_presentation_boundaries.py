"""Malformed and bounded source layouts stay inert and predictable."""

import pytest
from lxml import etree
from test_document_package import archive, doc

from app.documents.borders import property_borders
from app.documents.drawing_presentation import (
    SHAPES_LIMIT,
    WP,
    A,
    V,
    _drawing_recolor,
    display,
    recolor_targets,
)
from app.documents.package import DocxPackage, W
from app.documents.presentation import Layout


def drawing(children):
    return etree.fromstring(
        f'<w:r xmlns:w="{W[1:-1]}" xmlns:wp="{WP[1:-1]}" '
        f'xmlns:a="{A[1:-1]}" xmlns:v="{V[1:-1]}">{children}</w:r>'
    )


RECT = '<wp:extent cx="127000" cy="127000"/><a:prstGeom prst="rect"/>'


@pytest.mark.parametrize("kind", ["anchor", "inline", "vml"])
def test_display_and_recolor_share_the_shape_limit(kind):
    shape = (
        '<v:rect style="width:10pt;height:10pt" fillcolor="#abcdef"/>'
        if kind == "vml"
        else f'<wp:{kind}>{RECT}<a:solidFill><a:srgbClr val="ABCDEF"/>'
        f"</a:solidFill></wp:{kind}>"
    )
    root = drawing(shape * (SHAPES_LIMIT + 1))
    assert len(display(root)["shapes"]) == SHAPES_LIMIT
    targets = recolor_targets(root)
    assert len(targets) == SHAPES_LIMIT
    targets[-1]("123456")
    assert display(root)["shapes"][-1]["fill"] == "#123456"


@pytest.mark.parametrize("offset", ["invalid", "25400001"])
def test_bad_anchor_offsets_do_not_hide_following_valid_shapes(offset):
    root = drawing(
        f"<wp:anchor>{RECT}<wp:positionH><wp:posOffset>{offset}"
        "</wp:posOffset></wp:positionH></wp:anchor>"
        f"<wp:inline>{RECT}<a:ln/></wp:inline>"
    )
    assert display(root)["shapes"] == [
        {
            "width": 10,
            "height": 10,
            "fill": "#FFFFFF",
            "border": "0.5pt solid #000000",
            "placement": "inline",
        }
    ]


def test_optional_properties_and_missing_geometry_do_not_invent_styles():
    result = {"color": "#123456"}
    property_borders(None, result)
    assert result == {"color": "#123456"}
    assert _drawing_recolor(drawing("")) is None


def test_float_centering_skips_empty_paragraphs_and_handles_invalid_grids():
    def table(grid, props=""):
        return (
            '<w:tbl><w:tblPr><w:tblpPr w:tblpXSpec="center"/>'
            f"{props}</w:tblPr>{grid}<w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl>"
        )

    package = DocxPackage(
        archive(
            doc(
                table("<w:tblGrid/>", '<w:tblW w:w="1000"/>')
                + "<w:p/>"
                + table('<w:tblGrid><w:gridCol w:w="bad"/></w:tblGrid>')
                + '<w:sectPr><w:pgSz w:w="12000"/>'
                '<w:pgMar w:left="400" w:right="400"/></w:sectPr>'
            )
        )
    )
    layout = Layout(package).render()
    tables = [
        layout["nodes"][key]
        for key, el in package.elements.items()
        if el.tag == W + "tbl"
    ]
    assert tables[0]["width"] == "50pt"
    assert tables[0]["left"] == "255pt"
    assert "width" not in tables[1]
    assert tables[1]["margin-left"] == "0pt"
    cells = [
        layout["nodes"][key]
        for key, el in package.elements.items()
        if el.tag == W + "tc"
    ]
    assert all(cell["width"] == "auto" for cell in cells)
