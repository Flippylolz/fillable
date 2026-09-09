from copy import deepcopy

from test_document_package import archive, doc

from app.documents.export import DocxExport
from app.documents.package import DocxPackage, W
from app.documents.presentation import Layout, number


def test_source_layout_preserves_edit_model_and_original_package():
    styles = f'''<w:styles xmlns:w="{W[1:-1]}">
    <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman"/>
    <w:sz w:val="23"/></w:rPr></w:rPrDefault></w:docDefaults>
    <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:pPr><w:spacing w:after="0" w:line="240"/></w:pPr></w:style>
    <w:style w:styleId="Heading"><w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:color w:val="123ABC"/></w:rPr></w:style></w:styles>'''
    body = """<w:tbl><w:tblPr><w:tblBorders><w:top w:val="single"
      w:sz="8" w:color="000000"/></w:tblBorders>
      <w:tblCellMar><w:left w:w="80"/></w:tblCellMar></w:tblPr>
      <w:tblGrid><w:gridCol w:w="2800"/><w:gridCol w:w="3200"/></w:tblGrid>
      <w:tr><w:trPr><w:trHeight w:val="600"/></w:trPr><w:tc>
      <w:tcPr><w:tcW w:w="2800"/><w:vAlign w:val="center"/></w:tcPr>
      <w:p><w:pPr><w:pStyle w:val="Heading"/><w:ind w:left="200"/>
      <w:spacing w:before="120"/></w:pPr><w:r><w:rPr><w:sz w:val="28"/>
      </w:rPr><w:t>Синтетична форма</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
      <w:sectPr><w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:left="680" w:right="680" w:top="1020"/></w:sectPr>"""
    package = DocxPackage(archive(doc(body), {"word/styles.xml": styles}))
    before = deepcopy(package.model)
    layout = Layout(package).render()
    assert layout["section"]["font-size"] == "11.5pt"
    assert layout["section"]["width"] == "595.3pt"
    assert layout["section"]["padding-left"] == "34pt"
    by_tag = {
        el.tag.removeprefix(W): layout["nodes"][key]
        for key, el in package.elements.items()
    }
    assert by_tag["tbl"]["width"] == "300pt"
    assert by_tag["tr"]["height"] == "30pt"
    assert by_tag["tc"]["width"] == "140pt"
    assert by_tag["tc"]["padding-left"] == "4pt"
    assert by_tag["tc"]["border-top"] == "1pt solid #000000"
    assert by_tag["tc"]["vertical-align"] == "middle"
    assert by_tag["p"]["margin-top"] == "6pt"
    assert by_tag["p"]["margin-left"] == "10pt"
    assert by_tag["r"]["font-size"] == "14pt"
    assert by_tag["r"]["font-weight"] == "bold"
    assert "margin-left" not in by_tag["r"]
    assert package.model == before
    assert DocxExport(package).render(before, package.digest) == package.original


def test_untrusted_layout_values_cycles_and_extremes_are_bounded():
    styles = f'''<w:styles xmlns:w="{W[1:-1]}"><w:style w:styleId="cycle">
    <w:basedOn w:val="cycle"/><w:rPr><w:rFonts w:ascii="url(evil)"/>
    <w:color w:val="red;display:none"/><w:sz w:val="99999999"/>
    </w:rPr></w:style></w:styles>'''
    body = """<w:p><w:pPr><w:pStyle w:val="cycle"/><w:ind w:hanging="240"/>
    <w:spacing w:line="280" w:lineRule="exact"/><w:jc w:val="both"/>
    <w:pageBreakBefore/></w:pPr><w:r><w:rPr><w:b w:val="0"/>
    <w:i/><w:u w:val="none"/></w:rPr><w:t>ҐЄІЇ</w:t></w:r></w:p>"""
    package = DocxPackage(archive(doc(body), {"word/styles.xml": styles}))
    layout = Layout(package).render()
    paragraph, run = list(layout["nodes"].values())
    assert paragraph["text-indent"] == "-12pt"
    assert paragraph["line-height"] == "14pt"
    assert paragraph["text-align"] == "justify"
    assert paragraph["break-before"] == "page"
    assert run == {
        "font-weight": "normal",
        "font-style": "italic",
        "text-decoration": "none",
    }
    assert number("bad") is None
    assert number("-1") is None
    assert number(None) is None
    empty = Layout(DocxPackage(archive(doc("<w:p/>")))).render()
    assert empty["section"]["width"] == "595.3pt"


def test_rectangles_exclude_xml_coordinates_and_duplicate_fallback_text():
    from lxml import etree

    from app.documents.drawing_presentation import MC, WP, A, display

    xml = f'''<w:r xmlns:w="{W[1:-1]}" xmlns:a="{A[1:-1]}"
      xmlns:wp="{WP[1:-1]}" xmlns:mc="{MC[1:-1]}">
      <mc:AlternateContent><mc:Choice><w:drawing><wp:anchor>
      <wp:positionH><wp:posOffset>127000</wp:posOffset></wp:positionH>
      <wp:positionV><wp:posOffset>25400</wp:posOffset></wp:positionV>
      <wp:extent cx="127000" cy="127000"/><a:prstGeom prst="rect"/>
      <a:solidFill><a:srgbClr val="ABCDEF"/></a:solidFill>
      <w:t>Позначка</w:t></wp:anchor></w:drawing></mc:Choice>
      <mc:Fallback><w:t>Позначка</w:t></mc:Fallback></mc:AlternateContent></w:r>'''
    result = display(etree.fromstring(xml))
    assert result == {
        "text": "Позначка",
        "shapes": [
            {
                "x": 10,
                "y": 2,
                "width": 10,
                "height": 10,
                "fill": "#ABCDEF",
                "placement": "absolute",
            }
        ],
    }
    for old, new in [
        ('prst="rect"', 'prst="unknown"'),
        ('cx="127000"', 'cx="bad"'),
        ('cy="127000"', 'cy="-1"'),
    ]:
        assert display(etree.fromstring(xml.replace(old, new)))["shapes"] == []
    assert (
        display(etree.fromstring(xml.replace('val="ABCDEF"', 'val="evil"')))["shapes"][
            0
        ]["fill"]
        == "#FFFFFF"
    )


def test_floating_tables_use_page_offsets_and_start_end_borders():
    cell = """<w:tr><w:tc><w:tcPr><w:tcBorders><w:start w:val="single"
      w:sz="8"/><w:end w:val="nil"/></w:tcBorders></w:tcPr><w:p/></w:tc></w:tr>"""

    def table(position):
        return f'''<w:tbl><w:tblPr><w:tblpPr w:horzAnchor="page"
        w:tblpX="{position}" w:tblpY="200"/></w:tblPr>
        <w:tblGrid><w:gridCol w:w="800"/></w:tblGrid>{cell}</w:tbl>'''

    package = DocxPackage(
        archive(
            doc(
                table(2000)
                + table(3200)
                + """
      <w:sectPr><w:pgSz w:w="12000"/><w:pgMar w:left="400"/></w:sectPr>"""
            )
        )
    )
    result = Layout(package).render()
    tables = [
        result["nodes"][key]
        for key, el in package.elements.items()
        if el.tag == W + "tbl"
    ]
    assert tables[0]["display"] == "inline-table"
    assert tables[0]["margin-left"] == "80pt"
    assert tables[1]["margin-left"] == "20pt"
    cells = [
        result["nodes"][key]
        for key, el in package.elements.items()
        if el.tag == W + "tc"
    ]
    assert cells[0]["border-left"] == "1pt solid #000000"
    assert cells[0]["border-right"] == "none"


def test_internal_borders_styles_and_explicit_cell_overrides_survive_date_export():
    styles = f'''<w:styles xmlns:w="{W[1:-1]}">
      <w:style w:styleId="Boxes" w:type="table"><w:tblPr><w:tblBorders>
      <w:top w:val="double" w:sz="12"/><w:bottom w:val="single"/>
      <w:start w:val="single"/><w:end w:val="single"/>
      <w:insideV w:val="dotted" w:sz="8"/>
      <w:insideH w:val="dashed" w:sz="8"/>
      </w:tblBorders></w:tblPr></w:style></w:styles>'''
    cell = """<w:tc><w:tcPr>{}</w:tcPr><w:p><w:r><w:t>{}</w:t></w:r></w:p></w:tc>"""
    body = '<w:tbl><w:tblPr><w:tblStyle w:val="Boxes"/></w:tblPr>'
    body += "<w:tr>" + "".join(cell.format("", n) for n in "01012000") + "</w:tr>"
    body += (
        "<w:tr>"
        + cell.format('<w:tcBorders><w:top w:val="nil"/></w:tcBorders>', "x")
        + "</w:tr></w:tbl>"
    )
    package = DocxPackage(archive(doc(body), {"word/styles.xml": styles}))
    layout = Layout(package).render()
    cells = [
        layout["nodes"][key]
        for key, el in package.elements.items()
        if el.tag == W + "tc"
    ]
    assert cells[0]["border-top"] == "1.5pt double #000000"
    assert cells[0]["border-right"] == "1pt dotted #000000"
    assert cells[0]["border-bottom"] == "1pt dashed #000000"
    assert cells[-1]["border-top"] == "none"
    changed = deepcopy(package.model)
    row = changed["content"][0]["content"][0]["content"][0]
    for cell_node, digit in zip(row["content"], "29022024", strict=True):
        cell_node["content"][0]["content"][0]["text"] = digit
    output = DocxExport(package).render(changed, package.digest)
    reopened = DocxPackage(output)
    from lxml import etree

    original_borders = [
        etree.tostring(e) for e in package.roots["word/document.xml"].iter(W + "tcPr")
    ]
    assert original_borders == [
        etree.tostring(e) for e in reopened.roots["word/document.xml"].iter(W + "tcPr")
    ]
    assert Layout(reopened).render()["nodes"] == layout["nodes"]


def test_paragraph_and_run_outlines_are_bounded_and_preserved():
    body = """<w:p><w:pPr><w:pBdr><w:bottom w:val="double" w:sz="16" w:color="ABCDEF"/>
    <w:start w:val="single" w:sz="bad"/>
    <w:end w:val="single" w:sz="99999" w:color="evil"/>
    </w:pBdr></w:pPr><w:r><w:rPr><w:bdr w:val="single" w:sz="8"/></w:rPr>
    <w:t>0</w:t></w:r></w:p>"""
    package = DocxPackage(archive(doc(body)))
    paragraph, run = Layout(package).render()["nodes"].values()
    assert paragraph["border-bottom"] == "2pt double #ABCDEF"
    assert (
        paragraph["border-left"] == paragraph["border-right"] == "0.5pt solid #000000"
    )
    assert run["border"] == "1pt solid #000000"


def test_drawing_outline_weight_and_absent_stroke():
    from lxml import etree

    from app.documents.drawing_presentation import WP, A, display

    xml = f'''<w:r xmlns:w="{W[1:-1]}" xmlns:wp="{WP[1:-1]}" xmlns:a="{A[1:-1]}">
    <wp:anchor><wp:extent cx="127000" cy="127000"/><a:prstGeom prst="rect"/>
    <a:ln w="19050"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln>
    </wp:anchor></w:r>'''
    assert (
        display(etree.fromstring(xml))["shapes"][0]["border"] == "1.5pt solid #000000"
    )
    assert (
        display(etree.fromstring(xml.replace('w="19050"', 'w="bad"')))["shapes"][0][
            "border"
        ]
        == "0.5pt solid #000000"
    )
    assert (
        display(etree.fromstring(xml.replace('<a:ln w="19050">', "<a:ln><a:noFill/>")))[
            "shapes"
        ][0]["border"]
        == "none"
    )


def test_outline_stroke_does_not_become_the_rectangle_fill():
    from lxml import etree

    from app.documents.drawing_presentation import WP, A, display

    xml = f'''<w:r xmlns:w="{W[1:-1]}" xmlns:wp="{WP[1:-1]}" xmlns:a="{A[1:-1]}">
    <wp:anchor><wp:extent cx="127000" cy="127000"/><a:prstGeom prst="rect"/>
    <a:noFill/><a:ln w="19050"><a:solidFill><a:srgbClr val="000000"/>
    </a:solidFill></a:ln></wp:anchor></w:r>'''
    shape = display(etree.fromstring(xml))["shapes"][0]
    assert shape["fill"] == "transparent"
    assert shape["border"] == "1.5pt solid #000000"


def test_inline_rectangles_render_in_flow_without_absolute_offsets():
    from lxml import etree

    from app.documents.drawing_presentation import WP, A, display

    xml = f'''<w:r xmlns:w="{W[1:-1]}" xmlns:wp="{WP[1:-1]}" xmlns:a="{A[1:-1]}">
    <wp:inline><wp:extent cx="133350" cy="133350"/><a:prstGeom prst="rect"/>
    <a:noFill/><a:ln><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln>
    </wp:inline></w:r>'''
    result = display(etree.fromstring(xml))
    assert result["shapes"] == [
        {
            "width": 10.5,
            "height": 10.5,
            "fill": "transparent",
            "border": "0.5pt solid #000000",
            "placement": "inline",
        }
    ]
    assert display(
        etree.fromstring(xml.replace('prst="rect"', 'prst="unknown"'))
    )["shapes"] == []
    assert display(
        etree.fromstring(xml.replace('cy="133350"', 'cy="0"'))
    )["shapes"] == []


def test_vml_rectangles_become_inline_shapes_with_bounded_geometry():
    from lxml import etree

    from app.documents.drawing_presentation import V, display

    xml = f'''<w:r xmlns:w="{W[1:-1]}" xmlns:v="{V[1:-1]}">
    <w:pict><v:rect style="width:14pt;height:10.5pt" fillcolor="#ffffff" stroked="t"
      strokecolor="#123456"/></w:pict></w:r>'''
    result = display(etree.fromstring(xml))
    assert result["shapes"] == [
        {
            "width": 14.0,
            "height": 10.5,
            "fill": "#ffffff",
            "border": "0.5pt solid #123456",
            "placement": "inline",
        }
    ]
    for old, new in [
        ('style="width:14pt;height:10.5pt"', 'style="width:14pt"'),
        ('style="width:14pt;height:10.5pt"', 'style="width:14em;height:10.5pt"'),
        ('style="width:14pt;height:10.5pt"', 'style="width:4000pt;height:10.5pt"'),
        ('strokecolor="#123456"', 'strokecolor="evil"'),
    ]:
        shapes = display(etree.fromstring(xml.replace(old, new)))["shapes"]
        assert shapes == [] or shapes[0]["border"].endswith("#000000")


def test_vml_pixel_dimensions_convert_to_points():
    from lxml import etree

    from app.documents.drawing_presentation import V, display

    xml = f'''<w:r xmlns:w="{W[1:-1]}" xmlns:v="{V[1:-1]}">
    <w:pict><v:rect style="width:13.4px;height:13.4px" stroked="f"/></w:pict></w:r>'''
    shape = display(etree.fromstring(xml))["shapes"][0]
    assert (shape["width"], shape["height"]) == (10.05, 10.05)
    assert shape["border"] == "none"


def test_alternate_content_drawing_renders_once_without_vml_duplicate():
    from lxml import etree

    from app.documents.drawing_presentation import (
        MC,
        WP,
        A,
        V,
        display,
        recolor_targets,
    )

    xml = f'''<w:r xmlns:w="{W[1:-1]}" xmlns:a="{A[1:-1]}"
      xmlns:wp="{WP[1:-1]}" xmlns:mc="{MC[1:-1]}" xmlns:v="{V[1:-1]}">
      <mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wp:anchor>
      <wp:positionH relativeFrom="column">
      <wp:posOffset>127000</wp:posOffset></wp:positionH>
      <wp:positionV relativeFrom="paragraph"><wp:posOffset>25400</wp:posOffset>
      </wp:positionV>
      <wp:extent cx="127000" cy="127000"/><a:prstGeom prst="rect"/>
      <a:solidFill><a:srgbClr val="938953"/></a:solidFill>
      </wp:anchor></w:drawing></mc:Choice>
      <mc:Fallback><w:pict><v:rect style="width:10pt;height:10pt"
        fillcolor="#938953"/></w:pict></mc:Fallback></mc:AlternateContent></w:r>'''
    result = display(etree.fromstring(xml))
    assert len(result["shapes"]) == 1
    assert result["shapes"][0]["placement"] == "absolute"
    assert result["shapes"][0]["fill"] == "#938953"
    targets = recolor_targets(etree.fromstring(xml))
    assert len(targets) == 1 and targets[0] is not None
    # A rejected DrawingML choice falls back to its duplicate VML rectangle.
    broken = xml.replace('cx="127000"', 'cx="bad"')
    fallback = display(etree.fromstring(broken))["shapes"]
    assert [shape["placement"] for shape in fallback] == ["inline"]
    assert fallback[0]["fill"] == "#938953"
    # Standalone VML rectangles stay represented next to a valid drawing.
    standalone = xml.replace(
        "</w:r>",
        '<w:pict><v:rect style="width:5pt;height:5pt"/></w:pict></w:r>',
    )
    extra = display(etree.fromstring(standalone))["shapes"]
    assert [shape["width"] for shape in extra] == [10.0, 5.0]


def test_recolor_targets_are_absent_for_implicit_and_missing_fills():
    from lxml import etree

    from app.documents.drawing_presentation import WP, A, recolor_targets

    xml = f'''<w:r xmlns:w="{W[1:-1]}" xmlns:a="{A[1:-1]}" xmlns:wp="{WP[1:-1]}">
    <wp:anchor><wp:extent cx="127000" cy="127000"/><a:prstGeom prst="rect"/>
    <a:noFill/></wp:anchor>
    <wp:anchor><wp:extent cx="127000" cy="127000"/><a:prstGeom prst="rect"/>
    <a:solidFill><a:srgbClr val="ABCDEF"/></a:solidFill></wp:anchor>
    </w:r>'''
    tree = etree.fromstring(xml)
    targets = recolor_targets(tree)
    assert [target is not None for target in targets] == [False, True]
    targets[1]("ff0000")
    assert b'val="ff0000"' in etree.tostring(tree)
