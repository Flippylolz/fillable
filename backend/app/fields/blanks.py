"""Conservative blank proposals from supported text and nearby form labels."""

import itertools
import re
import unicodedata
from uuid import UUID

from app.fields.discovery import extract, identity
from app.fields.kinds import classify
from app.fields.schema import FieldSnapshot
from app.fields.validation import paragraphs, validate_snapshot

BLANKS = re.compile(r"_{2,}(?:[ \t]*[/.-][ \t]*_{2,}){1,2}|_{3,}|\.{5,}")
SPACES = re.compile(r"[ \u00a0]+")
BLOCKS = {"doc", "section", "table", "tableRow", "tableCell"}


def label(value):
    value = value.strip().rstrip(":：—-").strip()
    return (
        value
        if 0 < len(value) <= 160
        and any(char.isalpha() for char in value)
        and not any(char in value for char in "{}[]\ufffc\n")
        else None
    )


def context(model, known):
    nodes, labels, empty = {}, {}, set()
    stack = [(None, model)]
    while stack:
        part, node = stack.pop()
        kind = node["type"]
        if kind == "section":
            part = node["attrs"]["part"]
        if kind == "paragraph":
            nodes[(part, node["attrs"]["id"])] = node
        elif kind in BLOCKS:
            stack.extend((part, child) for child in node.get("content", []))
        if kind != "table":
            continue
        for row in node["content"]:
            cells = row["content"]
            for index in range(1, len(cells)):
                previous = [
                    child
                    for child in cells[index - 1]["content"]
                    if child["type"] == "paragraph"
                ]
                nearby = label(
                    " ".join(
                        known[(part, child["attrs"]["id"])][0] for child in previous
                    )
                )
                if nearby is None:
                    continue
                content = cells[index]["content"]
                for child in content:
                    if child["type"] != "paragraph":
                        continue
                    key = (part, child["attrs"]["id"])
                    labels[key] = nearby
                    if (
                        len(cells) == 2
                        and len(content) == 1
                        and all(cell["attrs"].get("colspan", 1) == 1 for cell in cells)
                        and known[key] == ("", {}, [])
                    ):
                        empty.add(key)
    return nodes, labels, empty


def underlined(node):
    offset = 0
    pending = None
    for child in node.get("content", []):
        if child["type"] == "text":
            value = child["text"]
            enabled = any(
                mark["type"] == "source" and mark["attrs"].get("underline")
                for mark in child.get("marks", [])
            )
            matches = SPACES.finditer(value) if enabled else ()
            for match in matches:
                start, end = offset + match.start(), offset + match.end()
                if pending is not None and pending[1] == start:
                    pending = (pending[0], end)
                else:
                    if pending is not None and pending[1] - pending[0] >= 3:
                        yield pending
                    pending = (start, end)
            offset += len(value)
            keep = enabled and pending is not None and pending[1] == offset
        else:
            offset += (
                sum(len(item["text"]) for item in child.get("content", []))
                if child["type"] == "field"
                else 1
            )
            keep = False
        if not keep:
            if pending is not None and pending[1] - pending[0] >= 3:
                yield pending
            pending = None
    if pending is not None and pending[1] - pending[0] >= 3:
        yield pending


def word(char):
    return char.isalnum() or char == "_" or unicodedata.category(char).startswith("M")


def nearby_label(text, start, end, table_label):
    prefix = text[:start].rsplit("\n", 1)[-1].strip()
    if prefix.endswith((":", "：")):
        return label(prefix)
    if not prefix:
        return table_label
    if (
        len(prefix) <= 80
        and not text[end:].strip()
        and not text[start:end].startswith(".")
    ):
        return label(prefix)
    return None


def discover(model: dict, source_version_id: UUID) -> FieldSnapshot:
    data = extract(model, source_version_id).model_dump(mode="json")
    known = paragraphs(model)
    nodes, labels, empty = context(model, known)
    occupied: dict[tuple, list[tuple[int, int]]] = {}
    for occurrence in data["occurrences"]:
        anchor = occurrence["anchor"]
        if anchor["kind"] == "span":
            occupied.setdefault((anchor["part"], anchor["paragraph_id"]), []).append(
                (anchor["start"], anchor["end"])
            )
    for location, (text, _controls, blocked) in reversed(known.items()):
        intervals = occupied.setdefault(location, [])
        ranges = itertools.chain(
            ((match.start(), match.end()) for match in BLANKS.finditer(text)),
            underlined(nodes[location]),
            [(0, 0)] if location in empty else [],
        )
        for start, end in ranges:
            if any(
                start < stop and end > begin or start <= begin == stop < end
                for begin, stop in blocked + intervals
            ):
                continue
            if start and word(text[start - 1]) or end < len(text) and word(text[end]):
                continue
            nearby = nearby_label(text, start, end, labels.get(location))
            if nearby is None:
                continue
            if len(data["occurrences"]) >= 2000:
                raise ValueError("field_candidate_limit")
            part, paragraph = location
            key = identity("blank", part, paragraph, start, end, text[start:end])
            data["occurrences"].append(
                {
                    "id": key,
                    "anchor": {
                        "kind": "span",
                        "part": part,
                        "paragraph_id": paragraph,
                        "start": start,
                        "end": end,
                    },
                    "value": text[start:end],
                }
            )
            data["candidates"].append(
                {
                    "id": "candidate:" + key,
                    "occurrence_id": key,
                    "label": nearby,
                    "reason": "blank_cell" if start == end else "blank_line",
                    "source_key": None,
                    "context": (
                        nearby + "\n" + text[max(0, start - 160) : end + 160]
                    )[:1024],
                    "type": classify(text[start:end], nearby),
                }
            )
            intervals.append((start, end))
    return validate_snapshot(data, source_version_id, model)
