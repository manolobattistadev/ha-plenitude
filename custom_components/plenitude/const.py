"""Constants of the Eni Plenitude integration."""

from __future__ import annotations

import hashlib
from datetime import timedelta

DOMAIN = "plenitude"
VERSION = "0.5.2"

# Cards (frontend/plenitude-cards.js), served by the integration and loaded by the frontend.
CARDS_URL = "/plenitude_static"
CARDS_FILE = "plenitude-cards.js"

CONF_SUPPLY = "supply"  # key of the supply: hash of the POD, never the POD itself

# The Gigya session lasts what the login asks for: 30 days were granted on 2026-11-22.
SESSION_EXPIRATION = 30 * 24 * 3600
# Minimum time between two logins with the password: when the customer area refuses the data of a new login,
# Home Assistant retries the setup every 80 seconds, and a login each time would only multiply the sessions.
LOGIN_PAUSE = timedelta(minutes=15)

# Data arrive about two days late, once a day: a few checks a day are enough.
UPDATE_INTERVAL = timedelta(hours=6)
# Days without data in this window are asked again (once a day), in case they arrive late.
RECHECK_DAYS = 14
# First import: walk back until this many consecutive days without data, at most HISTORY_MAX_DAYS.
HISTORY_EMPTY_RUN = 31
HISTORY_MAX_DAYS = 3 * 366
# First import: days asked three at a time, with a pause after each round, to be gentle with the portal. Measured
# on 2026-11-23, same session, rounds interleaved: 15 days in 15 s one at a time, in 5-6 s three at a time, with
# the same answers and no errors.
HISTORY_WORKERS = 3
REQUEST_PAUSE = 0.4
# First import: the most recent days are written as soon as they are read, so that sensors and cards show
# something in seconds; the whole history follows (minutes for years of data) and rewrites them.
FIRST_RESULTS_DAYS = 14

STORAGE_VERSION = 1

# Statistic keys, appended to the prefix of the supply.
STAT_ENERGY = "consumo"
STAT_COST = "costo"
CATEGORY_PREFIX = "cat_"
# Order in which the portal lists the categories ("altro" last): the cards keep it, colors follow it.
CATEGORY_ORDER = (
    "comfort_ambientale",
    "standby",
    "lavare",
    "elettronica_luci",
    "refrigerare",
    "cucinare",
    "ricarica_elettrica",
    "altro",
)


def supply_key(pod: str) -> str:
    """Stable, non-reversible key of a supply, used in unique ids and statistic ids."""
    return hashlib.sha256(pod.strip().upper().encode()).hexdigest()[:10]


def statistic_prefix(key: str) -> str:
    return f"{DOMAIN}:luce_{key}"
