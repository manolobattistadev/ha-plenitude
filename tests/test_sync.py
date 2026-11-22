"""Import of the statistics: first import, late days, transient failures, price changes."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_metadata, statistics_during_period
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.plenitude.api import CATEGORIES, ROME, PlenitudeAuthError, PlenitudeSessionExpired
from custom_components.plenitude.bands import BANDS, PRICE_MODE, band, price_of
from custom_components.plenitude.const import CONF_SUPPLY, DOMAIN, statistic_prefix, supply_key

from .conftest import KWH_PER_HOUR, POD, FakeClient, FakePortal, day_hours

PREFIX = statistic_prefix(supply_key(POD))
ENERGY = f"{PREFIX}_consumo"
COST = f"{PREFIX}_costo"
THREE_BANDS = {PRICE_MODE: "three", "price_f1": 0.30, "price_f2": 0.25, "price_f3": 0.20}


def days(first: date, last: date) -> set[date]:
    return {first + timedelta(days=i) for i in range((last - first).days + 1)}


async def rows(hass: HomeAssistant, statistic_id: str) -> list[dict]:
    await async_wait_recording_done(hass)
    stats = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2020, 1, 1, tzinfo=UTC),
        None,
        {statistic_id},
        "hour",
        None,
        {"state", "sum"},
    )
    return stats.get(statistic_id, [])


def sensor(hass: HomeAssistant, key: str):
    """State of a sensor found by unique id (the entity id depends on the language)."""
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{supply_key(POD)}_{key}")
    return hass.states.get(entity_id) if entity_id else None


def assert_consistent(data: list[dict]) -> None:
    """The cumulative sum must grow exactly by each state: no jumps, no steps back."""
    total = 0.0
    for row in data:
        total += row["state"]
        assert row["sum"] == pytest.approx(total, abs=1e-6)


def cost(name: str, kind: str, amount: float) -> ConfigSubentryData:
    return {
        "data": {"name": name, "kind": kind, "amount": amount},
        "subentry_type": "cost",
        "title": name,
        "unique_id": None,
    }


async def setup(hass: HomeAssistant, options: dict, costs: tuple[ConfigSubentryData, ...] = ()) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Plenitude luce",
        unique_id=supply_key(POD),
        data={"email": "test@example.com", "password": "x", CONF_SUPPLY: supply_key(POD)},
        options=options,
        subentries_data=costs,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    # Imports are queued in the recorder: wait until they are written, as hours pass between real syncs.
    await async_wait_recording_done(hass)
    return entry


async def test_first_import(recorder_mock, hass: HomeAssistant, freezer, fake_client: FakePortal) -> None:
    freezer.move_to(datetime(2026, 11, 22, 12, tzinfo=ROME))
    gap = date(2026, 11, 12)
    fake_client.days = days(date(2026, 10, 20), date(2026, 11, 20)) - {gap}

    await setup(hass, THREE_BANDS)

    energy = await rows(hass, ENERGY)
    hours = sum(len(day_hours(d)) for d in fake_client.days)
    assert len(energy) == hours == 31 * 24 + 1  # 25 October has 25 hours
    assert_consistent(energy)
    assert energy[-1]["sum"] == pytest.approx(hours * KWH_PER_HOUR)
    # The walk back stopped after the run of empty days.
    assert min(fake_client.day_requests) == date(2026, 10, 20) - timedelta(days=31)

    # The bands split every hour without losing anything, F1 only on working days.
    band_rows = {name: await rows(hass, f"{PREFIX}_{name}") for name in BANDS}
    assert sum(band_rows[name][-1]["sum"] for name in BANDS) == pytest.approx(energy[-1]["sum"])
    by_start = {name: {r["start"]: r["state"] for r in band_rows[name]} for name in BANDS}
    monday_10 = datetime(2026, 11, 2, 10, tzinfo=ROME).timestamp()
    sunday_10 = datetime(2026, 11, 1, 10, tzinfo=ROME).timestamp()
    assert by_start["f1"][monday_10] == KWH_PER_HOUR and by_start["f3"][monday_10] == 0
    assert by_start["f3"][sunday_10] == KWH_PER_HOUR and by_start["f1"][sunday_10] == 0

    cost = await rows(hass, COST)
    expected = sum(KWH_PER_HOUR * price_of(band(r.start), THREE_BANDS) for d in fake_client.days for r in day_hours(d))
    assert cost[-1]["sum"] == pytest.approx(expected)

    # Categories: one row per day, at local midnight, summing to the measured total.
    categories = [await rows(hass, f"{PREFIX}_cat_{slug}") for slug in CATEGORIES.values()]
    assert all(len(c) == len(fake_client.days) for c in categories)
    assert datetime.fromtimestamp(categories[0][0]["start"], ROME).time() == time(0)
    assert sum(c[-1]["sum"] for c in categories) == pytest.approx(energy[-1]["sum"])

    state = sensor(hass, "consumo_ultimo_giorno")
    assert state is not None and float(state.state) == pytest.approx(24 * KWH_PER_HOUR)
    assert sensor(hass, "ultimo_giorno").state == "2026-11-20"


async def test_late_day_and_transient_failure(
    recorder_mock, hass: HomeAssistant, freezer, fake_client: FakePortal
) -> None:
    freezer.move_to(datetime(2026, 11, 22, 12, tzinfo=ROME))
    gap = date(2026, 11, 12)
    fake_client.days = days(date(2026, 10, 20), date(2026, 11, 20)) - {gap}
    entry = await setup(hass, THREE_BANDS)

    # Next day: two more days, the missing day has arrived, and one stored day is not returned this time.
    freezer.move_to(datetime(2026, 11, 23, 12, tzinfo=ROME))
    fake_client.days |= {gap, date(2026, 11, 21)}
    fake_client.hidden = {date(2026, 11, 15)}
    fake_client.day_requests.clear()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    assert min(fake_client.day_requests) == gap  # rechecked although older than the last imported day
    energy = await rows(hass, ENERGY)
    assert_consistent(energy)
    hours = sum(len(day_hours(d)) for d in fake_client.days)
    assert len(energy) == hours
    assert energy[-1]["sum"] == pytest.approx(hours * KWH_PER_HOUR)
    for name in BANDS:
        assert_consistent(await rows(hass, f"{PREFIX}_{name}"))
    assert_consistent(await rows(hass, COST))
    for slug in CATEGORIES.values():
        category = await rows(hass, f"{PREFIX}_cat_{slug}")
        assert_consistent(category)
        assert len(category) == len(fake_client.days)

    # Same day again: nothing to fetch.
    fake_client.day_requests.clear()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    assert fake_client.day_requests == [date(2026, 11, 22)]


async def test_price_change_rebuilds_cost(recorder_mock, hass: HomeAssistant, freezer, fake_client: FakePortal) -> None:
    freezer.move_to(datetime(2026, 11, 22, 12, tzinfo=ROME))
    fake_client.days = days(date(2026, 11, 1), date(2026, 11, 20))
    entry = await setup(hass, {PRICE_MODE: "none"})
    assert await rows(hass, COST) == []
    assert sensor(hass, "costo_ultimo_giorno") is None

    hass.config_entries.async_update_entry(entry, options={PRICE_MODE: "single", "price": 0.4})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    energy = await rows(hass, ENERGY)
    cost = await rows(hass, COST)
    assert len(cost) == len(energy)
    assert_consistent(cost)
    assert cost[-1]["sum"] == pytest.approx(energy[-1]["sum"] * 0.4)
    state = sensor(hass, "costo_ultimo_giorno")
    assert state is not None and float(state.state) == pytest.approx(24 * KWH_PER_HOUR * 0.4)

    hass.config_entries.async_update_entry(entry, options={PRICE_MODE: "none"})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await rows(hass, COST) == []


async def test_info_for_the_cards(hass: HomeAssistant, hass_ws_client, fake_client: FakePortal) -> None:
    # Real time here: the access token of the websocket client expires 30 minutes after it is issued.
    last_day = datetime.now(ROME).date() - timedelta(days=2)
    fake_client.days = days(last_day - timedelta(days=19), last_day)
    costs = (cost("Quota fissa", "monthly", 10), cost("Oneri", "per_kwh", 0.05))
    entry = await setup(hass, THREE_BANDS, costs)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "plenitude/info"})
    reply = await client.receive_json()
    assert reply["success"]
    (info,) = reply["result"]["entries"]
    assert info["entry_id"] == entry.entry_id
    assert info["first_day"] == (last_day - timedelta(days=19)).isoformat()
    assert info["last_day"] == last_day.isoformat()
    assert info["prices"] == {"f1": 0.30, "f2": 0.25, "f3": 0.20}
    assert info["costs"] == [
        {"name": "Quota fissa", "kind": "monthly", "amount": 10.0},
        {"name": "Oneri", "kind": "per_kwh", "amount": 0.05},
    ]
    assert info["statistics"] == {
        "consumo": ENERGY,
        "f1": f"{PREFIX}_f1",
        "f2": f"{PREFIX}_f2",
        "f3": f"{PREFIX}_f3",
        "costo": COST,
    }
    assert [c["key"] for c in info["categories"]][-1] == "altro"
    assert POD not in str(reply)  # no customer identifiers towards the browser


async def test_cards_registered_with_the_frontend(hass: HomeAssistant) -> None:
    """With the frontend loaded the cards are served and added to every dashboard, with a cache-busting hash."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from custom_components.plenitude import _async_register_cards

    hass.config.components.add("frontend")
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
        await _async_register_cards(hass)
    (configs,) = hass.http.async_register_static_paths.call_args.args
    assert configs[0].url_path == "/plenitude_static" and configs[0].path.endswith("frontend")
    url = add_js.call_args.args[1]
    assert url.startswith("/plenitude_static/plenitude-cards.js?v=") and len(url.split("=")[1]) == 8


@pytest.mark.parametrize(
    ("language", "energy", "band_f1", "category"),
    [
        # Italian: the name sent by the (fake) portal; English: ours, by key.
        ("it", "Plenitude luce consumo", "Plenitude luce consumo F1", "Plenitude luce Comfort ambientale (stima)"),
        (
            "en",
            "Plenitude luce consumption",
            "Plenitude luce consumption F1",
            "Plenitude luce Heating and cooling (HVAC) (estimate)",
        ),
    ],
)
async def test_statistic_names_follow_the_server_language(
    recorder_mock, hass: HomeAssistant, freezer, fake_client: FakePortal, language, energy, band_f1, category
) -> None:
    freezer.move_to(datetime(2026, 11, 22, 12, tzinfo=ROME))
    hass.config.language = language
    fake_client.days = days(date(2026, 11, 18), date(2026, 11, 20))
    await setup(hass, THREE_BANDS)
    ids = {ENERGY, f"{PREFIX}_f1", f"{PREFIX}_cat_comfort_ambientale"}
    metadata = await get_instance(hass).async_add_executor_job(lambda: get_metadata(hass, statistic_ids=ids))
    names = {sid: meta["name"] for sid, (_, meta) in metadata.items()}
    assert names == {ENERGY: energy, f"{PREFIX}_f1": band_f1, f"{PREFIX}_cat_comfort_ambientale": category}


async def test_refused_login_asks_for_the_password(hass: HomeAssistant, fake_client: FakePortal) -> None:
    """Session over and password refused: the entry stops and Home Assistant starts the re-authentication."""
    with (
        patch.object(FakeClient, "has_portal_session", return_value=False),
        patch.object(FakeClient, "open_portal_session", side_effect=PlenitudeSessionExpired("expired")),
        patch.object(FakeClient, "login", side_effect=PlenitudeAuthError(403042, "Invalid LoginID")),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Plenitude luce",
            unique_id=supply_key(POD),
            data={"email": "test@example.com", "password": "x", CONF_SUPPLY: supply_key(POD)},
            options={PRICE_MODE: "none"},
        )
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "login_refused"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_network_error_retries_the_setup(hass: HomeAssistant, fake_client: FakePortal) -> None:
    with patch.object(FakeClient, "get_account", side_effect=TimeoutError()):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Plenitude luce",
            unique_id=supply_key(POD),
            data={"email": "test@example.com", "password": "x", CONF_SUPPLY: supply_key(POD)},
            options={PRICE_MODE: "none"},
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.error_reason_translation_key == "communication_error"


async def test_costs_per_kwh_follow_the_subentries(
    recorder_mock, hass: HomeAssistant, freezer, fake_client: FakePortal
) -> None:
    """Adding, editing and deleting a cost reloads the entry; costs per kWh rebuild the cost history."""
    freezer.move_to(datetime(2026, 11, 22, 12, tzinfo=ROME))
    fake_client.days = days(date(2026, 11, 10), date(2026, 11, 20))
    entry = await setup(hass, {PRICE_MODE: "none"})
    assert await rows(hass, COST) == []

    async def settle() -> None:
        await hass.async_block_till_done(wait_background_tasks=True)
        await async_wait_recording_done(hass)

    result = await hass.config_entries.subentries.async_init((entry.entry_id, "cost"), context={"source": "user"})
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Oneri", "kind": "per_kwh", "amount": 0.05}
    )
    await settle()
    energy = await rows(hass, ENERGY)
    cost = await rows(hass, COST)
    assert len(cost) == len(energy)
    assert_consistent(cost)
    assert cost[-1]["sum"] == pytest.approx(energy[-1]["sum"] * 0.05)
    state = sensor(hass, "costo_ultimo_giorno")  # created by the reload
    assert state is not None and float(state.state) == pytest.approx(24 * KWH_PER_HOUR * 0.05)

    # Prices and costs per kWh add up, hour by hour.
    hass.config_entries.async_update_entry(entry, options={PRICE_MODE: "single", "price": 0.2})
    await hass.config_entries.async_reload(entry.entry_id)  # what the options flow does
    await settle()
    assert (await rows(hass, COST))[-1]["sum"] == pytest.approx(energy[-1]["sum"] * 0.25)

    (subentry_id,) = entry.subentries
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Oneri", "kind": "per_kwh", "amount": 0.1}
    )
    await settle()
    assert (await rows(hass, COST))[-1]["sum"] == pytest.approx(energy[-1]["sum"] * 0.3)

    hass.config_entries.async_remove_subentry(entry, subentry_id)
    await settle()
    assert (await rows(hass, COST))[-1]["sum"] == pytest.approx(energy[-1]["sum"] * 0.2)
