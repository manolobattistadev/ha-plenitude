"""Websocket command for the cards: which statistics, categories and prices each supply has.

The cards read the values themselves with ``recorder/statistics_during_period``; this command only tells them
what to ask for. It returns no consumption values and no identifiers of the customer.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .bands import BANDS, PRICE_MODE, PRICE_NONE, price_of
from .const import CATEGORY_ORDER, DOMAIN, STAT_COST, STAT_ENERGY
from .coordinator import CURRENCY, PlenitudeCoordinator


def entry_info(entry_id: str, title: str, coordinator: PlenitudeCoordinator) -> dict[str, Any]:
    options = coordinator.config_entry.options
    data = coordinator.data
    return {
        "entry_id": entry_id,
        "title": title,
        "first_day": coordinator.first_day.isoformat() if coordinator.first_day else None,
        "last_day": data.last_day.isoformat() if data and data.last_day else None,
        "price_mode": options.get(PRICE_MODE, PRICE_NONE),
        # Energy price of each band (0 without a price of the energy); None when there is no cost at all.
        "prices": {name: price_of(name, options) or 0.0 for name in BANDS} if coordinator.has_cost else None,
        # Additional costs: the cards add the costs per kWh to the band prices and spread the periodic ones.
        "costs": [item.as_dict() for item in coordinator.cost_items],
        "currency": CURRENCY,
        "statistics": {
            STAT_ENERGY: coordinator.energy_id,
            **{name: coordinator.band_id(name) for name in BANDS},
            STAT_COST: coordinator.cost_id if coordinator.has_cost else None,
        },
        "categories": [
            {
                "key": slug,
                "name": coordinator.category_names.get(slug, slug),  # the portal's; the cards translate by key
                "statistic_id": coordinator.category_id(slug),
            }
            for slug in CATEGORY_ORDER
        ],
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/info"})
@callback
def ws_info(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entries = [
        entry_info(entry.entry_id, entry.title, entry.runtime_data)
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    connection.send_result(msg["id"], {"entries": entries})


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_info)
