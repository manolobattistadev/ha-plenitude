"""Constants of the Eni Plenitude integration."""

from __future__ import annotations

import hashlib
from datetime import timedelta

DOMAIN = "plenitude"

CONF_SUPPLY = "supply"  # key of the supply: hash of the POD, never the POD itself

# The Gigya session lasts what the login asks for: 30 days were granted on 2026-11-22.
SESSION_EXPIRATION = 30 * 24 * 3600

# Data arrive about two days late, once a day: a few checks a day are enough.
UPDATE_INTERVAL = timedelta(hours=6)
# Days without data in this window are asked again (once a day), in case they arrive late.
RECHECK_DAYS = 14
# First import: walk back until this many consecutive days without data, at most HISTORY_MAX_DAYS.
HISTORY_EMPTY_RUN = 31
HISTORY_MAX_DAYS = 3 * 366
# Pause between requests during the first import, to be gentle with the portal.
REQUEST_PAUSE = 0.4

STORAGE_VERSION = 1

# Statistic keys, appended to the prefix of the supply.
STAT_ENERGY = "consumo"
STAT_COST = "costo"
CATEGORY_PREFIX = "cat_"


def supply_key(pod: str) -> str:
    """Stable, non-reversible key of a supply, used in unique ids and statistic ids."""
    return hashlib.sha256(pod.strip().upper().encode()).hexdigest()[:10]


def statistic_prefix(key: str) -> str:
    return f"{DOMAIN}:luce_{key}"
