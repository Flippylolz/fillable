"""Native checkbox controls: bounded import, toggled export, and model validation."""

import copy
import io
from uuid import uuid4
from zipfile import ZipFile

import pytest

from app.documents.drawing_presentation import MC, WP, A, V
from app.documents.export import DocxExport
from app.documents.package import DocxPackage, W
from app.documents.presentation import Layout
from app.fields.working import validate_working

W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

CHECKBOX = """<w:sdt>
  <w:sdtPr><w:id w:val="101"/>
    <w14:checkbox>
      <w14:checked w14:val="{checked}"/>
      <w14:checkedState w14:val="2612" w14:font="MS Gothic"/>
      <w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/>
    </w14:checkbox>
  </w:sdtPr>
  <w:sdtContent><w:r>{glyph}</w:r></w:sdtContent>
</w:sdt>"""


def archive(body):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as output:
        output.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W[1:-1]}" xmlns:w14="{W14}">'
            f"<w:body>{body}</w:body></w:document>",
        )
    return buffer.getvalue()


def walk(node):
    yield node
    for child in node.get("content", []):
        yield from walk(child)


def checkboxes(model):
    return [node for node in walk(model) if node["type"] == "checkbox"]


def test_native_checkbox_imports_with_state_instead_of_locking():
    package = DocxPackage(
        archive(f"<w:p>{CHECKBOX.format(checked='1', glyph='<w:t>☒</w:t>')}</w:p>")
    )
    boxes = checkboxes(package.model)
    assert len(boxes) == 1
    assert boxes[0]["attrs"]["checked"] is True
    assert boxes[0]["attrs"]["id"] in package.elements
    assert package.unsupported == []
    package = DocxPackage(
        archive(f"<w:p>{CHECKBOX.format(checked='0', glyph='<w:t>☐</w:t>')}</w:p>")
    )
    assert checkboxes(package.model)[0]["attrs"]["checked"] is False
    package = DocxPackage(
        archive(f"<w:p>{CHECKBOX.format(checked='true', glyph='<w:t>☒</w:t>')}</w:p>")
    )
    assert checkboxes(package.model)[0]["attrs"]["checked"] is True


def test_checkbox_with_unsupported_interiors_stays_locked():
    package = DocxPackage(
        archive(
            "<w:p>"
            + CHECKBOX.format(checked="0", glyph='<w:footnoteReference w:id="4"/>')
            + "</w:p>"
        )
    )
    assert checkboxes(package.model) == []
    kinds = {node["type"] for node in walk(package.model)}
    assert "lockedInline" in kinds
    assert len(package.unsupported) == 1


def test_unchanged_checkbox_export_is_byte_identical():
    data = archive(f"<w:p>{CHECKBOX.format(checked='0', glyph='<w:t>☐</w:t>')}</w:p>")
    package = DocxPackage(data)
    assert DocxExport(package).render(package.model, package.digest) == data


def test_toggled_checkbox_export_updates_state_and_glyph():
    data = archive(f"<w:p>{CHECKBOX.format(checked='0', glyph='<w:t>☐</w:t>')}</w:p>")
    package = DocxPackage(data)
    model = copy.deepcopy(package.model)
    boxes = checkboxes(model)
    boxes[0]["attrs"]["checked"] = True
    changed = DocxExport(package).render(model, package.digest)
    with ZipFile(io.BytesIO(changed)) as saved:
        xml = saved.read("word/document.xml").decode("utf-8")
    assert '<w14:checked w14:val="1"/>' in xml
    assert "☒" in xml and "☐" not in xml
    reopened = DocxPackage(changed)
    assert checkboxes(reopened.model)[0]["attrs"]["checked"] is True
    # Toggling back re-parses with the original state.
    reverted = copy.deepcopy(reopened.model)
    checkboxes(reverted)[0]["attrs"]["checked"] = False
    again = DocxExport(reopened).render(reverted, reopened.digest)
    assert checkboxes(DocxPackage(again).model)[0]["attrs"]["checked"] is False


def test_toggled_checkbox_without_state_glyphs_keeps_text():
    minimal = CHECKBOX.split("<w14:checkedState")[0] + "</w14:checkbox></w:sdtPr>"
    body = (
        f"<w:p>{minimal.format(checked='0')}"
        "<w:sdtContent><w:r><w:t>x</w:t></w:r></w:sdtContent></w:sdt></w:p>"
    )
    data = archive(body)
    package = DocxPackage(data)
    model = copy.deepcopy(package.model)
    checkboxes(model)[0]["attrs"]["checked"] = True
    changed = DocxExport(package).render(model, package.digest)
    with ZipFile(io.BytesIO(changed)) as saved:
        xml = saved.read("word/document.xml").decode("utf-8")
    assert '<w14:checked w14:val="1"/>' in xml
    assert "x" in xml


def test_checkbox_export_rejects_malformed_nodes():
    from app.documents.package import InvalidDocument

    data = archive(f"<w:p>{CHECKBOX.format(checked='0', glyph='<w:t>☐</w:t>')}</w:p>")
    package = DocxPackage(data)
    exporter = DocxExport(package)
    model = copy.deepcopy(package.model)
    boxes = checkboxes(model)[0]
    boxes["attrs"]["checked"] = True
    for mutation in [
        lambda: boxes["attrs"].update(extra=1),
        lambda: boxes["attrs"].update(checked="yes"),
        lambda: boxes["attrs"].update(id="word/document.xml:999"),
        lambda: boxes["attrs"].pop("checked"),
    ]:
        mutation()
        with pytest.raises(InvalidDocument, match="invalid_anchor"):
            exporter.render(model, package.digest)


def shape_run(color):
    return f'''<w:r xmlns:mc="{MC[1:-1]}" xmlns:wp="{WP[1:-1]}" xmlns:a="{A[1:-1]}"
  xmlns:v="{V[1:-1]}"><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing>
  <wp:anchor>
  <wp:positionH relativeFrom="column"><wp:posOffset>127000</wp:posOffset></wp:positionH>
  <wp:positionV relativeFrom="paragraph"><wp:posOffset>25400</wp:posOffset>
  </wp:positionV>
  <wp:extent cx="127000" cy="127000"/><a:prstGeom prst="rect"/>
  <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>
  </wp:anchor></w:drawing></mc:Choice>
  <mc:Fallback><w:pict><v:rect style="width:10pt;height:10pt"
  fillcolor="#{color}"/></w:pict></mc:Fallback></mc:AlternateContent></w:r>'''


def shape_document(fill="938953"):
    return archive(
        f"<w:p>{shape_run(fill)}<w:r><w:t>ч</w:t></w:r></w:p>"
    )


def locked_runs(model):
    return [node for node in walk(model) if node["type"] == "lockedInline"]


def test_drawn_shape_renders_once_and_stays_byte_identical_unchanged():
    data = shape_document()
    package = DocxPackage(data)
    runs = locked_runs(package.model)
    assert len(runs) == 1
    layout = Layout(package).render()
    shapes = layout["locked"][runs[0]["attrs"]["id"]]["shapes"]
    assert len(shapes) == 1
    assert shapes[0]["placement"] == "absolute"
    assert shapes[0]["fill"] == "#938953"
    assert DocxExport(package).render(package.model, package.digest) == data
    # The editing schema serializes an empty override map; it stays byte-identical.
    model = copy.deepcopy(package.model)
    locked_runs(model)[0]["attrs"]["shapes"] = {}
    assert DocxExport(package).render(model, package.digest) == data


def test_toggled_shape_fill_export_updates_choice_and_fallback():
    data = shape_document()
    package = DocxPackage(data)
    model = copy.deepcopy(package.model)
    locked_runs(model)[0]["attrs"]["shapes"] = {"0": "#FF0000"}
    changed = DocxExport(package).render(model, package.digest)
    with ZipFile(io.BytesIO(changed)) as saved:
        xml = saved.read("word/document.xml").decode("utf-8")
    assert 'val="ff0000"' in xml
    assert 'fillcolor="#ff0000"' in xml
    reopened = DocxPackage(changed)
    runs = locked_runs(reopened.model)
    shapes = Layout(reopened).render()["locked"][runs[0]["attrs"]["id"]]["shapes"]
    assert shapes[0]["fill"] == "#ff0000"
    # Reverting to the authored color presents the source appearance again.
    reverted = copy.deepcopy(reopened.model)
    locked_runs(reverted)[0]["attrs"]["shapes"] = {"0": "#938953"}
    again = DocxPackage(DocxExport(reopened).render(reverted, reopened.digest))
    runs = locked_runs(again.model)
    shapes = Layout(again).render()["locked"][runs[0]["attrs"]["id"]]["shapes"]
    assert shapes[0]["fill"] == "#938953"


def test_shape_fill_export_rejects_malformed_overrides():
    from app.documents.package import InvalidDocument

    package = DocxPackage(shape_document())
    for overrides in [
        {"0": "red"},
        {"7": "#ff0000"},
        {"0": 5},
        {"-1": "#ff0000"},
        "x",
        {"0": "#ff0000", **{str(i): "#ff0000" for i in range(1, 40)}},
    ]:
        model = copy.deepcopy(package.model)
        locked_runs(model)[0]["attrs"]["shapes"] = overrides
        with pytest.raises(InvalidDocument, match="invalid_anchor"):
            DocxExport(package).render(model, package.digest)
    # A run without an explicit fill offers no recolor target at all.
    stripped = shape_run("938953").replace(
        '<a:solidFill><a:srgbClr val="938953"/></a:solidFill>', ""
    )
    empty = DocxPackage(
        archive(f"<w:p>{stripped}<w:r><w:t>ч</w:t></w:r></w:p>")
    )
    model = copy.deepcopy(empty.model)
    locked_runs(model)[0]["attrs"]["shapes"] = {"0": "#ff0000"}
    with pytest.raises(InvalidDocument, match="invalid_anchor"):
        DocxExport(empty).render(model, empty.digest)
    # Identity stays immutable: label changes stay rejected even with overrides.
    model = copy.deepcopy(package.model)
    locked_runs(model)[0]["attrs"].update(label="x", shapes={"0": "#ff0000"})
    with pytest.raises(InvalidDocument, match="invalid_anchor"):
        DocxExport(package).render(model, package.digest)


def test_working_model_accepts_bounded_shape_overrides():
    source = uuid4()
    model = {
        "type": "doc",
        "attrs": {},
        "content": [
            {
                "type": "section",
                "attrs": {"part": "word/document.xml"},
                "content": [
                    {
                        "type": "paragraph",
                        "attrs": {
                            "id": "word/document.xml:1",
                            "align": "left",
                            "numbered": False,
                        },
                        "content": [
                            {
                                "type": "lockedInline",
                                "attrs": {
                                    "id": "word/document.xml:2",
                                    "label": "",
                                    "shapes": {"0": "#938953"},
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }
    document, _ = validate_working(model, source)
    kinds = [node["type"] for node in walk(document)]
    assert "lockedInline" in kinds


def test_working_model_accepts_checkbox_only_inside_paragraphs():
    source = uuid4()

    def text(value, identity):
        return {
            "type": "text",
            "text": value,
            "marks": [
                {
                    "type": "source",
                    "attrs": {
                        "id": identity,
                        "bold": False,
                        "italic": False,
                        "underline": False,
                    },
                }
            ],
        }

    def model(paragraph_children):
        paragraph = {
            "type": "paragraph",
            "attrs": {"id": "word/document.xml:1", "align": "left", "numbered": False},
            "content": [
                text("a", "word/document.xml:2"),
                *paragraph_children,
                text("b", "word/document.xml:3"),
            ],
        }
        section = {
            "type": "section",
            "attrs": {"part": "word/document.xml"},
            "content": [paragraph],
        }
        return {"type": "doc", "attrs": {}, "content": [section]}

    good = model(
        [{"type": "checkbox", "attrs": {"id": "word/document.xml:7", "checked": True}}]
    )
    document, _ = validate_working(good, source)
    kinds = [node["type"] for node in walk(document)]
    assert "checkbox" in kinds

    for bad in [
        lambda: {
            **model([]),
            "content": [
                {
                    "type": "section",
                    "attrs": {"part": "word/document.xml"},
                    "content": [
                        {
                            "type": "checkbox",
                            "attrs": {"id": "word/document.xml:7", "checked": False},
                        }
                    ],
                }
            ],
        },
        lambda: model([{"type": "checkbox", "attrs": {"id": "", "checked": False}}]),
        lambda: model(
            [{"type": "checkbox", "attrs": {"id": "x:7", "checked": "no"}}]
        ),
        lambda: model([{"type": "checkbox", "attrs": {"id": "x:7"}}]),
    ]:
        with pytest.raises(ValueError):
            validate_working(bad(), source)


def test_checkbox_interior_is_protected_for_field_spans():
    from app.fields.validation import paragraphs

    model = {
        "type": "doc",
        "content": [
            {
                "type": "section",
                "attrs": {"part": "word/document.xml"},
                "content": [
                    {
                        "type": "paragraph",
                        "attrs": {"id": "word/document.xml:1"},
                        "content": [
                            {"type": "text", "text": "a"},
                            {
                            "type": "checkbox",
                            "attrs": {"id": "word/document.xml:2", "checked": False},
                        },
                            {"type": "text", "text": "b"},
                        ],
                    }
                ],
            }
        ],
    }
    result = paragraphs(model)
    text, _controls, blocked = result[("word/document.xml", "word/document.xml:1")]
    assert text == "a\ufffcb"
    assert blocked == [(1, 2)]
