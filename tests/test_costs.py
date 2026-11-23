"""Additional costs: amounts, hourly price and what rebuilds the cost history (no Home Assistant needed)."""

from __future__ import annotations

import pytest

from custom_components.plenitude.costs import (
    CostItem,
    cost_signature,
    format_number,
    has_cost,
    has_valid_decimals,
    hour_price,
    parse_number,
    per_kwh_extra,
    percent_rate,
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


def test_yearly_amount_of_the_periodic_costs() -> None:
    assert CostItem("Quota fissa", "monthly", 10).yearly == pytest.approx(120)
    assert CostItem("Bimestre", "bimonthly", 10).yearly == pytest.approx(60)
    assert CostItem("RAI", "yearly", 90).yearly == pytest.approx(90)
    assert CostItem("Quota potenza", "per_kw_monthly", 1.5, power=4.5).yearly == pytest.approx(1.5 * 4.5 * 12)
    assert CostItem("Oneri", "per_kwh", 0.05).yearly is None  # follows the consumption


def test_power_is_kept_only_for_the_costs_per_kw() -> None:
    data = {"name": "Quota potenza", "kind": "per_kw_monthly", "amount": 1.5, "power": 6}
    item = CostItem.from_data(data)
    assert item.power == 6.0 and item.as_dict() == {**data, "power": 6.0, "exempt": False}
    # A cost changed to another kind forgets the power; costs saved before 0.4.0 have none.
    assert CostItem.from_data({**data, "kind": "monthly"}).as_dict() == {
        "name": "Quota potenza",
        "kind": "monthly",
        "amount": 1.5,
        "exempt": False,
    }
    assert CostItem.from_data({"name": "RAI", "kind": "yearly", "amount": 90}).power is None


def test_percentages_apply_to_the_energy_and_to_the_costs_not_exempt() -> None:
    vat = CostItem("IVA", "percent", 10)
    items = [CostItem("Oneri", "per_kwh", 0.04), CostItem("Bonus", "per_kwh", -0.01, exempt=True), vat]
    assert percent_rate(items) == pytest.approx(0.10)
    assert per_kwh_extra(items) == pytest.approx(0.04) and per_kwh_extra(items, exempt=True) == pytest.approx(-0.01)
    assert hour_price("f1", SINGLE, items) == pytest.approx((0.2 + 0.04) * 1.1 - 0.01)
    # Two percentages add up, they do not apply to each other: 10 % + 2 % is 12 %, not 12.2 %.
    assert hour_price("f1", SINGLE, [vat, CostItem("Altro", "percent", 2)]) == pytest.approx(0.2 * 1.12)
    assert vat.yearly is None  # follows the other costs


def test_exempt_is_kept_but_never_for_a_percentage() -> None:
    data = {"name": "Canone TV", "kind": "monthly", "amount": 9, "exempt": True}
    assert CostItem.from_data(data).exempt and CostItem.from_data(data).as_dict() == {**data, "amount": 9.0}
    assert not CostItem.from_data({"name": "RAI", "kind": "yearly", "amount": 90}).exempt  # saved before 0.5.0
    vat = CostItem.from_data({"name": "IVA", "kind": "percent", "amount": 10, "exempt": True})
    assert not vat.exempt and vat.as_dict() == {"name": "IVA", "kind": "percent", "amount": 10.0}


def test_percentages_and_exempt_costs_per_kwh_rebuild_the_history() -> None:
    before = cost_signature(SINGLE, [CostItem("Oneri", "per_kwh", 0.04), CostItem("RAI", "yearly", 90)])
    # Entries without them keep the signature of 0.4: updating does not rebuild their history.
    assert before == "single:price=0.2|kwh=0.04"
    vat = CostItem("IVA", "percent", 10)
    assert cost_signature(SINGLE, [CostItem("Oneri", "per_kwh", 0.04), vat]) != before
    exempt = CostItem("Oneri", "per_kwh", 0.04, exempt=True)
    assert cost_signature(SINGLE, [exempt]) != before
    # A periodic cost excluded from the percentages is not in the hourly cost.
    assert cost_signature(SINGLE, [CostItem("RAI", "yearly", 90, exempt=True)]) == cost_signature(SINGLE, [])


def test_costs_per_kw_do_not_rebuild_the_history() -> None:
    base = cost_signature(SINGLE, [])
    assert cost_signature(SINGLE, [CostItem("Quota potenza", "per_kw_monthly", 1.5, power=3)]) == base


@pytest.mark.parametrize(
    ("typed", "number", "error"),
    [
        ("9,15", 9.15, None),
        ("9.15", 9.15, None),
        (" € 9,15 ", 9.15, None),
        ("9,15 €", 9.15, None),
        ("-5", -5.0, None),
        (",5", 0.5, None),
        ("0,123456", 0.123456, None),
        ("0,1234567", None, "too_many_decimals"),
        ("1.234,56", None, "invalid_number"),  # thousands separators: refused, not guessed
        ("1,2,3", None, "invalid_number"),
        ("1e3", None, "invalid_number"),
        ("nove", None, "invalid_number"),
        ("", None, "invalid_number"),
        ("100", None, "out_of_range"),
        (9.5, 9.5, None),  # numbers from older forms or tests
    ],
)
def test_numbers_with_comma_or_point(typed, number, error) -> None:
    assert parse_number(typed, -10, 10) == (number, error)


@pytest.mark.parametrize(
    ("value", "language", "shown"),
    [(9.15, "it", "9,15"), (9.15, "en", "9.15"), (90.0, "it", "90"), (0.000001, "it", "0,000001"), (-0.0, "it", "0")],
)
def test_numbers_shown_in_the_forms(value, language, shown) -> None:
    assert format_number(value, language) == shown
