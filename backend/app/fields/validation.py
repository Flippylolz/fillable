"""Check proposals against known model anchors, never XPath or global text search."""

from uuid import UUID

from app.fields.schema import ControlAnchor, FieldSnapshot

MODEL_NODES = 100000
MODEL_TEXT = 50 * 1024 * 1024


def paragraphs(model):
    result = {}
    stack = [(None, model)]
    examined = 0
    characters = 0
    while stack:
        part, node = stack.pop()
        examined += 1
        if examined > MODEL_NODES:
            raise ValueError("field_model_limit")
        kind = node.get("type")
        if kind == "section":
            part = node["attrs"]["part"]
        if kind == "paragraph":
            identity = (part, node["attrs"]["id"])
            if not part or identity in result:
                raise ValueError("invalid_paragraph_identity")
            text = ""
            controls = {}
            blocked = []
            for child in node.get("content", []):
                examined += 1 + len(child.get("content", []))
                if examined > MODEL_NODES:
                    raise ValueError("field_model_limit")
                start = len(text)
                if child["type"] == "text":
                    text += child["text"]
                elif child["type"] == "field":
                    value = "".join(item["text"] for item in child.get("content", []))
                    control = child["attrs"]["id"]
                    if control in controls:
                        raise ValueError("duplicate_control_identity")
                    controls[control] = value
                    text += value
                    blocked.append((start, len(text)))
                else:
                    text += "\ufffc"
                    blocked.append((start, len(text)))
                characters += len(text) - start
                if characters > MODEL_TEXT:
                    raise ValueError("field_model_limit")
            result[identity] = (text, controls, blocked)
        elif kind in {"doc", "section", "table", "tableRow", "tableCell"}:
            stack.extend((part, child) for child in node.get("content", []))
    return result


def validate_snapshot(
    data: dict, source_version_id: UUID, model: dict
) -> FieldSnapshot:
    snapshot = FieldSnapshot.model_validate(data)
    if snapshot.source_version_id != source_version_id:
        raise ValueError("stale_field_snapshot")
    known = paragraphs(model)
    seen = set()
    spans: dict[tuple, list[tuple[int, int]]] = {}
    for occurrence in snapshot.occurrences:
        anchor = occurrence.anchor
        paragraph = known.get((anchor.part, anchor.paragraph_id))
        if paragraph is None:
            raise ValueError("unknown_field_anchor")
        text, controls, blocked = paragraph
        key: tuple
        if isinstance(anchor, ControlAnchor):
            value = controls.get(anchor.control_id)
            key = (anchor.part, anchor.paragraph_id, anchor.control_id)
            if value is None:
                raise ValueError("unknown_field_control")
        else:
            start, end = anchor.start, anchor.end
            if (
                end > len(text)
                or (start == end and (text or blocked))
                or any(
                    start < stop and end > begin or start <= begin == stop < end
                    for begin, stop in blocked
                )
            ):
                raise ValueError("invalid_field_range")
            value = text[start:end]
            key = (anchor.part, anchor.paragraph_id, start, end)
        if key in seen:
            raise ValueError("duplicate_field_anchor")
        seen.add(key)
        if not isinstance(anchor, ControlAnchor):
            intervals = spans.setdefault((anchor.part, anchor.paragraph_id), [])
            if any(
                anchor.start < end and anchor.end > start for start, end in intervals
            ):
                raise ValueError("overlapping_field_anchors")
            intervals.append((anchor.start, anchor.end))
        if occurrence.value != value:
            raise ValueError("field_text_mismatch")
    return snapshot
