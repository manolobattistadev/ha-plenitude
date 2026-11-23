"""Configuration flow: login, choice of the supply, re-authentication, price options."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.plenitude.api import PlenitudeAuthError, PlenitudeSessionExpired, Supply
from custom_components.plenitude.bands import PRICE_MODE
from custom_components.plenitude.config_flow import _electric_supplies
from custom_components.plenitude.const import CONF_SUPPLY, DOMAIN, supply_key

from .conftest import POD, FakeClient, FakePortal

OTHER_POD = "IT001E88888888"  # fake
CREDENTIALS = {"email": "test@example.com", "password": "secret"}


def supply(pod: str) -> Supply:
    return Supply(kind="LUCE", pod=pod, pdr=None, contract_id="1", house_id="2", address="Via di prova 1")


@pytest.fixture(autouse=True)
def no_setup():
    with patch("custom_components.plenitude.async_setup_entry", return_value=True):
        yield


def login_returns(value=None, error=None):
    return patch(
        "custom_components.plenitude.config_flow._electric_supplies", AsyncMock(return_value=value, side_effect=error)
    )


@pytest.mark.parametrize(("language", "title"), [("en", "Plenitude electricity"), ("it", "Plenitude luce")])
async def test_single_supply(hass: HomeAssistant, language: str, title: str) -> None:
    hass.config.language = language  # the title follows the language of the server
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with login_returns([supply(POD)]):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == {**CREDENTIALS, CONF_SUPPLY: supply_key(POD)}
    assert POD not in str(result["data"])  # only the hash of the POD is stored
    assert result["options"] == {PRICE_MODE: "none"}


async def test_two_supplies(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with login_returns([supply(POD), supply(OTHER_POD)]):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["step_id"] == "supply"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_SUPPLY: supply_key(OTHER_POD)})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Plenitude electricity …8888"
    assert result["data"][CONF_SUPPLY] == supply_key(OTHER_POD)


@pytest.mark.parametrize(
    ("error", "value", "expected"),
    [
        (PlenitudeAuthError(403042, "Invalid LoginID"), None, "invalid_auth"),
        (TimeoutError(), None, "cannot_connect"),
        (PlenitudeSessionExpired("/api/contiServices/conti/…/lista-forniture: HTTP 401"), None, "portal_refused"),
        (None, [], "no_supplies"),
    ],
)
async def test_errors(hass: HomeAssistant, error, value, expected) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with login_returns(value, error):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_already_configured(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=supply_key(POD), data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with login_returns([supply(POD)]):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=supply_key(POD), data={**CREDENTIALS, CONF_SUPPLY: supply_key(POD)}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    with login_returns(error=PlenitudeAuthError(403042, "Invalid LoginID")):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}
    with login_returns([supply(POD)]):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new"


async def test_price_options(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=supply_key(POD),
        data={**CREDENTIALS, CONF_SUPPLY: supply_key(POD)},
        options={PRICE_MODE: "none"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {PRICE_MODE: "three"})
    assert result["step_id"] == "prices"
    assert set(result["data_schema"].schema) == {"price_f1", "price_f2", "price_f3"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"price_f1": 0.31, "price_f2": 0.27, "price_f3": 0.22}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {PRICE_MODE: "three", "price_f1": 0.31, "price_f2": 0.27, "price_f3": 0.22}

    # Back to a single price: only that price is asked and stored.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {PRICE_MODE: "single"})
    assert set(result["data_schema"].schema) == {"price"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"price": 0.29})
    assert entry.options == {PRICE_MODE: "single", "price": 0.29}


async def test_costs(hass: HomeAssistant) -> None:
    """Costs are subentries: as many as wanted, each with name, kind and amount (at most 6 decimals)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=supply_key(POD),
        data={**CREDENTIALS, CONF_SUPPLY: supply_key(POD)},
        options={PRICE_MODE: "none"},
    )
    entry.add_to_hass(hass)

    async def add(user_input: dict) -> dict:
        result = await hass.config_entries.subentries.async_init((entry.entry_id, "cost"), context={"source": "user"})
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
        return await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)

    result = await add({"name": "Canone RAI", "kind": "yearly", "amount": 90})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await add({"name": " Oneri di sistema ", "kind": "per_kwh", "amount": 0.041234})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    costs = {sub.title: dict(sub.data) for sub in entry.subentries.values()}
    assert costs == {
        "Canone RAI": {"name": "Canone RAI", "kind": "yearly", "amount": 90.0},
        "Oneri di sistema": {"name": "Oneri di sistema", "kind": "per_kwh", "amount": 0.041234},
    }

    result = await add({"name": "Troppi decimali", "kind": "monthly", "amount": 0.1234567})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"amount": "too_many_decimals"}
    result = await add({"name": "   ", "kind": "monthly", "amount": 1})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"name": "empty_name"}

    # Edit one: the form starts from its values.
    subentry_id = next(sid for sid, sub in entry.subentries.items() if sub.title == "Canone RAI")
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Canone TV", "kind": "monthly", "amount": 9}
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].title == "Canone TV"
    assert dict(entry.subentries[subentry_id].data) == {"name": "Canone TV", "kind": "monthly", "amount": 9.0}


def suggested(result: dict, field: str):
    for key in result["data_schema"].schema:
        if key == field:
            return (key.description or {}).get("suggested_value")
    raise KeyError(field)


async def test_cost_per_kw_asks_the_power(hass: HomeAssistant) -> None:
    """A cost per kW per month asks the power of the contract in a second step, and keeps it when edited."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=supply_key(POD),
        data={**CREDENTIALS, CONF_SUPPLY: supply_key(POD)},
        options={PRICE_MODE: "none"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init((entry.entry_id, "cost"), context={"source": "user"})
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Quota potenza", "kind": "per_kw_monthly", "amount": 1.716}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "power"
    assert result["description_placeholders"] == {"name": "Quota potenza"}
    assert suggested(result, "power") is None  # entry not loaded: no power from the customer area
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"power": 4.1234567})
    assert result["errors"] == {"power": "invalid_power"}  # 0 and negatives are refused by the selector itself
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"power": 4.5})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry_id,) = entry.subentries
    expected = {"name": "Quota potenza", "kind": "per_kw_monthly", "amount": 1.716, "power": 4.5}
    assert dict(entry.subentries[subentry_id].data) == expected

    # Edit: the power entered before is suggested.
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Quota potenza", "kind": "per_kw_monthly", "amount": 1.8}
    )
    assert result["step_id"] == "power" and suggested(result, "power") == 4.5
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"power": 6})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert dict(entry.subentries[subentry_id].data) == {**expected, "amount": 1.8, "power": 6.0}

    # Changed to a monthly cost: no second step, no power.
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Quota fissa", "kind": "monthly", "amount": 9}
    )
    assert result["type"] is FlowResultType.ABORT
    assert dict(entry.subentries[subentry_id].data) == {"name": "Quota fissa", "kind": "monthly", "amount": 9.0}


@pytest.mark.parametrize("refused", [False, True])
async def test_the_throw_away_login_is_closed(hass: HomeAssistant, refused: bool) -> None:
    """The login of the configuration is closed, also when the portal refuses the data."""
    portal = FakePortal()
    client = FakeClient(portal)
    if refused:
        client.get_supplies = AsyncMock(side_effect=PlenitudeSessionExpired("HTTP 401"))
    with patch("custom_components.plenitude.config_flow.PlenitudeClient", return_value=client):
        if refused:
            with pytest.raises(PlenitudeSessionExpired):
                await _electric_supplies(hass, "test@example.com", "secret")
        else:
            assert len(await _electric_supplies(hass, "test@example.com", "secret")) == 1
    assert (portal.logins, portal.logouts) == (1, 1)
