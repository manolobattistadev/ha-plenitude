"""Diagnostics: useful for an issue, and safe to publish."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.plenitude.api import ROME
from custom_components.plenitude.bands import PRICE_MODE
from custom_components.plenitude.const import CONF_SUPPLY, DOMAIN, supply_key
from custom_components.plenitude.diagnostics import async_get_config_entry_diagnostics

from .conftest import POD, FakePortal

EMAIL = "someone@example.com"
PASSWORD = "a-distinctive-password"


async def test_diagnostics_hide_personal_data(
    recorder_mock, hass: HomeAssistant, freezer, fake_client: FakePortal
) -> None:
    freezer.move_to(datetime(2026, 11, 22, 12, tzinfo=ROME))
    fake_client.days = {date(2026, 11, 20) - timedelta(days=i) for i in range(5)}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Plenitude luce …9999",
        unique_id=supply_key(POD),
        data={"email": EMAIL, "password": PASSWORD, CONF_SUPPLY: supply_key(POD)},
        options={PRICE_MODE: "single", "price": 0.3},
        subentries_data=(
            {
                "data": {"name": "Quota fissa", "kind": "monthly", "amount": 10.0},
                "subentry_type": "cost",
                "title": "Quota fissa",
                "unique_id": None,
            },
        ),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(result)
    for secret in (EMAIL, PASSWORD, POD, supply_key(POD), "9999", "Via di prova"):
        assert secret not in text
    assert result["entry"]["costs"] == [{"name": "Quota fissa", "kind": "monthly", "amount": 10.0}]
    assert result["supply"] == {"found": True, "consumption_analysis": True}
    assert result["sync"]["last_update_success"] is True
    assert result["sync"]["first_day"] == "2026-11-16"
    assert result["sync"]["last_day"] == "2026-11-20"
