"""Deterministic proposals from supported controls and explicit Unicode tokens."""

import hashlib
import json
import re
import unicodedata
from uuid import UUID

from app.fields.schema import FieldSnapshot
from app.fields.validation import paragraphs, validate_snapshot

TOKENS = re.compile(r"\{\{([^{}\r\n]{1,128})\}\}|\[\[([^\[\]\r\n]{1,128})\]\]")


def identity(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()[
        :32
    ]


def valid_key(value):
    return (
        value == value.strip()
        and any(char.isalnum() for char in value)
        and all(
            char.isalnum()
            or unicodedata.category(char).startswith("M")
            or char in "_-'’ʼ "
            for char in value
        )
    )


def metadata(model):
    stack = [model]
    result = {}
    while stack:
        node = stack.pop()
        if node["type"] == "field":
            result[node["attrs"]["id"]] = node["attrs"]
        elif node["type"] in {
            "doc",
            "section",
            "paragraph",
            "table",
            "tableRow",
            "tableCell",
        }:
            stack.extend(node.get("content", []))
    return result


def extract(model: dict, source_version_id: UUID) -> FieldSnapshot:
    known = paragraphs(model)  # Validate the traversal budget before more indexing.
    native = metadata(model)
    data: dict = {
        "source_version_id": source_version_id,
        "fields": [],
        "occurrences": [],
        "candidates": [],
        "decisions": [],
    }
    groups: dict[str, dict] = {}

    def add(occurrence, label, key, reason, context):
        if len(data["occurrences"]) >= 2000:
            raise ValueError("field_candidate_limit")
        candidate_id = "candidate:" + occurrence["id"]
        data["occurrences"].append(occurrence)
        data["candidates"].append(
            {
                "id": candidate_id,
                "occurrence_id": occurrence["id"],
                "label": label,
                "source_key": key,
                "reason": reason,
                "context": context[:1024],
            }
        )
        return candidate_id

    for (part, paragraph), (text, controls, blocked) in reversed(known.items()):
        base = {"part": part, "paragraph_id": paragraph}
        for control_id, value in controls.items():
            attrs = native[control_id]
            key = attrs["key"] if attrs["key"] != control_id else None
            label = attrs["label"] or key or ""
            candidate = add(
                {
                    "id": control_id,
                    "anchor": {"kind": "control", **base, "control_id": control_id},
                    "value": value,
                },
                label,
                key,
                "native_control",
                text,
            )
            group = identity(
                "field",
                "key" if key is not None else "control",
                key if key is not None else control_id,
            )
            if group not in groups:
                groups[group] = {"id": group, "label": label, "occurrence_ids": []}
            groups[group]["occurrence_ids"].append(control_id)
            # Preserve a field that already exists in the source, not inferred XML.
            data["decisions"].append(
                {"candidate_id": candidate, "status": "accepted", "field_id": group}
            )
        for match in TOKENS.finditer(text):
            key = match.group(1) or match.group(2)
            start, end = match.span()
            if not valid_key(key) or any(
                start < stop and end > begin or start <= begin == stop < end
                for begin, stop in blocked
            ):
                continue
            occurrence = {
                "id": identity("span", part, paragraph, start, end, match.group()),
                "anchor": {"kind": "span", **base, "start": start, "end": end},
                "value": match.group(),
            }
            add(
                occurrence,
                key,
                key,
                "placeholder",
                text[max(0, start - 160) : end + 160],
            )
    data["fields"] = list(groups.values())
    return validate_snapshot(data, source_version_id, model)
