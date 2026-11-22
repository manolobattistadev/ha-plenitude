"""ARERA time bands (fasce orarie) of Italian electricity tariffs, and the price of each hour.

Source: ARERA deliberation 181/06, Tabella 1 "fasce orarie con decorrenza 1 gennaio 2007"
(https://www.arera.it/atti-e-provvedimenti/dettaglio/06/181-06), read on 2026-11-22:

- F1: Monday to Friday, 08:00-19:00;
- F2: Monday to Friday, 07:00-08:00 and 19:00-23:00; Saturday, 07:00-23:00;
- F3: Monday to Saturday, 23:00-07:00; Sundays and holidays, all day.

Holidays listed by the table: 1 January, 6 January, Easter Monday, 25 April, 1 May, 2 June, 15 August,
1 November, 8 December, 25 December, 26 December. 4 October, a national holiday again since 2026, is not in
the table and is therefore treated as a working day until ARERA updates it.

Like ``api``, this module does not import Home Assistant.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any

F1 = "f1"
F2 = "f2"
F3 = "f3"
BANDS = (F1, F2, F3)

_FIXED_HOLIDAYS = {(1, 1), (1, 6), (4, 25), (5, 1), (6, 2), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)}

# Price options (stored in the config entry options, EUR per kWh).
PRICE_MODE = "price_mode"
PRICE_NONE = "none"  # no price: no cost statistic
PRICE_SINGLE = "single"  # monoraria: one price for every hour
PRICE_TWO = "two"  # bioraria: F1 and F23 (= F2 + F3)
PRICE_THREE = "three"  # multioraria: F1, F2, F3
PRICE_MODES = (PRICE_NONE, PRICE_SINGLE, PRICE_TWO, PRICE_THREE)
PRICE_ALL = "price"
PRICE_F1 = "price_f1"
PRICE_F2 = "price_f2"
PRICE_F3 = "price_f3"
PRICE_F23 = "price_f23"
PRICE_FIELDS = {
    PRICE_NONE: (),
    PRICE_SINGLE: (PRICE_ALL,),
    PRICE_TWO: (PRICE_F1, PRICE_F23),
    PRICE_THREE: (PRICE_F1, PRICE_F2, PRICE_F3),
}


def easter_sunday(year: int) -> date:
    """Gregorian Easter Sunday (anonymous algorithm, Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 - name of the published algorithm
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def is_holiday(day: date) -> bool:
    """Holiday according to the ARERA table (Sundays are handled separately)."""
    return (day.month, day.day) in _FIXED_HOLIDAYS or day == easter_sunday(day.year) + timedelta(days=1)


def band(local_start: datetime) -> str:
    """Band of the hour that starts at ``local_start``, which must be Italian local time."""
    hour, weekday = local_start.hour, local_start.weekday()
    if weekday == 6 or is_holiday(local_start.date()) or hour < 7 or hour >= 23:
        return F3
    if weekday == 5:
        return F2
    return F1 if 8 <= hour < 19 else F2


def price_signature(options: Mapping[str, Any]) -> str:
    """Compact description of the configured prices: when it changes, the cost history is rebuilt."""
    mode = options.get(PRICE_MODE, PRICE_NONE)
    values = ",".join(f"{field}={float(options[field])}" for field in PRICE_FIELDS.get(mode, ()))
    return f"{mode}:{values}"


def price_of(band_name: str, options: Mapping[str, Any]) -> float | None:
    """Price (EUR/kWh) of an hour in ``band_name``, or ``None`` if no price is configured."""
    mode = options.get(PRICE_MODE, PRICE_NONE)
    if mode == PRICE_SINGLE:
        return float(options[PRICE_ALL])
    if mode == PRICE_TWO:
        return float(options[PRICE_F1] if band_name == F1 else options[PRICE_F23])
    if mode == PRICE_THREE:
        return float(options[{F1: PRICE_F1, F2: PRICE_F2, F3: PRICE_F3}[band_name]])
    return None
