"""Diagnostics (Settings > Devices & services > Eni Plenitude > ... > Download diagnostics).

Made to be attached to a public issue: no credentials, tokens, cookies, customer codes, POD (not even its short
hash, which can be brute-forced back to the POD), address or consumption values. Only the state of the
session, the dates of the imported history and the options.
"""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_SUPPLY, VERSION
from .coordinator import PlenitudeConfigEntry

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, CONF_SUPPLY}


def _mask(message: str) -> str:
    """Long numbers in error messages may be customer codes."""
    return re.sub(r"\d{5,}", "…", message)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PlenitudeConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    client = coordinator.client
    data = coordinator.data
    supply = coordinator.supply
    expires = client.login_token_expires_at
    return {
        "integration_version": VERSION,
        "server_language": coordinator.language,
        "commodity": coordinator.commodity,
        "entry": {
            "title": REDACTED,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
            "costs": [item.as_dict() for item in coordinator.cost_items],
        },
        "session": {
            "gigya_session": client.login_token is not None,
            "gigya_session_expires_at": expires.isoformat() if expires else None,
            "portal_session_cookies": client.has_portal_session(),
        },
        "supply": {
            "found": supply is not None,
            "consumption_analysis": bool(supply and supply.contract_id and supply.house_id),
        },
        "sync": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": _mask(repr(coordinator.last_exception)) if coordinator.last_exception else None,
            "update_interval": str(coordinator.update_interval),
            "first_day": coordinator.first_day.isoformat() if coordinator.first_day else None,
            "last_day": data.last_day.isoformat() if data and data.last_day else None,
            "last_day_has_consumption": bool(data and data.last_day_kwh),
            "gaps_checked": coordinator.gaps_checked,
        },
    }
