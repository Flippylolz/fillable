"""Save-time field constraints matching the frontend, without changing source text."""

import re
from datetime import date

# ECMAScript trim whitespace, shared with the browser's String.trim().
TRIM = (
    "\t\n\x0b\x0c\r \xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
NUMBER = re.compile(
    r"-?(?:[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+|[0-9]+)(?:[.,][0-9]+)?"
)
ISO = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
DAY_FIRST = re.compile(r"([0-9]{1,2})[./-]([0-9]{1,2})[./-]([0-9]{4})")
XML_TEXT = re.compile(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def validate_value(value: str, kind: str) -> None:
    if len(value) > 65536 or XML_TEXT.search(value):
        raise ValueError("invalid_field_value")
    text = value.strip(TRIM)
    if not text:
        return
    if kind == "number" and not NUMBER.fullmatch(text):
        raise ValueError("invalid_number")
    if kind == "date":
        iso = ISO.fullmatch(text)
        day_first = DAY_FIRST.fullmatch(text)
        if iso:
            year, month, day = map(int, iso.groups())
        elif day_first:
            day, month, year = map(int, day_first.groups())
        else:
            raise ValueError("invalid_date")
        date(year, month, day)


def validate_values(document: dict, review: dict | None) -> None:
    """Read actual control text; review locations/types have already been validated."""
    kinds = {
        item["location"]["id"]: item["type"]
        for item in (review or {}).get("items", [])
        if item["decision"] == "accepted"
    }
    pending = [document]
    while pending:
        node = pending.pop()
        children = node.get("content", [])
        if node["type"] == "field":
            value = "".join(child["text"] for child in children)
            validate_value(value, kinds.get(node["attrs"]["id"], "text"))
        pending.extend(children)
