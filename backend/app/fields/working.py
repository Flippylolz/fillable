"""Validate live ProseMirror anchors before pairing a document with field review.

The caller must separately validate the document against its immutable OOXML source.
This module does not write files, create revisions or authorize a save.
"""

from bisect import bisect_right
from copy import deepcopy
from uuid import UUID

from app.fields.validation import MODEL_NODES, MODEL_TEXT
from app.fields.working_schema import WorkingControl, WorkingReview

CONTAINERS = {"doc", "section", "paragraph", "table", "tableRow", "tableCell", "field"}
LEAVES = {"lockedBlock", "lockedInline", "checkbox"}
CHILDREN = {
    "doc": {"section"},
    "section": {"paragraph", "table", "lockedBlock"},
    "paragraph": {"text", "field", "lockedInline", "checkbox"},
    "table": {"tableRow"},
    "tableRow": {"tableCell"},
    "tableCell": {"paragraph", "table", "lockedBlock"},
    "field": {"text"},
}


def bounded(value):
    stack = [(value, 0)]
    count = size = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if count > MODEL_NODES * 20 or depth > 100:
            raise ValueError("working_model_limit")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
            stack.extend((key, depth + 1) for key in item)
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            size += len(item.encode("utf-8"))
            if size > MODEL_TEXT:
                raise ValueError("working_model_limit")
        elif item is not None and type(item) not in {int, bool}:
            raise ValueError("invalid_working_value")


def index(model):
    sizes: dict[int, int] = {}
    texts: dict[int, bytes] = {}
    stack = [(model, False)]
    examined = 0
    while stack:
        node, visited = stack.pop()
        if not isinstance(node, dict):
            raise ValueError("invalid_working_node")
        if set(node) - {"type", "attrs", "content", "marks", "text"}:
            raise ValueError("invalid_working_node")
        kind = node.get("type")
        children = node.get("content", [])
        if not isinstance(children, list):
            raise ValueError("invalid_working_node")
        if visited:
            sizes[id(node)] = sum(sizes[id(child)] for child in children) + (
                0 if kind == "doc" else 2
            )
            continue
        examined += 1
        if examined > MODEL_NODES:
            raise ValueError("working_model_limit")
        if kind == "text":
            if children or not isinstance(node.get("text"), str) or not node["text"]:
                raise ValueError("invalid_working_text")
            texts[id(node)] = node["text"].encode("utf-16-le")
            sizes[id(node)] = len(texts[id(node)]) // 2
        elif kind in LEAVES:
            if children:
                raise ValueError("invalid_working_leaf")
            if kind == "checkbox":
                attrs = node.get("attrs")
                if (
                    not isinstance(attrs, dict)
                    or set(attrs) != {"id", "checked"}
                    or not isinstance(attrs["id"], str)
                    or not attrs["id"]
                    or type(attrs["checked"]) is not bool
                ):
                    raise ValueError("invalid_working_leaf")
            sizes[id(node)] = 1
        elif kind in CONTAINERS:
            if any(
                not isinstance(child, dict) or child.get("type") not in CHILDREN[kind]
                for child in children
            ):
                raise ValueError("invalid_working_structure")
            stack.append((node, True))
            stack.extend((child, False) for child in reversed(children))
        else:
            raise ValueError("invalid_working_node")
    paragraphs, controls = [], {}
    positions = [(model, 0)]
    while positions:
        node, position = positions.pop()
        kind = node["type"]
        children = node.get("content", [])
        start = position + (0 if kind == "doc" else 1)
        if kind == "paragraph":
            segments = []
            cursor = start
            for child in children:
                size = sizes[id(child)]
                segments.append((cursor, cursor + size, texts.get(id(child))))
                cursor += size
            paragraphs.append(
                (start, cursor, segments, [segment[0] for segment in segments])
            )
        if kind == "field":
            attrs = node["attrs"]
            identity = attrs["id"]
            if (
                not isinstance(identity, str)
                or identity in controls
                or any(child["type"] != "text" for child in children)
            ):
                raise ValueError("invalid_working_control")
            controls[identity] = attrs
        pending = []
        for child in children:
            pending.append((child, start))
            start += sizes[id(child)]
        positions.extend(reversed(pending))
    return paragraphs, controls


def validate_span(location, paragraphs, starts):
    selected = bisect_right(starts, location.start) - 1
    if selected < 0:
        raise ValueError("invalid_working_span")
    start, end, segments, points = paragraphs[selected]
    if location.start > location.end or location.end > end:
        raise ValueError("invalid_working_span")
    if location.start == location.end:
        if start != end or location.text:
            raise ValueError("invalid_working_span")
        return
    if location.end - location.start != len(location.text.encode("utf-16-le")) // 2:
        raise ValueError("working_text_mismatch")
    value = []
    first = max(0, bisect_right(points, location.start) - 1)
    for position in range(first, len(segments)):
        begin, stop, text = segments[position]
        if begin >= location.end:
            break
        if location.start >= stop or location.end <= begin:
            continue
        if text is None:
            raise ValueError("protected_working_span")
        encoded = text
        value.append(
            encoded[
                max(0, location.start - begin) * 2 : (min(stop, location.end) - begin)
                * 2
            ].decode("utf-16-le")
        )
    if "".join(value) != location.text:
        raise ValueError("working_text_mismatch")


def _validate_working(model: dict, source_version: UUID, previous_origin: UUID | None):
    """Return a detached document/review pair; missing records stay explicit."""
    bounded(model)
    if model.get("type") != "doc" or set(model.get("attrs", {})) - {"review"}:
        raise ValueError("invalid_working_root")
    paragraphs, controls = index(model)
    data = model.get("attrs", {}).get("review")
    review = None if data is None else WorkingReview.model_validate(data)
    if review is not None:
        if review.source_version is not None and review.source_version not in {
            source_version,
            previous_origin,
        }:
            raise ValueError("stale_working_review")
        starts = [paragraph[0] for paragraph in paragraphs]
        seen = set()
        spans = sorted(
            (item.location.start, item.location.end)
            for item in review.items
            if not isinstance(item.location, WorkingControl) and not item.missing
        )
        if any(
            start < previous_end or (start == previous_start and end == previous_end)
            for (previous_start, previous_end), (start, end) in zip(spans, spans[1:])
        ):
            raise ValueError("overlapping_working_spans")
        for item in review.items:
            location = item.location
            if isinstance(location, WorkingControl):
                if location.id in seen:
                    raise ValueError("duplicate_working_control")
                seen.add(location.id)
                actual = controls.get(location.id)
                if item.missing != (actual is None):
                    raise ValueError("working_presence_mismatch")
                if actual is not None and (
                    item.label != actual["label"] or item.key != actual["key"]
                ):
                    raise ValueError("working_property_mismatch")
            elif not item.missing:
                validate_span(location, paragraphs, starts)
        if not set(controls) <= seen:
            raise ValueError("untracked_working_control")
    document = deepcopy(model)
    document.pop("attrs", None)
    return document, None if review is None else review.model_dump(
        mode="json", by_alias=True
    )


def validate_working(
    model: dict, source_version: UUID, previous_origin: UUID | None = None
):
    try:
        return _validate_working(model, source_version, previous_origin)
    except (KeyError, TypeError, AttributeError, UnicodeError, RecursionError):
        raise ValueError("invalid_working_model") from None
