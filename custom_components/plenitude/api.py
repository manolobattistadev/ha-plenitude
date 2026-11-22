"""Unofficial async client for the Eni Plenitude customer area.

The API is not documented: it was reconstructed on 2026-11-22 from the traffic of the web app
(https://eniplenitude.com/my-eni) and can change without notice.

Authentication chain:
  1. Gigya (SAP Customer Data Cloud) ``accounts.login`` -> ``login_token`` (the Gigya session);
  2. ``accounts.getJWT`` with the ``login_token`` -> short-lived ``id_token``;
  3. ``serviceDAp/api/c360/getJwe`` with header ``JWT`` -> portal cookies ``GYSESSION`` and ``G-GENUI``.
Step 2-3 can be repeated without the password while the Gigya session is alive.

This module must not import Home Assistant: it is shared by the integration and by the command-line
prototype in ``scripts/``.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import secrets
import string
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp
from yarl import URL

GIGYA_API_KEY = "4_QsDZw2Yu7M9yCRldyBrBhg"  # public key of the site, visible in the page source
GIGYA_BASE = "https://login.eniplenitude.com"
PORTAL_HOST = "eniplenitude.com"
PORTAL_BASE = f"https://{PORTAL_HOST}"
SERVICE_BASE = f"{PORTAL_BASE}/serviceDAp"
PAGE_URL = f"{PORTAL_BASE}/my-eni"
ROME = ZoneInfo("Europe/Rome")
# Browser identity: the client presents itself as a current Firefox, coherent with the headers it sends (Firefox
# has no client hints, Chrome has). It starts from the Firefox of 2026-11-22 and advances one major version every
# 30 days: Firefox ships one about every four weeks, so the version stays close to the current release without
# getting ahead of it.
FIREFOX_VERSION = 160
FIREFOX_VERSION_DATE = date(2026, 11, 22)
FIREFOX_DAYS_PER_VERSION = 30
SAME_ORIGIN = "same-origin"  # Sec-Fetch-Site of the portal services, called by the page on eniplenitude.com
SAME_SITE = "same-site"  # Sec-Fetch-Site of Gigya, on login.eniplenitude.com
PORTAL_SESSION_COOKIES = ("GYSESSION", "G-GENUI")
_LOGGER = logging.getLogger(__name__)
_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

# Values of the "type" field of analysis/consumptions and the "view" the server answers with.
VIEW_DAY = "0"  # FIFTEEN_DAILY: 24 hourly values in "data", 96 quarter-hours in "additionalData"
VIEW_WEEK = "1"  # WEEKLY: one value per day
VIEW_MONTH = "2"  # MONTHLY: one value per day
VIEW_YEAR = "3"  # YEARLY: one value per month

# activityId of the estimated breakdown (Midori). 0 is "Energia attiva", the measured total.
TOTAL_ACTIVITY = 0
CATEGORIES: dict[int, str] = {
    1: "refrigerare",
    2: "standby",
    3: "lavare",
    4: "cucinare",
    5: "comfort_ambientale",
    6: "elettronica_luci",
    7: "altro",
    8: "ricarica_elettrica",
}


class PlenitudeError(Exception):
    """Generic error talking to the Plenitude customer area."""


class PlenitudeAuthError(PlenitudeError):
    """Gigya refused the login: wrong credentials, CAPTCHA required, locked account...

    In Home Assistant this must start a re-authentication flow: retrying will not help.
    """

    def __init__(self, code: int, message: str, details: str = "") -> None:
        text = f"Gigya error {code}: {message}"
        super().__init__(f"{text} ({details})" if details else text)
        self.code = code


class PlenitudeSessionExpired(PlenitudeError):
    """The portal or Gigya session is no longer valid: open a new one."""


@dataclass
class Account:
    """Identifiers of the logged-in customer (personal data: never log them)."""

    client_code: str
    account_code: str


@dataclass
class Supply:
    """One supply (electricity or gas) of the account."""

    kind: str
    pod: str | None
    pdr: str | None
    contract_id: str | None = None
    house_id: str | None = None
    address: str | None = None


@dataclass
class Reading:
    """Energy measured in one interval, in kWh. ``start`` is timezone-aware (Europe/Rome)."""

    start: datetime
    kwh: float


@dataclass
class DayConsumption:
    """Consumption of one day as returned by the ``FIFTEEN_DAILY`` view.

    Timestamps are rebuilt from the position of each value (see ``_sequence``). ``server_timestamps_ok``
    tells whether the server's own timestamps agreed: they do not on DST days.
    """

    day: date
    status: str | None
    hours: list[Reading]
    quarter_hours: list[Reading]
    server_timestamps_ok: bool = True


@dataclass
class MonthConsumption:
    """Daily consumption of one month per activity (``MONTHLY`` view).

    ``days`` maps a category key (``CATEGORIES`` values, or ``"totale"``) to ``{day: kWh}``; days without a
    value are missing. ``names`` are the labels the portal shows for each key.
    """

    year: int
    month: int
    status: str | None
    days: dict[str, dict[date, float]]
    names: dict[str, str]


def token_lifetime(jwt: str) -> int:
    """Lifetime in seconds of a JWT (``exp - iat``), read without verifying the signature."""
    payload = jwt.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))
    return int(claims["exp"]) - int(claims["iat"])


def user_agent(today: date | None = None) -> str:
    """User-Agent of a current Firefox on macOS (see ``FIREFOX_VERSION``)."""
    days = max(0, ((today or date.today()) - FIREFOX_VERSION_DATE).days)
    version = FIREFOX_VERSION + days // FIREFOX_DAYS_PER_VERSION
    return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:{version}.0) Gecko/20100101 Firefox/{version}.0"


def safe_path(path: str) -> str:
    """Path for error messages and logs: account and customer codes (5+ digits) are masked."""
    return re.sub(r"\d{5,}", "…", path)


def safe_error(err: BaseException) -> str:
    """Text of an error for logs and messages: no query strings, long numbers (customer codes) masked."""
    text = str(err) or type(err).__name__
    return re.sub(r"\d{5,}", "…", re.sub(r"\?[^\s'\"]*", "", text))


def _trace(resp: aiohttp.ClientResponse, answer: str | None = None) -> None:
    """Debug log of one request: method, host, path with the codes masked, status and type of the answer.

    ``answer`` (only for errors) is the start of the body, whitespace collapsed and long numbers masked: the
    error answers of the portal are generic (``{"error":"Unauthorized"}``, pages of the firewall).
    """
    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return
    kind = resp.headers.get("Content-Type", "-").split(";")[0]
    line = f"{resp.method} {resp.url.host}{safe_path(resp.url.path)}: HTTP {resp.status} {kind}"
    if answer is not None:
        line += " | " + re.sub(r"\d{5,}", "…", " ".join(answer.split()))[:300]
    _LOGGER.debug(line)


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def day_period(day: date) -> dict[str, str]:
    """``startTime``/``endTime`` for one day, built exactly as the web app does.

    The web app sends the next local midnight converted to UTC (for 20/11: ``2026-11-20T23:00:00.000Z``)
    and an ``endTime`` with the same date at 00:00Z. The server appears to use only the date part.
    """
    next_midnight = datetime.combine(day + timedelta(days=1), time.min, ROME)
    return {"startTime": _utc_iso(next_midnight), "endTime": f"{day.isoformat()}T00:00:00.000Z"}


def month_period(year: int, month: int) -> dict[str, str]:
    """``startTime``/``endTime`` for one month, built as the web app does.

    The web app sends local midnight of day 2 converted to UTC (for November: ``2026-11-01T23:00:00.000Z``)
    and the last day of the month at 23:00Z.
    """
    start = datetime.combine(date(year, month, 2), time.min, ROME)
    last = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    return {"startTime": _utc_iso(start), "endTime": f"{last.isoformat()}T23:00:00.000Z"}


def _day_label(name: Any, year: int, month: int) -> date | None:
    """Day of a ``dd/mm`` label of the monthly view, or ``None`` if it does not belong to the month."""
    try:
        day_text, month_text = str(name).split("/")
        if int(month_text) != month:
            return None
        return date(year, month, int(day_text))
    except ValueError:
        return None


def _sequence(items: list[dict[str, Any]] | None, day: date, step: timedelta) -> tuple[list[Reading], bool]:
    """Assign each value of a day to its interval by position, starting from local midnight.

    The server mislabels DST days: on 2026-03-29 it skips both 02:xx and 03:xx and runs one hour into
    the next day, although it returns the right number of values (92 quarter-hours, 23 hours). Real time
    is continuous, so value ``i`` covers ``midnight + i * step`` (computed in UTC). If the count does not
    match the length of the day the series is rejected (empty list) rather than imported wrongly.
    Returns the readings and whether the server timestamps matched the rebuilt ones.
    """
    items = items or []
    start = datetime.combine(day, time.min, ROME).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, ROME).astimezone(UTC)
    if not items or len(items) != (end - start) // step:
        return [], not items
    readings, server_ok = [], True
    for index, item in enumerate(items):
        moment = start + index * step
        if item.get("startTime") and int(item["startTime"]) != int(moment.timestamp()):
            server_ok = False
        if item.get("consumption") is not None:
            readings.append(Reading(start=moment.astimezone(ROME), kwh=float(item["consumption"])))
    return readings, server_ok


def _readings(items: list[dict[str, Any]] | None) -> list[Reading]:
    """Convert the ``data``/``additionalData`` lists, skipping intervals without a value."""
    readings = []
    for item in items or []:
        if item.get("consumption") is None or not item.get("startTime"):
            continue
        start = datetime.fromtimestamp(int(item["startTime"]), ROME)
        readings.append(Reading(start=start, kwh=float(item["consumption"])))
    return readings


class PlenitudeClient:
    """Client bound to an ``aiohttp.ClientSession`` with its own cookie jar.

    Do not share the session with other integrations: the portal session lives in its cookies.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self.login_token: str | None = None
        self.login_token_expires_at: datetime | None = None
        self._last_jwt: str | None = None

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _log_hash() -> str:
        """Random 22-character trace id, as generated by the web app (generateLogHash)."""
        return "".join(secrets.choice(_ALPHABET) for _ in range(22))

    @staticmethod
    def _headers(site: str, method: str = "GET", extra: dict[str, str] | None = None) -> dict[str, str]:
        """Headers of a request made by the page of the customer area, as Firefox sends them.

        ``site`` is the ``Sec-Fetch-Site`` (``SAME_ORIGIN`` or ``SAME_SITE``). Like the browser, ``Origin`` only
        on POST, and towards Gigya (another origin) the ``Referer`` reduced to the origin of the page.
        """
        headers = {
            "User-Agent": user_agent(),
            "Accept": "application/json, text/plain, */*" if site == SAME_ORIGIN else "*/*",
            "Accept-Language": "it-IT,it;q=0.9",
            "Referer": f"{PAGE_URL}/home" if site == SAME_ORIGIN else f"{PORTAL_BASE}/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": site,
        }
        if method != "GET":
            headers["Origin"] = PORTAL_BASE
        return {**headers, **(extra or {})}

    @staticmethod
    def _page_headers() -> dict[str, str]:
        """Headers of the navigation to the page of the customer area, as Firefox sends them."""
        return {
            "User-Agent": user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _gigya(self, method: str, data: dict[str, str]) -> dict[str, Any]:
        payload = {"APIKey": GIGYA_API_KEY, "sdk": "js_latest", "pageURL": PAGE_URL, "format": "json", **data}
        headers = self._headers(SAME_SITE, "POST")
        async with self._session.post(f"{GIGYA_BASE}/{method}", data=payload, headers=headers) as resp:
            text = await resp.text()
            _trace(resp)  # never the body: it contains the tokens
        try:
            result = json.loads(text)
        except json.JSONDecodeError as err:
            raise PlenitudeError(f"{method}: unexpected answer (HTTP {resp.status})") from err
        if result.get("errorCode", 0) != 0:
            raise PlenitudeAuthError(
                int(result["errorCode"]), result.get("errorMessage", ""), result.get("errorDetails", "")
            )
        return result

    async def _service(
        self, method: str, path: str, *, params: dict[str, str] | None = None, body: dict[str, Any] | None = None
    ) -> Any:
        query = {**(params or {}), "logHash": self._log_hash(), "channel": "PORTAL"}
        headers = self._headers(SAME_ORIGIN, method)
        async with self._session.request(
            method, f"{SERVICE_BASE}{path}", params=query, json=body, headers=headers, allow_redirects=False
        ) as resp:
            self._fix_cookie_paths()
            failed = resp.status >= 300 or (resp.status != 204 and "json" not in resp.headers.get("Content-Type", ""))
            debug = failed and _LOGGER.isEnabledFor(logging.DEBUG)
            _trace(resp, await resp.text(errors="replace") if debug else None)
            # 406 is what the portal answers after about an hour of inactivity (measured 2026-11-22).
            if resp.status in (301, 302, 303, 307, 308, 401, 403, 406):
                raise PlenitudeSessionExpired(f"{safe_path(path)}: HTTP {resp.status}")
            if resp.status == 204:
                return None
            if resp.status >= 400:
                # Not raise_for_status(): its message would contain the full URL with the codes.
                raise PlenitudeError(f"{safe_path(path)}: HTTP {resp.status}")
            if "json" not in resp.headers.get("Content-Type", ""):
                raise PlenitudeSessionExpired(
                    f"{safe_path(path)}: answer is {resp.headers.get('Content-Type')}, not JSON"
                )
            return await resp.json()

    def _fix_cookie_paths(self) -> None:
        """Bring the cookies of the portal back to the path ``/``, where the portal sets all of them.

        The portal writes ``Expires`` without the comma after the day (``Expires=Mon   23 Nov 2026 20:20:54
        GMT``), and the cookie parser of aiohttp before 3.14.5 (the one of Home Assistant 2026.9) then loses the
        attributes after it, ``Path=/`` included. The session cookies set by ``getJwe`` get the default path
        ``/serviceDAp/api/c360``: they are sent to ``c360/init`` but not to the other services, which answer
        HTTP 401 (found on 2026-11-22). With aiohttp 3.14.5 there is nothing to fix. A cookie with the same name
        already on ``/`` is newer and is kept.
        """
        jar = self._session.cookie_jar
        stray = [c for c in jar if (c["domain"] or "").endswith(PORTAL_HOST) and c["path"] not in ("", "/")]
        if not stray:
            return
        at_root = {(c["domain"], c.key) for c in jar if c["path"] in ("", "/")}
        keys = {(c["domain"], c["path"], c.key) for c in stray}
        jar.clear(lambda c: (c["domain"], c["path"], c.key) in keys)
        for cookie in stray:
            if (cookie["domain"], cookie.key) not in at_root:
                jar.update_cookies({cookie.key: cookie.value}, URL(f"https://{cookie['domain']}/"))
        _LOGGER.debug("Cookies moved to the path /: %s", ", ".join(sorted({c.key for c in stray})))

    def has_portal_session(self) -> bool:
        names = {cookie.key for cookie in self._session.cookie_jar}
        return all(name in names for name in PORTAL_SESSION_COOKIES)

    # ------------------------------------------------------------- authentication

    async def login(self, email: str, password: str, session_expiration: int = 3000) -> dict[str, int]:
        """Full login with the credentials. Returns the lifetimes observed (seconds)."""
        _LOGGER.debug("Signing in as %s", user_agent())
        # Landing page: the F5 application firewall sets its TS* cookies here.
        async with self._session.get(PAGE_URL, headers=self._page_headers()) as resp:
            _trace(resp)
            resp.raise_for_status()
        # Gigya bootstrap: device cookies (gmid, ucid) used by Gigya's risk assessment.
        async with self._session.get(
            f"{GIGYA_BASE}/accounts.webSdkBootstrap",
            params={"apiKey": GIGYA_API_KEY, "pageURL": PAGE_URL, "sdk": "js_latest", "format": "json"},
            headers=self._headers(SAME_SITE),
        ) as resp:
            _trace(resp)
            await resp.text()
        result = await self._gigya(
            "accounts.login",
            {
                "loginID": email,
                "password": password,
                "sessionExpiration": str(session_expiration),
                "targetEnv": "jssdk",
                "include": "profile,data,id_token,",
                "includeUserInfo": "true",
                "loginMode": "standard",
                "authMode": "cookie",
                "lang": "it",
                "source": "showScreenSet",
            },
        )
        info = result.get("sessionInfo") or {}
        if "login_token" not in info:
            raise PlenitudeError("accounts.login: no login_token in the answer")
        expires_in = int(info.get("expires_in", 0))
        self.login_token = info["login_token"]
        self.login_token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        jwt_seconds = await self.open_portal_session()
        return {"gigya_session": expires_in, "requested_gigya_session": session_expiration, "jwt": jwt_seconds}

    async def check_gigya_session(self) -> int:
        """Ask Gigya for a JWT with the stored ``login_token``. Returns the JWT lifetime (seconds).

        Raises ``PlenitudeSessionExpired`` if the Gigya session is over. Does not touch the portal cookies.
        """
        if not self.login_token:
            raise PlenitudeSessionExpired("no Gigya session")
        try:
            result = await self._gigya("accounts.getJWT", {"login_token": self.login_token, "authMode": "cookie"})
        except PlenitudeAuthError as err:
            raise PlenitudeSessionExpired(str(err)) from err
        self._last_jwt = result["id_token"]
        return token_lifetime(self._last_jwt)

    async def open_portal_session(self) -> int:
        """Exchange the Gigya session for the portal cookies, without the password. Returns the JWT lifetime."""
        jwt_seconds = await self.check_gigya_session()
        async with self._session.get(
            f"{SERVICE_BASE}/api/c360/getJwe",
            params={"channel": "PORTAL", "logHash": self._log_hash()},
            headers=self._headers(SAME_ORIGIN, extra={"JWT": self._last_jwt, "Referer": PAGE_URL}),
        ) as resp:
            debug = resp.status >= 400 and _LOGGER.isEnabledFor(logging.DEBUG)
            _trace(resp, await resp.text(errors="replace") if debug else None)
            if resp.status in (401, 403):
                raise PlenitudeSessionExpired(f"getJwe: HTTP {resp.status}")
            resp.raise_for_status()
            await resp.read()
        self._fix_cookie_paths()
        if not self.has_portal_session():
            raise PlenitudeError("getJwe did not set the portal session cookies")
        return jwt_seconds

    async def logout(self, account: Account | None = None) -> None:
        """Close the sessions as the web app does when the user signs out: Gigya first, then the portal.

        Best effort: errors are only written to the debug log. Without it every login stays open on the account
        until it expires (30 days for the one of the integration). The portal part needs the customer code
        (``account``).
        """
        if self.login_token:
            try:
                await self._gigya("accounts.logout", {"login_token": self.login_token})
            except (PlenitudeError, aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("Gigya logout failed: %s", safe_error(err))
        if account is not None and self.has_portal_session():
            log_hash = self._log_hash()
            extra = {"Cache-Control": "Clear-Site-Data", "Isbeta": "true"}
            try:
                async with self._session.post(
                    f"{SERVICE_BASE}/api/action/logout",
                    params={"logHash": log_hash},
                    json={"logHash": log_hash, "codiceCliente": account.client_code},
                    headers=self._headers(SAME_ORIGIN, "POST", extra),
                    allow_redirects=False,
                ) as resp:
                    _trace(resp)
                    await resp.read()
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("Portal logout failed: %s", safe_error(err))
        self.login_token = None
        self.login_token_expires_at = None
        self._last_jwt = None
        self._session.cookie_jar.clear()

    # ---------------------------------------------------------------- persistence

    def export_state(self) -> dict[str, Any]:
        """Session state to store between runs (secret: tokens and cookies)."""
        cookies = [
            {"name": c.key, "value": c.value, "domain": c["domain"] or "eniplenitude.com"}
            for c in self._session.cookie_jar
            if (c["domain"] or "").endswith("eniplenitude.com")
        ]
        return {
            "login_token": self.login_token,
            "login_token_expires_at": self.login_token_expires_at.isoformat() if self.login_token_expires_at else None,
            "cookies": cookies,
        }

    def import_state(self, state: dict[str, Any]) -> None:
        self.login_token = state.get("login_token")
        expires = state.get("login_token_expires_at")
        self.login_token_expires_at = datetime.fromisoformat(expires) if expires else None
        for cookie in state.get("cookies", []):
            domain = cookie["domain"].lstrip(".")
            self._session.cookie_jar.update_cookies({cookie["name"]: cookie["value"]}, URL(f"https://{domain}/"))

    # ----------------------------------------------------------------------- data

    async def get_account(self) -> Account:
        data = await self._service("GET", "/api/c360/init")
        if not data or not data.get("codiceCliente") or not data.get("codiceContoDefault"):
            raise PlenitudeSessionExpired("c360/init: no customer data (not logged in)")
        return Account(client_code=str(data["codiceCliente"]), account_code=str(data["codiceContoDefault"]))

    async def get_supplies(self, account: Account) -> list[Supply]:
        """Supplies of the account, with the ``contractId``/``houseId`` needed by the consumption API."""
        data = await self._service("GET", f"/api/contiServices/conti/{account.account_code}/lista-forniture")
        supplies = [
            Supply(
                kind=str(item.get("tipo")),
                pod=item.get("pod") or None,
                pdr=item.get("pdr") or None,
                address=item.get("indirizzoFornitura") or None,
            )
            for item in (data or {}).get("fornitura", [])
        ]
        for supply in supplies:
            profile = await self._service(
                "POST",
                f"/api/profilo-energetico-services/{account.account_code}/users/{account.client_code}/supplies",
                body={"pod": supply.pod or "", "pdr": supply.pdr or ""},
            )
            for item in (profile or {}).get("fornitureClienteMidori4FE", []):
                if supply.pod and item.get("lightCode") != supply.pod:
                    continue
                if supply.pdr and not supply.pod and item.get("gasCode") != supply.pdr:
                    continue
                supply.contract_id = str(item["contractId"])
                supply.house_id = str(item["houseId"])
                break
        return supplies

    async def get_day(self, account: Account, supply: Supply, day: date) -> DayConsumption:
        """Hourly and quarter-hourly consumption of one day (``FIFTEEN_DAILY`` view)."""
        if not supply.contract_id or not supply.house_id:
            raise PlenitudeError("supply without contractId/houseId: consumption analysis not available")
        body = {
            "clientCode": account.client_code,
            "contractId": supply.contract_id,
            "houseId": supply.house_id,
            **day_period(day),
            "type": VIEW_DAY,
        }
        data = await self._service(
            "POST", f"/api/profilo-energetico-services/{account.account_code}/analysis/consumptions", body=body
        )
        total = next(iter((data or {}).get("consumptionList") or []), {})
        hours, hours_ok = _sequence(total.get("data"), day, timedelta(hours=1))
        quarters, quarters_ok = _sequence((data or {}).get("additionalData"), day, timedelta(minutes=15))
        return DayConsumption(
            day=day,
            status=(data or {}).get("status"),
            hours=hours,
            quarter_hours=quarters,
            server_timestamps_ok=hours_ok and quarters_ok,
        )

    async def get_month(self, account: Account, supply: Supply, year: int, month: int) -> MonthConsumption:
        """Daily totals of one month, measured and per estimated category (``MONTHLY`` view).

        The categories exist only at this granularity: in the day view each one has a single value.
        """
        if not supply.contract_id or not supply.house_id:
            raise PlenitudeError("supply without contractId/houseId: consumption analysis not available")
        body = {
            "clientCode": account.client_code,
            "contractId": supply.contract_id,
            "houseId": supply.house_id,
            **month_period(year, month),
            "type": VIEW_MONTH,
        }
        data = await self._service(
            "POST", f"/api/profilo-energetico-services/{account.account_code}/analysis/consumptions", body=body
        )
        days: dict[str, dict[date, float]] = {}
        names: dict[str, str] = {}
        for item in (data or {}).get("consumptionList") or []:
            activity = item.get("activityId")
            if activity == TOTAL_ACTIVITY:
                key = "totale"
            elif activity in CATEGORIES:
                key = CATEGORIES[activity]
            else:
                key = f"categoria_{activity}"
            names[key] = str(item.get("activityName") or key)
            values = days.setdefault(key, {})
            for entry in item.get("data") or []:
                day = _day_label(entry.get("name"), year, month)
                if day is not None and entry.get("consumption") is not None:
                    values[day] = float(entry["consumption"])
        return MonthConsumption(year=year, month=month, status=(data or {}).get("status"), days=days, names=names)

    async def get_monthly_by_band(self, account: Account) -> list[dict[str, Any]]:
        """Monthly consumption per time band F1/F2/F3 (kWh, billing data), raw as returned."""
        data = await self._service("GET", "/api/consumptionData", params={"codiceContoCliente": account.account_code})
        return (data or {}).get("supplies", [])
