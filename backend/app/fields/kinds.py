"""Deterministic field-type hints from value shapes and nearby labels.

Classification only proposes the fill-time kind recorded on candidates and
fields; review can change it. Ukrainian inflections and token keys joined by
underscores drive substring roots; English relies on word boundaries. Document
numbers («номер», "number") stay text because they legitimately contain
letters, leading zeros and dashes, and contact/postal labels force text over
numeric-looking values.
"""

import re

from app.fields.schema import FieldType

# Dates: D.M.YYYY, YYYY-M-D with any separator, or the «дд.мм.рррр» form.
DATE_VALUE = re.compile(
    r"^(?:\d{1,2}[ \t]*[./-][ \t]*\d{1,2}[ \t]*[./-][ \t]*\d{2,4}"
    r"|\d{4}[ \t]*[./-][ \t]*\d{1,2}[ \t]*[./-][ \t]*\d{1,2}"
    r"|[дd]{1,2}[ \t]*[./-][ \t]*[мm]{1,2}[ \t]*[./-][ \t]*[рry]{2,4})$",
    re.IGNORECASE,
)
# Blank shapes: exactly three digit/underscore segments «__.__.____».
SEGMENTED = re.compile(r"^[\d_]{1,6}[ \t]*(?:[./-][ \t]*[\d_]{1,6}[ \t]*){2}$")
# Amounts: optional minus, space thousands, one decimal separator.
NUMBER_VALUE = re.compile(
    r"^-(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?$"
    r"|^\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?$|^\d+(?:[.,]\d+)?$"
)
DATE_LABEL = re.compile(r"дат|\bdate\b", re.IGNORECASE)
TEXT_LABEL = re.compile(
    r"телефон|\bтелеф|\bпошт|адрес|\baddress\b|\bphone\b|\be-?mail\b|\bmail\b",
    re.IGNORECASE,
)
NUMBER_PREFIX = re.compile(r"\b(?:кільк|вартіст|вартост|цін)", re.IGNORECASE)
NUMBER_WORD = re.compile(
    r"\b(?:сум(?:а|и|і|у|ою|ах|ам)?|в[іi]к|amount|price|quantity|total|sum|count|age)\b",
    re.IGNORECASE,
)


def classify(value: str, label: str | None) -> FieldType:
    """Return the proposed type for one occurrence from its value and label."""
    text = value.strip()
    if DATE_VALUE.match(text) or SEGMENTED.match(text):
        return "date"
    # Token keys join words with underscores; keyword matching reads them as
    # separators, while «№» keeps its original position.
    name = (label or "").strip()
    words = name.replace("_", " ")
    if DATE_LABEL.search(words):
        return "date"
    if TEXT_LABEL.search(words):
        return "text"
    if "№" in name or NUMBER_PREFIX.search(words) or NUMBER_WORD.search(words):
        return "number"
    if NUMBER_VALUE.match(text):
        return "number"
    return "text"
