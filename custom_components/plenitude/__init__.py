"""Eni Plenitude: electricity consumption from the Plenitude customer area as long-term statistics."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path

import aiohttp
from homeassistant.config_entries import SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntry, ConfigEntryChange
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import websocket
from .api import PlenitudeError, safe_error
from .const import CARDS_FILE, CARDS_URL, DOMAIN
from .coordinator import PlenitudeConfigEntry, PlenitudeCoordinator, async_close_login, cost_items

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
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

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
    except UpdateFailed as err:
        # Same translated message in the integration card ("will retry: ...").
        raise ConfigEntryNotReady(
            translation_domain=err.translation_domain,
            translation_key=err.translation_key,
            translation_placeholders=err.translation_placeholders,
        ) from err
    except (PlenitudeError, aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": safe_error(err)},
        ) from err
    entry.runtime_data = coordinator
    entry.async_on_unload(_reload_when_costs_change(hass, entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The first import can take minutes (one request per day of history): it runs in the background.
    entry.async_create_background_task(hass, coordinator.async_refresh(), f"{DOMAIN}_first_sync")
    return True


def _reload_when_costs_change(hass: HomeAssistant, entry: PlenitudeConfigEntry) -> Callable[[], None]:
    """Costs are subentries: adding, editing or deleting one does not reload the entry by itself.

    The prices are options and reload through ``OptionsFlowWithReload``; an update listener is not allowed with
    it, so the change of the costs is caught on the signal of the changed entry.
    """
    loaded = cost_items(entry)

    @callback
    def changed(change: ConfigEntryChange, changed_entry: ConfigEntry) -> None:
        if (
            change is ConfigEntryChange.UPDATED
            and changed_entry.entry_id == entry.entry_id
            and cost_items(changed_entry) != loaded
        ):
            hass.config_entries.async_schedule_reload(entry.entry_id)

    return async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, changed)


async def async_unload_entry(hass: HomeAssistant, entry: PlenitudeConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PlenitudeConfigEntry) -> None:
    """Removed entry: close its login (it would keep a place among the sessions of the account for 30 days)."""
    await async_close_login(hass, entry.entry_id)
