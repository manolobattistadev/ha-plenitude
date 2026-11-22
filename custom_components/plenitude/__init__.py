"""Eni Plenitude: electricity consumption from the Plenitude customer area as long-term statistics."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import aiohttp
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import websocket
from .api import PlenitudeError
from .const import CARDS_FILE, CARDS_URL, DOMAIN
from .coordinator import PlenitudeConfigEntry, PlenitudeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Once per start: the websocket command and the cards for the frontend."""
    websocket.async_register(hass)
    await _async_register_cards(hass)
    return True


async def _async_register_cards(hass: HomeAssistant) -> None:
    """Serve the cards and make every dashboard load them: nothing to install by hand."""
    if hass.http is None or "frontend" not in hass.config.components:
        _LOGGER.debug("Frontend not loaded: cards not registered")
        return
    from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415
    from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

    content = await hass.async_add_executor_job((FRONTEND_DIR / CARDS_FILE).read_bytes)
    version = hashlib.sha256(content).hexdigest()[:8]  # changes with the file: browsers reload it
    await hass.http.async_register_static_paths([StaticPathConfig(CARDS_URL, str(FRONTEND_DIR), False)])
    add_extra_js_url(hass, f"{CARDS_URL}/{CARDS_FILE}?v={version}")


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
