"""Identity of the client towards the customer area (User-Agent and headers)."""

import re
from datetime import date, timedelta

from custom_components.plenitude.api import (
    FIREFOX_DAYS_PER_VERSION,
    FIREFOX_VERSION,
    FIREFOX_VERSION_DATE,
    SAME_ORIGIN,
    SAME_SITE,
    PlenitudeClient,
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
