"""Additional costs entered by the user (TV licence fee, fixed fee, charges per kWh...), and the hourly price.

Each cost is a configuration subentry of type ``cost`` with a free name, a kind and an amount in euro (at most
six decimals). Costs per kWh depend on the consumption: they are added to the price of every hour, so they are in
the cost statistic and in the Energy dashboard. Monthly, two-monthly and yearly costs do not depend on the hours:
they stay out of the statistic, and the cards count them in full, month by month. Costs per kW per month (the
power fee of the bill) are monthly costs of ``amount x power``, with the power of the contract in kW.

Percentage costs (VAT, for example) apply to the energy price and to every other cost not marked ``exempt`` (the TV
licence fee is outside VAT), not to each other: with VAT at 10 % an hour costs ``(energy + taxed costs per kWh) x
1.10 + exempt costs per kWh``, and the cards do the same with the periodic costs.

Like ``api`` and ``bands``, this module does not import Home Assistant.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .bands import PRICE_MODE, PRICE_NONE, price_of, price_signature

COST_SUBENTRY = "cost"
COST_NAME = "name"
COST_KIND = "kind"
COST_AMOUNT = "amount"
COST_POWER = "power"
COST_EXEMPT = "exempt"

KIND_MONTHLY = "monthly"
KIND_BIMONTHLY = "bimonthly"
KIND_YEARLY = "yearly"
KIND_PER_KW_MONTHLY = "per_kw_monthly"
KIND_PER_KWH = "per_kwh"
KIND_PERCENT = "percent"
COST_KINDS = (KIND_MONTHLY, KIND_BIMONTHLY, KIND_YEARLY, KIND_PER_KW_MONTHLY, KIND_PER_KWH, KIND_PERCENT)
# Periodic kinds: how many times a year they are charged.
PERIODS_PER_YEAR = {KIND_MONTHLY: 12, KIND_BIMONTHLY: 6, KIND_YEARLY: 1, KIND_PER_KW_MONTHLY: 12}

AMOUNT_DECIMALS = 6


@dataclass(frozen=True)
class CostItem:
    name: str
    kind: str
    amount: float
    power: float | None = None  # kW, only for the costs per kW per month
    exempt: bool = False  # not subject to the percentage costs (never for a percentage cost itself)

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> CostItem:
        kind = str(data[COST_KIND])
        power = data.get(COST_POWER)
        return cls(
            name=str(data[COST_NAME]),
            kind=kind,
            amount=float(data[COST_AMOUNT]),
            power=float(power) if power is not None and kind == KIND_PER_KW_MONTHLY else None,
            exempt=bool(data.get(COST_EXEMPT, False)) and kind != KIND_PERCENT,
        )

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {COST_NAME: self.name, COST_KIND: self.kind, COST_AMOUNT: self.amount}
        if self.kind == KIND_PER_KW_MONTHLY:
            data[COST_POWER] = self.power
        if self.kind != KIND_PERCENT:
            data[COST_EXEMPT] = self.exempt
        return data

    @property
    def yearly(self) -> float | None:
        """Euro per year of a periodic cost, without the percentages; None for the costs per kWh, which follow the
        consumption, and for the percentages, which follow the other costs."""
        times = PERIODS_PER_YEAR.get(self.kind)
        if times is None:
            return None
        factor = (self.power or 0.0) if self.kind == KIND_PER_KW_MONTHLY else 1.0
        return self.amount * factor * times


# A number as people type it: comma or point for the decimals, one of them at most, no thousands separators.
_NUMBER = re.compile(r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)")


def parse_number(value: object, minimum: float, maximum: float) -> tuple[float | None, str | None]:
    """A number typed in a form, with a comma or a point for the decimals (``9,15`` or ``9.15``); a euro sign and
    spaces around it are ignored. Returns the number and no error, or no number and the key of the error:
    ``invalid_number`` (not a number, or with thousands separators: ``1.234,56`` is refused rather than guessed),
    ``too_many_decimals`` (more than six), ``out_of_range`` (outside ``minimum``..``maximum``)."""
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None, "invalid_number"
    text = str(value).replace("\u00a0", " ").strip().removeprefix("€").removesuffix("€").strip()
    if not _NUMBER.fullmatch(text):
        return None, "invalid_number"
    text = text.replace(",", ".")
    if len(text.partition(".")[2]) > AMOUNT_DECIMALS:
        return None, "too_many_decimals"
    number = float(text)
    if not minimum <= number <= maximum:
        return None, "out_of_range"
    return number, None


def format_number(value: float | None, language: str) -> str | None:
    """A stored number shown in a form: no trailing zeros, decimal comma in Italian."""
    if value is None:
        return None
    text = f"{value:.{AMOUNT_DECIMALS}f}".rstrip("0").rstrip(".")
    text = "0" if text == "-0" else text
    return text.replace(".", ",") if language.lower().startswith("it") else text


def has_valid_decimals(amount: float) -> bool:
    """At most six decimals, as typed (0.1234567 is refused, 0.123456 is accepted)."""
    try:
        exponent = Decimal(str(amount)).normalize().as_tuple().exponent
    except InvalidOperation:
        return False
    return isinstance(exponent, int) and exponent >= -AMOUNT_DECIMALS


def per_kwh_extra(items: Iterable[CostItem], exempt: bool = False) -> float:
    """Sum of the costs per kWh subject to the percentages (or, with ``exempt``, of those that are not)."""
    return sum(item.amount for item in items if item.kind == KIND_PER_KWH and item.exempt == exempt)


def percent_rate(items: Iterable[CostItem]) -> float:
    """Sum of the percentage costs as a fraction (VAT at 10 %: 0.10). They do not apply to each other."""
    return sum(item.amount for item in items if item.kind == KIND_PERCENT) / 100


def has_cost(options: Mapping[str, Any], items: Iterable[CostItem]) -> bool:
    """A cost exists with a price of the energy or with at least one additional cost."""
    return options.get(PRICE_MODE, PRICE_NONE) != PRICE_NONE or any(True for _ in items)


def hour_price(band_name: str, options: Mapping[str, Any], items: Iterable[CostItem]) -> float:
    """Price (EUR/kWh) of an hour in ``band_name``: energy price of the band plus the costs per kWh, the
    percentages applied to the energy and to the costs that are not exempt."""
    items = list(items)
    taxed = (price_of(band_name, options) or 0.0) + per_kwh_extra(items)
    return taxed * (1 + percent_rate(items)) + per_kwh_extra(items, exempt=True)


def cost_signature(options: Mapping[str, Any], items: Iterable[CostItem]) -> str:
    """What the hourly cost statistic depends on: when it changes, the cost history is rebuilt."""
    items = list(items)
    if not has_cost(options, items):
        return "none"
    signature = f"{price_signature(options)}|kwh={round(per_kwh_extra(items), AMOUNT_DECIMALS)}"
    # Added only when present, so that the entries without them keep their signature and are not rebuilt.
    if exempt := round(per_kwh_extra(items, exempt=True), AMOUNT_DECIMALS):
        signature += f"|exempt={exempt}"
    if rate := round(percent_rate(items), AMOUNT_DECIMALS + 2):
        signature += f"|percent={rate}"
    return signature
