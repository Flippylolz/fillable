"""Offline synthetic-corpus scoring; never used by production discovery."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from app.documents.package import DocxPackage, W
from app.fields.blanks import discover
from app.fields.schema import FieldSnapshot
from app.fields.validation import validate_snapshot

REASONS = {
    "native_text_control": "native_control",
    "placeholder": "placeholder",
    "underlined_spaces": "blank_line",
    "underscore_blank": "blank_line",
    "segmented_date_blank": "blank_line",
    "dotted_blank": "blank_line",
    "empty_cell": "blank_cell",
}


def resolve(package, locator):
    found = package.roots[locator["part"]].xpath(
        locator["xpath"], namespaces={"w": W[1:-1]}
    )
    if len(found) != 1:
        raise ValueError("ambiguous_fixture_locator")
    return found[0]


def projection(package, paragraph, node):
    """Map each raw w:t code point to the model, excluding locked interiors."""
    bases, raw = {}, 0
    for element in paragraph.iter(W + "t"):
        bases[element] = raw
        raw += len(element.text or "")
    mapped, offset = {}, 0
    stack = list(reversed(node.get("content", [])))
    while stack:
        child = stack.pop()
        if child["type"] == "field":
            stack.extend(reversed(child.get("content", [])))
        elif child["type"] == "text":
            source = next(mark for mark in child["marks"] if mark["type"] == "source")
            run = package.elements[source["attrs"]["id"]]
            for element in run:
                if element.tag == W + "t":
                    for index in range(len(element.text or "")):
                        mapped[bases[element] + index] = offset
                        offset += 1
                elif element.tag in {W + "tab", W + "br"}:
                    offset += 1
        else:
            offset += 1
    return mapped, offset


def reference_key(package, item, nodes):
    paragraph = resolve(package, item["paragraph"])
    raw = "".join(element.text or "" for element in paragraph.iter(W + "t"))
    start, end = item["start"], item["end"]
    if not 0 <= start <= end <= len(raw) or raw[start:end] != item["initial_text"]:
        raise ValueError("fixture_text_mismatch")
    part = item["paragraph"]["part"]
    paragraph_id = next(key for key in nodes if package.elements[key] is paragraph)
    reason = REASONS[item["kind"]]
    if reason == "native_control":
        control = resolve(package, item["control"])
        return reason, part, paragraph_id, control
    mapped, length = projection(package, paragraph, nodes[paragraph_id])
    if start == end:
        if length:
            raise ValueError("nonempty_fixture_location")
        return reason, part, paragraph_id, 0, 0
    if any(index not in mapped for index in range(start, end)):
        raise ValueError("protected_fixture_location")
    return reason, part, paragraph_id, mapped[start], mapped[end - 1] + 1


def ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def evaluate(package: DocxPackage, expected: dict, snapshot: FieldSnapshot) -> dict:
    if package.digest != expected["sha256"]:
        raise ValueError("fixture_digest_mismatch")
    snapshot = validate_snapshot(
        snapshot.model_dump(), snapshot.source_version_id, package.model
    )
    nodes = {}
    stack = [package.model]
    while stack:
        node = stack.pop()
        if node["type"] == "paragraph":
            nodes[node["attrs"]["id"]] = node
        else:
            stack.extend(node.get("content", []))
    gold: dict[tuple, str] = {}
    for item in expected["occurrences"]:
        key = reference_key(package, item, nodes)
        if key in gold or item["id"] in gold.values():
            raise ValueError("duplicate_fixture_location")
        gold[key] = item["id"]
    occurrences = {item.id: item for item in snapshot.occurrences}
    accepted = {
        item.candidate_id for item in snapshot.decisions if item.status == "accepted"
    }
    actual, locations = {}, {}
    for candidate in snapshot.candidates:
        anchor = occurrences[candidate.occurrence_id].anchor
        location = (candidate.reason, anchor.part, anchor.paragraph_id)
        if anchor.kind == "control":
            key = (*location, package.elements[anchor.control_id])
        else:
            key = (*location, anchor.start, anchor.end)
        actual[key] = candidate.id
        locations[candidate.id] = package.elements[anchor.paragraph_id]
    metrics = {}
    for reason in sorted(set(REASONS.values()) | {key[0] for key in actual}):
        wanted = {key for key in gold if key[0] == reason}
        found = {key for key in actual if key[0] == reason}
        matched = len(wanted & found)
        metrics[reason] = {
            "expected": len(wanted),
            "predicted": len(found),
            "true_positives": matched,
            "false_positives": len(found - wanted),
            "false_negatives": len(wanted - found),
            "precision": ratio(matched, len(found)),
            "recall": ratio(matched, len(wanted)),
            "missed_ids": sorted(gold[key] for key in wanted - found),
            "extra_candidate_ids": sorted(actual[key] for key in found - wanted),
        }
    negatives = []
    for item in expected["negative_cases"]:
        paragraph = resolve(package, item["paragraph"])
        if (
            "".join(el.text or "" for el in paragraph.iter(W + "t"))
            != item["initial_text"]
        ):
            raise ValueError("fixture_text_mismatch")
        candidates = {key for key, element in locations.items() if element is paragraph}
        negatives.append(
            {
                "id": item["id"],
                "review_proposals_allowed": item["expected_action"]
                == "do_not_auto_accept",
                "candidate_ids": sorted(candidates),
                "accepted_candidate_ids": sorted(candidates & accepted),
            }
        )
    extras = {actual[key] for key in actual.keys() - gold.keys()}
    return {
        "schema_version": 1,
        "fixture_id": expected["fixture_id"],
        "sha256": package.digest,
        "detectors": metrics,
        "negative_cases": negatives,
        "incorrect_confirmed_candidate_ids": sorted(extras & accepted),
        "inferred_confirmed_candidate_ids": sorted(
            item.id
            for item in snapshot.candidates
            if item.reason != "native_control" and item.id in accepted
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("expected", type=Path)
    args = parser.parse_args()
    package = DocxPackage(args.document.read_bytes())
    expected = json.loads(args.expected.read_text())
    print(
        json.dumps(
            evaluate(package, expected, discover(package.model, UUID(int=0))), indent=2
        )
    )


if __name__ == "__main__":
    main()
