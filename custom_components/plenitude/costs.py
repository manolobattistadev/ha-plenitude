"""Additional costs entered by the user (TV licence fee, fixed fee, charges per kWh...), and the hourly price.

Each cost is a configuration subentry of type ``cost`` with a free name, a kind and an amount in euro (at most
six decimals). Costs per kWh depend on the consumption: they are added to the price of every hour, so they are in
the cost statistic and in the Energy dashboard. Monthly, two-monthly and yearly costs do not depend on the hours:
they stay out of the statistic, and the cards spread them over the days (amount x periods per year / days of the
year).

Like ``api`` and ``bands``, this module does not import Home Assistant.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .bands import PRICE_MODE, PRICE_NONE, price_of, price_signature

COST_SUBENTRY = "cost"
COST_NAME = "name"
COST_KIND = "kind"
COST_AMOUNT = "amount"

KIND_MONTHLY = "monthly"
KIND_BIMONTHLY = "bimonthly"
KIND_YEARLY = "yearly"
KIND_PER_KWH = "per_kwh"
COST_KINDS = (KIND_MONTHLY, KIND_BIMONTHLY, KIND_YEARLY, KIND_PER_KWH)
# Periodic kinds: how many times a year they are charged.
PERIODS_PER_YEAR = {KIND_MONTHLY: 12, KIND_BIMONTHLY: 6, KIND_YEARLY: 1}

AMOUNT_DECIMALS = 6


@dataclass(frozen=True)
class CostItem:
    name: str
    kind: str
    amount: float

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> CostItem:
        return cls(name=str(data[COST_NAME]), kind=str(data[COST_KIND]), amount=float(data[COST_AMOUNT]))

    def as_dict(self) -> dict[str, Any]:
        return {COST_NAME: self.name, COST_KIND: self.kind, COST_AMOUNT: self.amount}


def has_valid_decimals(amount: float) -> bool:
    """At most six decimals, as typed (0.1234567 is refused, 0.123456 is accepted)."""
    try:
        exponent = Decimal(str(amount)).normalize().as_tuple().exponent
    except InvalidOperation:
        return False
    return isinstance(exponent, int) and exponent >= -AMOUNT_DECIMALS


def per_kwh_extra(items: Iterable[CostItem]) -> float:
    """Sum of the costs per kWh, added to the price of every hour."""
    return sum(item.amount for item in items if item.kind == KIND_PER_KWH)


def has_cost(options: Mapping[str, Any], items: Iterable[CostItem]) -> bool:
    """A cost exists with a price of the energy or with at least one additional cost."""
    return options.get(PRICE_MODE, PRICE_NONE) != PRICE_NONE or any(True for _ in items)


def hour_price(band_name: str, options: Mapping[str, Any], items: Iterable[CostItem]) -> float:
    """Price (EUR/kWh) of an hour in ``band_name``: energy price of the band plus the costs per kWh."""
    return (price_of(band_name, options) or 0.0) + per_kwh_extra(items)


def cost_signature(options: Mapping[str, Any], items: Iterable[CostItem]) -> str:
    """What the hourly cost statistic depends on: when it changes, the cost history is rebuilt."""
    items = list(items)
    if not has_cost(options, items):
        return "none"
    return f"{price_signature(options)}|kwh={round(per_kwh_extra(items), AMOUNT_DECIMALS)}"
