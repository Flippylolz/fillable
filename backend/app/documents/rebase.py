"""Match a saved working tree to its own exported package, never by text search."""

import hashlib
from copy import deepcopy
from dataclasses import dataclass

from app.documents.package import W
from app.fields.validation import validate_snapshot
from app.fields.working import bounded, index, validate_working


def children(node):
    """Run boundaries may change during export; formatting and order may not."""
    result = []
    fragments: list[str] = []
    previous = None

    def flush():
        if fragments:
            result.append(
                {"type": "text", "text": "".join(fragments), "style": previous}
            )
            fragments.clear()

    for child in node.get("content", []):
        if child["type"] != "text":
            flush()
            result.append(child)
            previous = None
            continue
        marks = child.get("marks", [])
        attrs = {}
        if marks:
            if len(marks) != 1 or marks[0].get("type") != "source":
                raise ValueError("copy_format_mismatch")
            attrs = marks[0]["attrs"]
            if set(attrs) != {"id", "bold", "italic", "underline"}:
                raise ValueError("copy_format_mismatch")
        style = tuple(attrs.get(key, False) for key in ("bold", "italic", "underline"))
        if any(type(value) is not bool for value in style):
            raise ValueError("copy_format_mismatch")
        if style != previous:
            flush()
            previous = style
        fragments.append(child["text"])
    flush()
    return result


def correspondence(document, package):
    """Return one-to-one structural identities after semantic correspondence."""
    bounded(document)
    index(document)
    identities: dict[str, str] = {}
    targets = set()
    pending = [(document, package.model)]
    while pending:
        source, target = pending.pop()
        kind = source["type"]
        if kind != target["type"]:
            raise ValueError("copy_structure_mismatch")
        if kind == "text":
            if source != target:
                raise ValueError("copy_text_mismatch")
            continue
        left, right = dict(source.get("attrs", {})), dict(target.get("attrs", {}))
        old, new = left.pop("id", None), right.pop("id", None)
        # Shape fill overrides are locked-run presentation state that only the
        # working model carries; the canonical package model never has them.
        left.pop("shapes", None)
        right.pop("shapes", None)
        if old is not None or new is not None:
            if (
                not isinstance(old, str)
                or not isinstance(new, str)
                or old in identities
                or new in targets
            ):
                raise ValueError("copy_identity_mismatch")
            identities[old] = new
            targets.add(new)
        if kind == "field" and left.get("key") == old and right.get("key") == new:
            tag = package.elements[new].find(W + "sdtPr/" + W + "tag")
            if tag is None or not tag.get(W + "val", "").strip():
                left["key"] = right["key"]
        if left != right:
            raise ValueError("copy_property_mismatch")
        before, after = children(source), children(target)
        if len(before) != len(after):
            raise ValueError("copy_structure_mismatch")
        pending.extend(zip(before, after, strict=True))
    return identities


@dataclass
class PreparedCopy:
    document: dict
    review: dict | None
    identities: dict[str, str]
    controls: dict

    def bind(self, target_version):
        if self.review is not None:
            self.review["sourceVersion"] = str(target_version)
            for item in self.review["items"]:
                location = item["location"]
                if location["kind"] != "control":
                    continue
                if item["missing"]:
                    # A removed source position can now name another live control.
                    token = f"{target_version}:{location['id']}".encode()
                    location["id"] = "missing:" + hashlib.sha256(token).hexdigest()
                else:
                    location["id"] = self.identities[location["id"]]
                    current = self.controls[location["id"]]
                    item.update(key=current["key"], label=current["label"])
            self.document["attrs"] = {"review": self.review}
        return self.document


def prepare(model, package, source_version, previous_origin=None):
    """Do parsing/tree work before the storage finalization transaction."""
    document, review = validate_working(model, source_version, previous_origin)
    identities = correspondence(document, package)
    copied = deepcopy(package.model)
    _, controls = index(copied)
    return PreparedCopy(copied, review, identities, controls)


def rebase_discovery(data, source_version, source, target_version, target, identities):
    snapshot = validate_snapshot(data, source_version, source).model_dump(mode="json")
    snapshot["source_version_id"] = str(target_version)
    for occurrence in snapshot["occurrences"]:
        anchor = occurrence["anchor"]
        anchor["paragraph_id"] = identities[anchor["paragraph_id"]]
        if anchor["kind"] == "control":
            anchor["control_id"] = identities[anchor["control_id"]]
    return validate_snapshot(snapshot, target_version, target)
