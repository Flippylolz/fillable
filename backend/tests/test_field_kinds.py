"""Deterministic text/number/date proposals from values and nearby labels."""

import pytest

from app.fields.kinds import classify


@pytest.mark.parametrize(
    "value,label,expected",
    [
        ("__.__.____", None, "date"),
        ("____ / ____ / ____", None, "date"),
        ("__-__-____", None, "date"),
        ("16.09.2026", None, "date"),
        ("16 / 09 / 2026", None, "date"),
        ("2026-09-16", None, "date"),
        ("дд.мм.рррр", None, "date"),
        ("dd.mm.yyyy", None, "date"),
        ("{{ДАТА_АНКЕТИ}}", "ДАТА_АНКЕТИ", "date"),
        ("{{НЕ_ЗАПОВНЮВАТИ}}", "НЕ_ЗАПОВНЮВАТИ", "text"),
        ("", "Дата події", "date"),
        ("", "Date of birth", "date"),
        ("2026", "Дата анкети", "date"),
        ("____.____", None, "text"),
        ("____—____", None, "text"),
        ("0501234567", "Телефон", "text"),
        ("+380501234567", "Телефон", "text"),
        ("01001", "Поштовий індекс", "text"),
        ("Майстерня «Їжак і Ґудзик»", "Організація", "text"),
        ("", "Номер клієнта", "text"),
        ("", "СУМА_ДОГОВОРУ", "number"),
        ("", "КІЛЬКІСТЬ_ГОДИН", "number"),
        ("42", "№ рахунку", "number"),
        ("№ 123-А", "Номер договору", "text"),
        ("1 250,50", "Сума договору", "number"),
        ("1 250,50", None, "number"),
        ("1 250,50", "Кількість телефонів", "text"),
        ("42", None, "number"),
        ("12,5", None, "number"),
        ("42", "Кількість годин", "number"),
        ("42", "Вартість робіт", "number"),
        ("42", "ціна", "number"),
        ("7", "Вік", "number"),
        ("7", "Age", "number"),
        ("19", "Total amount", "number"),
        ("16.09", None, "number"),
        ("2026", None, "number"),
        ("1 250,50 грн", None, "text"),
        ("16.09.20", None, "date"),
        ("", None, "text"),
        ("   ", None, "text"),
        (" ", "  ", "text"),
    ],
)
def test_value_shapes_and_labels_classify_reviewable_kinds(value, label, expected):
    assert classify(value, label) == expected
