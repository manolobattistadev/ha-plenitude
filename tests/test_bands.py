"""ARERA bands and prices."""

from datetime import date, datetime

import pytest

from custom_components.plenitude.api import ROME
from custom_components.plenitude.bands import (
    F1,
    F2,
    F3,
    PRICE_MODE,
    band,
    easter_sunday,
    is_holiday,
    price_of,
    price_signature,
)


def local(year, month, day, hour):
    return datetime(year, month, day, hour, tzinfo=ROME)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (local(2026, 11, 23, 8), F1),  # Monday 08:00
        (local(2026, 11, 23, 18), F1),  # 18:00-19:00 is the last F1 hour
        (local(2026, 11, 23, 19), F2),  # 19:00-20:00 is F2
        (local(2026, 11, 23, 7), F2),
        (local(2026, 11, 23, 22), F2),
        (local(2026, 11, 23, 23), F3),
        (local(2026, 11, 23, 6), F3),
        (local(2026, 11, 28, 10), F2),  # Saturday daytime
        (local(2026, 11, 28, 23), F3),  # Saturday night
        (local(2026, 11, 28, 6), F3),
        (local(2026, 11, 29, 12), F3),  # Sunday
        (local(2026, 12, 8, 10), F3),  # Tuesday, Immacolata
        (local(2026, 4, 6, 10), F3),  # Easter Monday 2026
        (local(2026, 4, 7, 10), F1),  # the day after is a working day
        (local(2027, 10, 4, 10), F1),  # 4 October is not in the ARERA table
    ],
)
def test_band(moment, expected):
    assert band(moment) == expected


def test_easter():
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert easter_sunday(2027) == date(2027, 3, 28)
    assert easter_sunday(2025) == date(2025, 4, 20)
    assert is_holiday(date(2027, 3, 29))


def test_prices():
    three = {PRICE_MODE: "three", "price_f1": 0.3, "price_f2": 0.25, "price_f3": 0.2}
    assert price_of(F2, three) == 0.25
    two = {PRICE_MODE: "two", "price_f1": 0.3, "price_f23": 0.22}
    assert price_of(F1, two) == 0.3 and price_of(F3, two) == 0.22
    assert price_of(F3, {PRICE_MODE: "single", "price": 0.27}) == 0.27
    assert price_of(F1, {}) is None
    assert price_signature(three) != price_signature({**three, "price_f3": 0.21})
    assert price_signature({PRICE_MODE: "none", "price": 1}) == price_signature({})
