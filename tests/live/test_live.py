"""Live check against the real Plenitude portal, in a throw-away Home Assistant with a real recorder.

Skipped unless ``PLENITUDE_LIVE=1``. Credentials come from the macOS Keychain (service ``ha-plenitude``),
as for ``scripts/prototipo.py``. The report prints counts, dates of missing days and *differences* with the
portal's own monthly figures (percent, percentage points): never kWh values, codes or credentials.

    PLENITUDE_LIVE=1 ~/venvs/ha-plenitude-test/bin/python -m pytest -s -p no:logging tests/live
"""

from __future__ import annotations

import logging
import math
import os
import re
import socket
import subprocess
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import aiohttp
import pytest
import pytest_socket
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component import plugins
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.plenitude.api import CATEGORIES, ROME
from custom_components.plenitude.bands import BANDS, PRICE_MODE, band, price_of
from custom_components.plenitude.const import DOMAIN
from custom_components.plenitude.coordinator import session_store

pytestmark = pytest.mark.skipif(os.environ.get("PLENITUDE_LIVE") != "1", reason="live check: PLENITUDE_LIVE=1")

# The test kit logs every SQL statement with its parameters, which would print the consumption values: quiet
# from the import of this module on, before the recorder starts.
if os.environ.get("PLENITUDE_LIVE") == "1":
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

PRICES = {PRICE_MODE: "three", "price_f1": 0.30, "price_f2": 0.25, "price_f3": 0.20}  # dummy prices


def keychain_credentials() -> tuple[str, str]:
    info = subprocess.run(
        ["security", "find-generic-password", "-s", "ha-plenitude"], capture_output=True, text=True, check=True
    ).stdout
    email = re.search(r'"acct"<blob>="([^"]*)"', info).group(1)
    password = subprocess.run(
        ["security", "find-generic-password", "-s", "ha-plenitude", "-w"], capture_output=True, text=True, check=True
    ).stdout.rstrip("\n")
    return email, password


@pytest.fixture
def network():
    """The test kit blocks sockets and DNS: lift the block for this test only."""
    pytest_socket._remove_restrictions()
    socket.getaddrinfo = plugins._real_getaddrinfo
    yield


@pytest.fixture
async def plain_sessions():
    """In the test kit the shared DNS resolver of Home Assistant belongs to another event loop: use plain
    aiohttp sessions with a threaded resolver here. The integration code is unchanged."""
    created: list[tuple[aiohttp.ClientSession, aiohttp.TCPConnector]] = []

    def factory(hass, *args, cookie_jar=None, **kwargs):
        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        session = aiohttp.ClientSession(cookie_jar=cookie_jar, connector=connector)
        created.append((session, connector))
        return session

    with (
        patch("custom_components.plenitude.coordinator.async_create_clientsession", factory),
        patch("custom_components.plenitude.config_flow.async_create_clientsession", factory),
    ):
        yield
    # The config flow detaches its session (as it must with the shared connector of Home Assistant): here the
    # connectors are our own, so close both.
    for session, connector in created:
        if not session.closed:
            await session.close()
        await connector.close()


def check(condition: bool, message: str) -> None:
    """Like assert, but the failure shows only the message: pytest would print the compared values."""
    __tracebackhide__ = True
    if not condition:
        pytest.fail(message, pytrace=False)


def close(a: float, b: float, rel: float = 1e-6) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-5)


@pytest.fixture
def expected_lingering_timers() -> bool:
    return True


async def rows(hass: HomeAssistant, ids: set[str]) -> dict[str, list[dict]]:
    await async_wait_recording_done(hass)
    return await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2020, 1, 1, tzinfo=UTC),
        None,
        ids,
        "hour",
        None,
        {"state", "sum"},
    )


def local_day(row: dict) -> date:
    return datetime.fromtimestamp(row["start"], ROME).date()


def ranges(days: list[date]) -> str:
    """Compact list of dates: 01/02-09/02, 15/03."""
    parts, start, prev = [], None, None
    for day in sorted(days):
        if start is None:
            start = prev = day
        elif day == prev + timedelta(days=1):
            prev = day
        else:
            parts.append(f"{start:%d/%m}" if start == prev else f"{start:%d/%m}-{prev:%d/%m}")
            start = prev = day
    if start is not None:
        parts.append(f"{start:%d/%m}" if start == prev else f"{start:%d/%m}-{prev:%d/%m}")
    return ", ".join(parts) or "nessuno"


async def test_live(hass: HomeAssistant, network, plain_sessions) -> None:
    email, password = keychain_credentials()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"email": email, "password": password})
    if result["type"] is FlowResultType.FORM and result["step_id"] == "supply":
        options = result["data_schema"].schema["supply"].config["options"]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"supply": options[0]["value"]})
    check(result["type"] is FlowResultType.CREATE_ENTRY, f"configurazione non riuscita: {result.get('errors')}")
    print("\nConfigurazione guidata: login riuscito, voce creata")

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options=PRICES)
    started = datetime.now()
    await hass.async_block_till_done(wait_background_tasks=True)
    coordinator = entry.runtime_data
    check(coordinator.last_update_success, f"primo import non riuscito: {coordinator.last_exception}")
    print(f"Primo import: {(datetime.now() - started).seconds} s")

    ids = {coordinator.energy_id, coordinator.cost_id, *(coordinator.band_id(b) for b in BANDS)}
    ids |= {coordinator.category_id(slug) for slug in CATEGORIES.values()}
    stats = await rows(hass, ids)
    energy = stats[coordinator.energy_id]
    days = sorted({local_day(r) for r in energy})
    missing = [d for d in (days[0] + timedelta(days=i) for i in range((days[-1] - days[0]).days)) if d not in days]
    print(f"Ore importate: {len(energy)}; giorni: {len(days)}, dal {days[0]:%d/%m/%Y} al {days[-1]:%d/%m/%Y}")
    print(f"Giorni mancanti nel periodo: {len(missing)} ({ranges(missing)})")

    total = 0.0
    for row in energy:
        total += row["state"]
        check(close(row["sum"], total), "somma cumulativa del consumo incoerente")
    print("Somma cumulativa del consumo: coerente ora per ora")
    band_total = sum(stats[coordinator.band_id(b)][-1]["sum"] for b in BANDS)
    check(close(band_total, total), "F1 + F2 + F3 diverso dal consumo")
    print("F1 + F2 + F3 = consumo: verificato")
    expected_cost = sum(r["state"] * price_of(band(datetime.fromtimestamp(r["start"], ROME)), PRICES) for r in energy)
    check(close(stats[coordinator.cost_id][-1]["sum"], expected_cost), "costo diverso da kWh x prezzo")
    print("Costo = kWh x prezzo della fascia (prezzi di prova): verificato")
    categories = [stats.get(coordinator.category_id(slug), []) for slug in CATEGORIES.values()]
    category_days = sorted({local_day(r) for c in categories for r in c})
    category_total = sum(c[-1]["sum"] for c in categories if c)
    print(
        f"Categorie: {sum(1 for c in categories if c)} con dati, {len(category_days)} giorni; "
        f"somma delle categorie vs consumo misurato: {100 * (category_total / total - 1):+.2f}%"
    )

    # Our bands, from the ARERA calendar, against the portal's monthly billing figures per band.
    ours: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for name in BANDS:
        for row in stats[coordinator.band_id(name)]:
            moment = datetime.fromtimestamp(row["start"], ROME)
            ours[(moment.year, moment.month)][name] += row["state"]
    portal = await coordinator.client.get_monthly_by_band(coordinator._account)
    print("Confronto mensile con le fasce di Plenitude (Δ totale in %, Δ quota di ogni fascia in punti):")
    for item in (portal[0].get("consumptions") if portal else []) or []:
        key = (int(item["year"]), int(item["numericalMonth"]))
        if key not in ours:
            continue
        theirs = {b: float(item.get(f"consumptions{b.upper()}") or 0) for b in BANDS}
        mine = ours[key]
        mine_total, theirs_total = sum(mine.values()), sum(theirs.values())
        if not theirs_total or not mine_total:
            continue
        month_missing = sum(1 for d in missing if (d.year, d.month) == key)
        shares = ", ".join(f"{b.upper()} {100 * (mine[b] / mine_total - theirs[b] / theirs_total):+.1f}" for b in BANDS)
        flags = (" parziale" if item.get("isPartial") else "") + (
            f" ({month_missing} gg mancanti)" if month_missing else ""
        )
        print(f"  {key[0]}-{key[1]:02d}: totale {100 * (mine_total / theirs_total - 1):+.1f}%, {shares}{flags}")

    # A second sync right away must not import the history again.
    requested: list[date] = []
    original = coordinator.client.get_day

    async def counting(account, supply, day):
        requested.append(day)
        return await original(account, supply, day)

    coordinator.client.get_day = counting
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    print(f"Seconda sincronizzazione: {len(requested)} giorni chiesti ({ranges(requested)})")
    check(len(requested) <= 20, "la seconda sincronizzazione ha chiesto troppi giorni")

    # Removal closes the 30-day login: otherwise every run would keep a place among the sessions of the account.
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    check(await session_store(hass, entry.entry_id).async_load() is None, "sessione non cancellata alla rimozione")
    print("Rimozione: login chiuso, sessione cancellata")
