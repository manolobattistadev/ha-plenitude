"""Fixtures: a fake Plenitude portal that serves synthetic days, no network."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch

import pytest

from custom_components.plenitude.api import (
    CATEGORIES,
    ROME,
    Account,
    DayConsumption,
    MonthConsumption,
    PlenitudeBadRequest,
    Reading,
    Supply,
)

pytest_plugins = "pytest_homeassistant_custom_component"

POD = "IT001E99999999"  # fake
KWH_PER_HOUR = 0.5


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    # The recorder must be created before hass: this fixture asks for it first.
    yield


def day_hours(day: date) -> list[Reading]:
    start = datetime.combine(day, time.min, ROME).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, ROME).astimezone(UTC)
    count = (end - start) // timedelta(hours=1)
    return [Reading(start=(start + i * timedelta(hours=1)).astimezone(ROME), kwh=KWH_PER_HOUR) for i in range(count)]


@dataclass
class FakePortal:
    """Days with data; ``hidden`` days have data but are not returned this time (transient failure)."""

    days: set[date] = field(default_factory=set)
    hidden: set[date] = field(default_factory=set)
    day_requests: list[date] = field(default_factory=list)
    logins: int = 0
    logouts: int = 0
    refused: set[date] = field(default_factory=set)
    refused_months: set[tuple[int, int]] = field(default_factory=set)

    def available(self, day: date) -> bool:
        return day in self.days and day not in self.hidden


class FakeClient:
    def __init__(self, portal: FakePortal) -> None:
        self.portal = portal
        self.login_token: str | None = "fake"
        self.login_token_expires_at: datetime | None = None

    def has_portal_session(self) -> bool:
        return True

    async def open_portal_session(self) -> int:
        return 300

    async def login(self, email, password, session_expiration=3000):
        self.portal.logins += 1
        return {}

    async def logout(self, account=None) -> None:
        self.portal.logouts += 1

    def export_state(self) -> dict:
        return {}

    def import_state(self, state) -> None:
        return None

    async def get_account(self) -> Account:
        return Account(client_code="C", account_code="A")

    async def get_supplies(self, account) -> list[Supply]:
        return [Supply(kind="LUCE", pod=POD, pdr=None, contract_id="1", house_id="2", address="Via di prova 1")]

    async def get_day(self, account, supply, day: date) -> DayConsumption:
        self.portal.day_requests.append(day)
        if day in self.portal.refused:
            raise PlenitudeBadRequest("/api/profilo-energetico-services/…/analysis/consumptions: HTTP 400")
        if not self.portal.available(day):
            return DayConsumption(day=day, status="NO_DATA", hours=[], quarter_hours=[])
        return DayConsumption(day=day, status="DATA", hours=day_hours(day), quarter_hours=[])

    async def get_month(self, account, supply, year: int, month: int) -> MonthConsumption:
        if (year, month) in self.portal.refused_months:
            raise PlenitudeBadRequest("/api/profilo-energetico-services/…/analysis/consumptions: HTTP 400")
        days: dict[str, dict[date, float]] = {slug: {} for slug in CATEGORIES.values()}
        for day in self.portal.days:
            if (day.year, day.month) == (year, month) and self.portal.available(day):
                per_category = len(day_hours(day)) * KWH_PER_HOUR / len(CATEGORIES)
                for slug in CATEGORIES.values():
                    days[slug][day] = per_category
        names = {slug: slug.replace("_", " ").capitalize() for slug in CATEGORIES.values()}
        return MonthConsumption(year=year, month=month, status="DATA", days=days, names=names)


@pytest.fixture
def portal() -> FakePortal:
    return FakePortal()


@pytest.fixture
def fake_client(portal: FakePortal):
    with (
        patch("custom_components.plenitude.coordinator.PlenitudeClient", lambda session: FakeClient(portal)),
        patch("custom_components.plenitude.coordinator.REQUEST_PAUSE", 0),
    ):
        yield portal
