"""Cross-language boundary vectors for save-time field validation."""

import pytest

from app.fields.values import validate_value, validate_values


@pytest.mark.parametrize(
    "kind,value",
    [
        ("number", "0"),
        ("number", "-0,25"),
        ("number", "-1 234.50"),
        ("number", "1\u00a0234\u202f567,89"),
        ("number", "\ufeff12\ufeff"),
        ("date", "2024-02-29"),
        ("date", "29.2.2000"),
        ("date", "1/1/0001"),
        ("date", "31-12-9999"),
        ("date", "1.2/2024"),
        ("text", "ҐЄІЇ іʼ’\n\t\r🙂\u0085\ue000\ufffd"),
        ("text", "🙂" * 65536),
        ("number", ""),
        ("date", " \t\n\ufeff"),
    ],
)
def test_valid_values_are_preserved(kind, value):
    validate_value(value, kind)


@pytest.mark.parametrize(
    "kind,value",
    [
        ("number", "NaN"),
        ("number", "Infinity"),
        ("number", "1e3"),
        ("number", "12 34"),
        ("number", "+1"),
        ("number", "１２"),
        ("number", "1,2.3"),
        ("number", "\u008512"),
        ("date", "2024-2-29"),
        ("date", "31.02.2024"),
        ("date", "29.02.1900"),
        ("date", "0000-01-01"),
        ("date", "2024-13-01"),
        ("date", "2024-01-00"),
        ("date", "not-a-date"),
        ("text", "🙂" * 65537),
        ("text", "\x00"),
        ("text", "\ud800"),
        ("text", "\ufffe"),
    ],
)
def test_invalid_values_are_rejected(kind, value):
    with pytest.raises(ValueError):
        validate_value(value, kind)


def test_length_is_aggregated_across_runs_even_without_review():
    field = {
        "type": "field",
        "attrs": {"id": "a"},
        "content": [
            {"type": "text", "text": "x" * 32768},
            {"type": "text", "text": "x" * 32768},
        ],
    }
    validate_values(field, None)
    field["content"][1]["text"] += "x"
    with pytest.raises(ValueError):
        validate_values(field, None)
