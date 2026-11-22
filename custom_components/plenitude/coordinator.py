"""Coordinator: keeps the Plenitude session alive and imports the consumption as long-term statistics.

Statistics (``{prefix}`` is ``plenitude:luce_<key of the supply>``), all with a cumulative ``sum``:

- ``{prefix}_consumo``: measured kWh per hour;
- ``{prefix}_f1``, ``_f2``, ``_f3``: the same hours split by ARERA band (0 in the hours of other bands);
- ``{prefix}_costo``: EUR per hour, kWh x price of the band, only if a price is configured;
- ``{prefix}_cat_<category>``: estimated kWh per day (one value at local midnight), as the portal gives them.

Data arrive about two days late, so they are imported with their own timestamps instead of being sensor states.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .api import (
    CATEGORIES,
    ROME,
    Account,
    DayConsumption,
    MonthConsumption,
    PlenitudeAuthError,
    PlenitudeClient,
    PlenitudeError,
    PlenitudeSessionExpired,
    Supply,
)
from .bands import BANDS, PRICE_MODE, PRICE_NONE, band, price_of, price_signature
from .const import (
    CATEGORY_PREFIX,
    CONF_SUPPLY,
    DOMAIN,
    HISTORY_EMPTY_RUN,
    HISTORY_MAX_DAYS,
    RECHECK_DAYS,
    REQUEST_PAUSE,
    SESSION_EXPIRATION,
    STAT_COST,
    STAT_ENERGY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
    statistic_prefix,
    supply_key,
)

_LOGGER = logging.getLogger(__name__)

CURRENCY = "EUR"
# Labels used until the portal has sent its own (they are the same on 2026-11-22).
DEFAULT_CATEGORY_NAMES = {
    "refrigerare": "Refrigerare",
    "standby": "Standby",
    "lavare": "Lavare",
    "cucinare": "Cucinare",
    "comfort_ambientale": "Comfort ambientale (HVAC)",
    "elettronica_luci": "Elettronica e luci",
    "altro": "Altro",
    "ricarica_elettrica": "Ricarica elettrica",
}

type PlenitudeConfigEntry = ConfigEntry[PlenitudeCoordinator]


@dataclass
class PlenitudeData:
    """What the sensors show: the last day with data."""

    last_day: date | None = None
    last_day_kwh: float | None = None
    last_day_cost: float | None = None


def _days(first: date, last: date) -> Iterator[date]:
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def _midnight_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, ROME).astimezone(timezone.utc)


def _local_day(moment: datetime) -> date:
    return moment.astimezone(ROME).date()


class PlenitudeCoordinator(DataUpdateCoordinator[PlenitudeData]):
    """One supply of one Plenitude account."""

    config_entry: PlenitudeConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PlenitudeConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        # A session of its own: the portal session lives in its cookies.
        self.client = PlenitudeClient(async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar()))
        # Tokens and cookies are secrets: the file is written readable by the owner only.
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}", private=True
        )
        self._state: dict[str, Any] = {}
        self._account: Account | None = None
        self.supply: Supply | None = None
        self.prefix = statistic_prefix(entry.data[CONF_SUPPLY])
        self.category_names = dict(DEFAULT_CATEGORY_NAMES)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ statistic ids

    def statistic_id(self, key: str) -> str:
        return f"{self.prefix}_{key}"

    @property
    def energy_id(self) -> str:
        return self.statistic_id(STAT_ENERGY)

    @property
    def cost_id(self) -> str:
        return self.statistic_id(STAT_COST)

    def band_id(self, band_name: str) -> str:
        return self.statistic_id(band_name)

    def category_id(self, slug: str) -> str:
        return self.statistic_id(f"{CATEGORY_PREFIX}{slug}")

    @property
    def has_price(self) -> bool:
        return self.config_entry.options.get(PRICE_MODE, PRICE_NONE) != PRICE_NONE

    def _metadata(self, statistic_id: str) -> StatisticMetaData:
        title = self.config_entry.title
        unit: str | None = UnitOfEnergy.KILO_WATT_HOUR
        unit_class: str | None = EnergyConverter.UNIT_CLASS
        key = statistic_id.removeprefix(f"{self.prefix}_")
        if key == STAT_ENERGY:
            label = "consumo"
        elif key == STAT_COST:
            label, unit, unit_class = "costo", CURRENCY, None
        elif key in BANDS:
            label = f"consumo {key.upper()}"
        else:
            slug = key.removeprefix(CATEGORY_PREFIX)
            label = f"{self.category_names.get(slug, slug)} (stima)"
        return StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"{title} {label}",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=unit_class,
            unit_of_measurement=unit,
        )

    # ------------------------------------------------------------------ session

    async def async_prepare(self) -> None:
        """Load the saved session and find the supply. Called by the setup of the config entry."""
        self._state = await self._store.async_load() or {}
        self.client.import_state(self._state.get("session") or {})
        await self._ensure_supply()

    async def _save(self) -> None:
        self._state["session"] = self.client.export_state()
        await self._store.async_save(self._state)

    async def _renew(self) -> None:
        """Open a new portal session: without the password while Gigya allows it, with it otherwise."""
        try:
            try:
                await self.client.open_portal_session()
                _LOGGER.debug("Portal session renewed without the password")
            except PlenitudeSessionExpired:
                data = self.config_entry.data
                await self.client.login(data[CONF_EMAIL], data[CONF_PASSWORD], SESSION_EXPIRATION)
                _LOGGER.debug("New login with the password")
        except PlenitudeAuthError as err:
            # Gigya codes 401xxx and 403xxx: credentials refused, CAPTCHA, locked account. Asking the user is
            # the only way out; anything else (5xxxxx) is temporary.
            if err.code // 1000 in (401, 403):
                raise ConfigEntryAuthFailed(f"Plenitude login refused: {err}") from err
            raise UpdateFailed(f"Plenitude login failed: {err}") from err
        await self._save()

    async def _call[T](self, request: Callable[[], Awaitable[T]]) -> T:
        """Run a request; if the session is over, renew it once and try again."""
        try:
            return await request()
        except PlenitudeSessionExpired:
            await self._renew()
            return await request()

    async def _ensure_supply(self) -> None:
        if self.supply is not None:
            return
        if not self.client.has_portal_session():
            await self._renew()
        account = await self._call(self.client.get_account)
        supplies = await self._call(lambda: self.client.get_supplies(account))
        wanted = self.config_entry.data[CONF_SUPPLY]
        for supply in supplies:
            if supply.pod and supply_key(supply.pod) == wanted:
                if not supply.contract_id or not supply.house_id:
                    raise UpdateFailed("The consumption analysis is not available for the configured supply")
                self._account, self.supply = account, supply
                return
        raise UpdateFailed("The configured supply is no longer in the Plenitude account")

    async def _get_day(self, day: date) -> DayConsumption:
        assert self._account and self.supply
        return await self._call(lambda: self.client.get_day(self._account, self.supply, day))

    async def _get_month(self, year: int, month: int) -> MonthConsumption:
        assert self._account and self.supply
        return await self._call(lambda: self.client.get_month(self._account, self.supply, year, month))

    # ----------------------------------------------------------------- recorder

    async def _recorder[T](self, function: Callable[..., T], *args: Any) -> T:
        return await get_instance(self.hass).async_add_executor_job(function, self.hass, *args)

    async def _stored_states(self, start: datetime, ids: set[str]) -> dict[str, dict[datetime, float]]:
        """Hourly ``state`` already in the recorder from ``start`` on, per statistic id."""
        stats = await self._recorder(statistics_during_period, start, None, ids, "hour", None, {"state"})
        return {
            sid: {
                dt_util.utc_from_timestamp(row["start"]): float(row["state"])
                for row in rows
                if row.get("state") is not None
            }
            for sid, rows in stats.items()
        }

    async def _sums_before(self, moment: datetime, ids: set[str]) -> dict[str, float]:
        """Cumulative ``sum`` of the last row before ``moment``, per statistic id (0 if there is none).

        Looks back a little first and further only for the ids not found: there can be gaps of days
        (missing data) and the band statistics have no rows on some days.
        """
        found: dict[str, float] = {}
        pending = set(ids)
        for days_back in (4, 45, 400, 4000):
            stats = await self._recorder(
                statistics_during_period, moment - timedelta(days=days_back), moment, pending, "hour", None, {"sum"}
            )
            for sid, rows in stats.items():
                if rows:
                    found[sid] = float(rows[-1].get("sum") or 0.0)
                    pending.discard(sid)
            if not pending:
                break
        return {sid: found.get(sid, 0.0) for sid in ids}

    def _clear(self, ids: list[str]) -> None:
        get_instance(self.hass).async_clear_statistics(ids)

    # --------------------------------------------------------------------- sync

    async def _async_update_data(self) -> PlenitudeData:
        async with self._lock:
            try:
                return await self._sync()
            except (PlenitudeError, aiohttp.ClientError, TimeoutError) as err:
                raise UpdateFailed(f"Plenitude: {err}") from err

    async def _sync(self) -> PlenitudeData:
        await self._ensure_supply()
        today = dt_util.now(ROME).date()
        yesterday = today - timedelta(days=1)
        last = await self._recorder(get_last_statistics, 1, self.energy_id, True, {"sum"})
        first_import = not last.get(self.energy_id)

        if first_import:
            days = await self._fetch_history(yesterday)
            if not days:
                _LOGGER.info("Plenitude: no consumption data available yet")
                return PlenitudeData()
            window_start = days[0].day
        else:
            last_day = _local_day(dt_util.utc_from_timestamp(last[self.energy_id][0]["start"]))
            check_from = last_day + timedelta(days=1)
            if self._state.get("gaps_checked") != today.isoformat():
                # Once a day, also ask again the recent days without data, in case they arrived late.
                check_from = min(check_from, today - timedelta(days=RECHECK_DAYS))
            present = await self._stored_states(_midnight_utc(check_from), {self.energy_id})
            present_days = {_local_day(moment) for moment in present.get(self.energy_id, {})}
            missing = [day for day in _days(check_from, yesterday) if day not in present_days]
            if not missing:
                await self._maybe_rebuild_cost()
                self._state["gaps_checked"] = today.isoformat()
                await self._save()
                return await self._summary()
            window_start = missing[0]
            days = []
            for day in _days(window_start, yesterday):
                days.append(await self._get_day(day))

        months: list[MonthConsumption] = []
        if any(day.hours for day in days):  # categories only follow new measured days
            for year, month in sorted({(day.year, day.month) for day in _days(window_start, yesterday)}):
                months.append(await self._get_month(year, month))
                if first_import:
                    await asyncio.sleep(REQUEST_PAUSE)

        result = await self._import(window_start, days, months, first_import)
        self._state["gaps_checked"] = today.isoformat()
        await self._save()
        return result

    async def _fetch_history(self, yesterday: date) -> list[DayConsumption]:
        """First import: walk back from yesterday until a long run of days without data."""
        days: list[DayConsumption] = []
        empty_run = 0
        for offset in range(HISTORY_MAX_DAYS):
            day = yesterday - timedelta(days=offset)
            result = await self._get_day(day)
            if result.hours:
                days.append(result)
                empty_run = 0
            else:
                empty_run += 1
                if empty_run >= HISTORY_EMPTY_RUN:
                    break
            if offset and offset % 30 == 0:
                _LOGGER.info("Plenitude: first import, %d days read, %d with data", offset + 1, len(days))
            await asyncio.sleep(REQUEST_PAUSE)
        days.reverse()
        return days

    async def _import(
        self, window_start: date, days: list[DayConsumption], months: list[MonthConsumption], first_import: bool
    ) -> PlenitudeData:
        """Write the statistics from ``window_start`` on, continuing the sums of what is already there."""
        start = _midnight_utc(window_start)
        category_slugs = set(CATEGORIES.values())
        for month in months:
            for slug, name in month.names.items():
                if slug != "totale":
                    self.category_names[slug] = name
                    category_slugs.add(slug)

        # Hours from the portal; for days it did not give back now, what is already stored is kept, so that the
        # rewritten sums stay consistent with the rows that are not rewritten.
        stored = {} if first_import else await self._stored_states(
            start, {self.energy_id, *(self.category_id(slug) for slug in category_slugs)}
        )
        energy: dict[datetime, float] = {}
        fetched_days = set()
        for day in days:
            if day.hours:
                fetched_days.add(day.day)
                for reading in day.hours:
                    energy[reading.start.astimezone(timezone.utc)] = reading.kwh
        for moment, kwh in stored.get(self.energy_id, {}).items():
            if _local_day(moment) not in fetched_days:
                energy.setdefault(moment, kwh)
        if not energy:
            # Nothing new (usually: yesterday is not available yet), but the prices may have changed.
            await self._maybe_rebuild_cost()
            return await self._summary()
        last_energy_day = _local_day(max(energy))

        # Categories: one value per day, only up to the last complete day of measured data (later values may
        # still be provisional).
        categories: dict[str, dict[datetime, float]] = {}
        for month in months:
            for slug, values in month.days.items():
                if slug == "totale":
                    continue
                for day, kwh in values.items():
                    if window_start <= day <= last_energy_day:
                        categories.setdefault(slug, {})[_midnight_utc(day)] = kwh
        for slug in category_slugs:
            fetched = {_local_day(moment) for moment in categories.get(slug, {})}
            for moment, kwh in stored.get(self.category_id(slug), {}).items():
                if _local_day(moment) not in fetched:
                    categories.setdefault(slug, {}).setdefault(moment, kwh)

        signature = price_signature(self.config_entry.options)
        rebuild_cost = not first_import and self._state.get("price_signature") != signature
        ids = {self.energy_id, *(self.band_id(name) for name in BANDS)}
        ids |= {self.category_id(slug) for slug in categories}
        if self.has_price and not rebuild_cost:
            ids.add(self.cost_id)
        sums = {sid: 0.0 for sid in ids} if first_import else await self._sums_before(start, ids)
        rows: dict[str, list[StatisticData]] = {sid: [] for sid in ids}

        def add(sid: str, moment: datetime, value: float) -> None:
            sums[sid] += value
            rows[sid].append(StatisticData(start=moment, state=round(value, 6), sum=round(sums[sid], 6)))

        options = self.config_entry.options
        for moment, kwh in sorted(energy.items()):
            hour_band = band(moment.astimezone(ROME))
            add(self.energy_id, moment, kwh)
            for name in BANDS:
                add(self.band_id(name), moment, kwh if name == hour_band else 0.0)
            if self.cost_id in ids:
                add(self.cost_id, moment, kwh * (price_of(hour_band, options) or 0.0))
        for slug, series in categories.items():
            for moment, kwh in sorted(series.items()):
                add(self.category_id(slug), moment, kwh)

        for sid, data in rows.items():
            if data:
                async_add_external_statistics(self.hass, self._metadata(sid), data)
        if rebuild_cost:
            await self._rebuild_cost(energy)
        self._state["price_signature"] = signature
        _LOGGER.debug("Plenitude: imported %d hours from %s", len(rows[self.energy_id]), window_start)

        return self._day_summary(last_energy_day, energy)

    async def _maybe_rebuild_cost(self) -> None:
        if self._state.get("price_signature") != price_signature(self.config_entry.options):
            await self._rebuild_cost({})
            self._state["price_signature"] = price_signature(self.config_entry.options)

    async def _rebuild_cost(self, recent: dict[datetime, float]) -> None:
        """The price changed: rewrite the whole cost history from the stored hourly consumption."""
        self._clear([self.cost_id])
        if not self.has_price:
            _LOGGER.info("Plenitude: no price configured, cost statistic removed")
            return
        stored = await self._stored_states(datetime(2000, 1, 1, tzinfo=timezone.utc), {self.energy_id})
        energy = {**stored.get(self.energy_id, {}), **recent}
        options = self.config_entry.options
        total = 0.0
        data: list[StatisticData] = []
        for moment, kwh in sorted(energy.items()):
            value = kwh * (price_of(band(moment.astimezone(ROME)), options) or 0.0)
            total += value
            data.append(StatisticData(start=moment, state=round(value, 6), sum=round(total, 6)))
        if data:
            async_add_external_statistics(self.hass, self._metadata(self.cost_id), data)
        _LOGGER.info("Plenitude: cost history rebuilt with the new prices (%d hours)", len(data))

    async def _summary(self) -> PlenitudeData:
        """Last day with data, read back from the recorder (after a restart with nothing new)."""
        last = await self._recorder(get_last_statistics, 1, self.energy_id, True, {"sum"})
        if not last.get(self.energy_id):
            return PlenitudeData()
        day = _local_day(dt_util.utc_from_timestamp(last[self.energy_id][0]["start"]))
        hours = (await self._stored_states(_midnight_utc(day), {self.energy_id})).get(self.energy_id, {})
        return self._day_summary(day, hours)

    def _day_summary(self, day: date, energy: dict[datetime, float]) -> PlenitudeData:
        """Totals of ``day``. The cost comes from the current prices, not from the cost statistic, which may
        still be queued in the recorder right after a price change."""
        hours = {moment: kwh for moment, kwh in energy.items() if _local_day(moment) == day}
        cost = None
        if self.has_price:
            options = self.config_entry.options
            cost = sum(kwh * (price_of(band(m.astimezone(ROME)), options) or 0.0) for m, kwh in hours.items())
        return PlenitudeData(
            last_day=day,
            last_day_kwh=round(sum(hours.values()), 3),
            last_day_cost=round(cost, 2) if cost is not None else None,
        )
