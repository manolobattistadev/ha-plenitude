"""Eni Plenitude: electricity consumption from the Plenitude customer area as long-term statistics."""

from __future__ import annotations

import aiohttp
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import PlenitudeError
from .const import DOMAIN
from .coordinator import PlenitudeConfigEntry, PlenitudeCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PlenitudeConfigEntry) -> bool:
    coordinator = PlenitudeCoordinator(hass, entry)
    try:
        # Session and supply first: a refused login starts the re-authentication (ConfigEntryAuthFailed
        # passes through), a network problem retries the setup later.
        await coordinator.async_prepare()
    except (UpdateFailed, PlenitudeError, aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(str(err)) from err
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The first import can take minutes (one request per day of history): it runs in the background.
    entry.async_create_background_task(hass, coordinator.async_refresh(), f"{DOMAIN}_first_sync")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlenitudeConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
