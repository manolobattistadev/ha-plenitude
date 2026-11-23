"""Identity of the client towards the customer area (User-Agent and headers)."""

import logging
import re
from collections.abc import Iterator
from datetime import date, timedelta
from http.cookies import SimpleCookie
from types import SimpleNamespace

import aiohttp
import pytest
from yarl import URL

from custom_components.plenitude.api import (
    FIREFOX_DAYS_PER_VERSION,
    FIREFOX_VERSION,
    FIREFOX_VERSION_DATE,
    SAME_ORIGIN,
    SAME_SITE,
    PlenitudeClient,
    _trace,
    user_agent,
)


def firefox_version(agent: str) -> int:
    match = re.fullmatch(r"Mozilla/5\.0 \(.+; rv:(\d+)\.0\) Gecko/20100101 Firefox/(\d+)\.0", agent)
    assert match, agent
    assert match.group(1) == match.group(2), "rv and Firefox version must agree"
    return int(match.group(1))


def test_user_agent_starts_from_the_measured_firefox() -> None:
    assert firefox_version(user_agent(FIREFOX_VERSION_DATE)) == FIREFOX_VERSION
    # Before the reference day (clock behind) it does not go back.
    assert firefox_version(user_agent(FIREFOX_VERSION_DATE - timedelta(days=400))) == FIREFOX_VERSION


def test_user_agent_advances_one_version_per_period() -> None:
    step = timedelta(days=FIREFOX_DAYS_PER_VERSION)
    assert firefox_version(user_agent(FIREFOX_VERSION_DATE + step - timedelta(days=1))) == FIREFOX_VERSION
    assert firefox_version(user_agent(FIREFOX_VERSION_DATE + step)) == FIREFOX_VERSION + 1
    # Never ahead of the real Firefox, which ships a version about every four weeks.
    a_year_later = FIREFOX_VERSION_DATE + timedelta(days=365)
    assert firefox_version(user_agent(a_year_later)) <= FIREFOX_VERSION + 365 // 28


def test_user_agent_of_today_is_firefox() -> None:
    assert firefox_version(user_agent()) == firefox_version(user_agent(date.today()))
    assert firefox_version(user_agent()) >= FIREFOX_VERSION


def test_headers_follow_the_browser() -> None:
    get = PlenitudeClient._headers(SAME_ORIGIN)
    post = PlenitudeClient._headers(SAME_ORIGIN, "POST")
    gigya = PlenitudeClient._headers(SAME_SITE, "POST")

    assert "Origin" not in get, "a browser sends no Origin on same-origin GET requests"
    assert post["Origin"] == gigya["Origin"] == "https://eniplenitude.com"
    assert get["Sec-Fetch-Site"] == "same-origin" and gigya["Sec-Fetch-Site"] == "same-site"
    assert {get["Sec-Fetch-Mode"], get["Sec-Fetch-Dest"]} == {"cors", "empty"}
    # Towards another origin Firefox sends only the origin of the page as Referer.
    assert gigya["Referer"] == "https://eniplenitude.com/"
    assert "Chrome" not in get["User-Agent"]

    page = PlenitudeClient._page_headers()
    assert page["Sec-Fetch-Mode"] == "navigate" and page["Sec-Fetch-Site"] == "none"
    assert "Origin" not in page and "Referer" not in page


def test_extra_headers_override() -> None:
    headers = PlenitudeClient._headers(
        SAME_ORIGIN, extra={"JWT": "token", "Referer": "https://eniplenitude.com/my-eni"}
    )
    assert headers["JWT"] == "token"
    assert headers["Referer"] == "https://eniplenitude.com/my-eni"


class Records(logging.Handler):
    """Collects the records of the client's logger (works also with ``-p no:logging``)."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    @property
    def messages(self) -> list[str]:
        return [record.getMessage() for record in self.records]


@pytest.fixture
def records() -> Iterator[Records]:
    logger = logging.getLogger("custom_components.plenitude.api")
    handler, level = Records(), logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield handler
    logger.removeHandler(handler)
    logger.setLevel(level)


def fake_response(path: str, status: int, kind: str = "application/json") -> SimpleNamespace:
    return SimpleNamespace(
        method="GET",
        url=URL(f"https://eniplenitude.com{path}?logHash=abc&codiceContoCliente=123456789"),
        status=status,
        headers={"Content-Type": f"{kind};charset=UTF-8"},
    )


def test_debug_trace_masks_the_codes(records: Records) -> None:
    path = "/serviceDAp/api/contiServices/conti/123456789/lista-forniture"
    _trace(fake_response(path, 401), '{"error":\n "Unauthorized"}')
    _trace(fake_response("/serviceDAp/api/c360/init", 200))
    assert records.messages == [
        "GET eniplenitude.com/serviceDAp/api/contiServices/conti/…/lista-forniture: HTTP 401 application/json"
        ' | {"error": "Unauthorized"}',
        "GET eniplenitude.com/serviceDAp/api/c360/init: HTTP 200 application/json",
    ]
    assert not any("123456789" in m or "logHash" in m for m in records.messages)


def test_debug_trace_shortens_long_answers(records: Records) -> None:
    _trace(fake_response("/serviceDAp/api/c360/init", 200, "text/html"), "<html>" + "x" * 1000 + " 9876543210")
    assert len(records.messages[0].split(" | ")[1]) == 300


def test_no_trace_without_debug(records: Records) -> None:
    logging.getLogger("custom_components.plenitude.api").setLevel(logging.INFO)
    _trace(fake_response("/serviceDAp/api/c360/init", 401), "body")
    assert not records.records


# Set-Cookie of getJwe as the portal writes them (values replaced): Expires without the comma after the day.
GETJWE_COOKIES = [
    "GYSESSION=abc+DEF/123==; Max-Age=86400; Expires=Mon   23 Nov 2026 20:20:54 GMT; Path=/; Secure; HttpOnly",
    "G-GENUI=ghi+JKL/456==; Max-Age=86400; Expires=Mon   23 Nov 2026 20:20:54 GMT; Domain=eniplenitude.com; "
    "Path=/; Secure; HttpOnly",
    "TS01dc4fc6=0123456789abcdef; Path=/; Secure; HttpOnly; SameSite=Strict",
]
GETJWE = URL("https://eniplenitude.com/serviceDAp/api/c360/getJwe")
SUPPLIES = URL("https://eniplenitude.com/serviceDAp/api/contiServices/conti/123/lista-forniture")


async def test_session_cookies_reach_every_service() -> None:
    """With aiohttp before 3.14.5 the cookies of getJwe lose Path=/; after the fix every service gets them."""
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        client = PlenitudeClient(session)
        session.cookie_jar.update_cookies_from_headers(GETJWE_COOKIES, GETJWE)
        client._fix_cookie_paths()
        sent = session.cookie_jar.filter_cookies(SUPPLIES)
        assert {"GYSESSION", "G-GENUI", "TS01dc4fc6"} <= set(sent)
        assert sent["GYSESSION"].value == "abc+DEF/123=="
        assert len([c for c in session.cookie_jar if c.key == "GYSESSION"]) == 1


async def test_newer_cookie_on_root_wins() -> None:
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        client = PlenitudeClient(session)
        old = SimpleCookie()
        old["GAESA"] = "old"
        old["GAESA"]["path"] = "/serviceDAp/api/c360"
        session.cookie_jar.update_cookies(old, GETJWE)
        session.cookie_jar.update_cookies({"GAESA": "new"}, URL("https://eniplenitude.com/"))
        client._fix_cookie_paths()
        assert [c.value for c in session.cookie_jar if c.key == "GAESA"] == ["new"]
        assert session.cookie_jar.filter_cookies(SUPPLIES)["GAESA"].value == "new"


@pytest.mark.parametrize(
    ("value", "power"),
    [
        ("6", 6.0),
        (4.5, 4.5),
        ("4,5", 4.5),
        ("3.0", 3.0),
        (None, None),
        ("", None),
        ("0", None),
        ("abc", None),
        ("nan", None),
    ],
)
def test_power_of_the_contract(value, power) -> None:
    from custom_components.plenitude.api import _power

    assert _power(value) == power
