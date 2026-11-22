"""Additional costs: amounts, hourly price and what rebuilds the cost history (no Home Assistant needed)."""

from __future__ import annotations

import pytest

from custom_components.plenitude.costs import (
    CostItem,
    cost_signature,
    has_cost,
    has_valid_decimals,
    hour_price,
    per_kwh_extra,
)

NO_PRICE = {"price_mode": "none"}
SINGLE = {"price_mode": "single", "price": 0.2}


@pytest.mark.parametrize(
    ("amount", "valid"),
    [(90, True), (0.123456, True), (0.1, True), (-5.25, True), (1e-6, True), (0.1234567, False), (1e-7, False)],
)
def test_at_most_six_decimals(amount: float, valid: bool) -> None:
    assert has_valid_decimals(amount) is valid


def test_hour_price_adds_the_costs_per_kwh() -> None:
    items = [CostItem("Oneri", "per_kwh", 0.04), CostItem("Accise", "per_kwh", 0.0227), CostItem("RAI", "yearly", 90)]
    assert per_kwh_extra(items) == pytest.approx(0.0627)
    assert hour_price("f1", SINGLE, items) == pytest.approx(0.2627)
    assert hour_price("f3", NO_PRICE, items) == pytest.approx(0.0627)


def test_what_needs_a_cost_statistic() -> None:
    assert not has_cost(NO_PRICE, [])
    assert has_cost(SINGLE, [])
    assert has_cost(NO_PRICE, [CostItem("RAI", "yearly", 90)])


def test_only_prices_and_costs_per_kwh_rebuild_the_history() -> None:
    base = cost_signature(SINGLE, [CostItem("RAI", "yearly", 90)])
    assert cost_signature(SINGLE, [CostItem("Canone", "monthly", 9)]) == base  # periodic costs: not hourly
    assert cost_signature(SINGLE, [CostItem("Oneri", "per_kwh", 0.01)]) != base
    assert cost_signature({"price_mode": "single", "price": 0.25}, []) != cost_signature(SINGLE, [])
    assert cost_signature(NO_PRICE, []) == "none"
