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
import secrets
import string
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp
from yarl import URL

GIGYA_API_KEY = "4_QsDZw2Yu7M9yCRldyBrBhg"  # public key of the site, visible in the page source
GIGYA_BASE = "https://login.eniplenitude.com"
PORTAL_BASE = "https://eniplenitude.com"
SERVICE_BASE = f"{PORTAL_BASE}/serviceDAp"
PAGE_URL = f"{PORTAL_BASE}/my-eni"
ROME = ZoneInfo("Europe/Rome")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
PORTAL_SESSION_COOKIES = ("GYSESSION", "G-GENUI")
_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

# Values of the "type" field of analysis/consumptions and the "view" the server answers with.
VIEW_DAY = "0"  # FIFTEEN_DAILY: 24 hourly values in "data", 96 quarter-hours in "additionalData"
VIEW_WEEK = "1"  # WEEKLY: one value per day
VIEW_MONTH = "2"  # MONTHLY: one value per day
VIEW_YEAR = "3"  # YEARLY: one value per month


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


@dataclass
class Reading:
    """Energy measured in one interval, in kWh. ``start`` is timezone-aware (Europe/Rome)."""

    start: datetime
    kwh: float


@dataclass
class DayConsumption:
    """Consumption of one day as returned by the ``FIFTEEN_DAILY`` view."""

    day: date
    status: str | None
    hours: list[Reading]
    quarter_hours: list[Reading]


def token_lifetime(jwt: str) -> int:
    """Lifetime in seconds of a JWT (``exp - iat``), read without verifying the signature."""
    payload = jwt.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))
    return int(claims["exp"]) - int(claims["iat"])


def _utc_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def day_period(day: date) -> dict[str, str]:
    """``startTime``/``endTime`` for one day, built exactly as the web app does.

    The web app sends the next local midnight converted to UTC (for 20/11: ``2026-11-20T23:00:00.000Z``)
    and an ``endTime`` with the same date at 00:00Z. The server appears to use only the date part.
    """
    next_midnight = datetime.combine(day + timedelta(days=1), time.min, ROME)
    return {"startTime": _utc_iso(next_midnight), "endTime": f"{day.isoformat()}T00:00:00.000Z"}


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
    def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "it-IT,it;q=0.9",
            "Origin": PORTAL_BASE,
            "Referer": f"{PAGE_URL}/home",
        }
        return {**headers, **(extra or {})}

    async def _gigya(self, method: str, data: dict[str, str]) -> dict[str, Any]:
        payload = {"APIKey": GIGYA_API_KEY, "sdk": "js_latest", "pageURL": PAGE_URL, "format": "json", **data}
        async with self._session.post(f"{GIGYA_BASE}/{method}", data=payload, headers=self._headers()) as resp:
            text = await resp.text()
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
        headers = self._headers({"Accept": "application/json, text/plain, */*"})
        async with self._session.request(
            method, f"{SERVICE_BASE}{path}", params=query, json=body, headers=headers, allow_redirects=False
        ) as resp:
            if resp.status in (301, 302, 303, 307, 308, 401, 403):
                raise PlenitudeSessionExpired(f"{path}: HTTP {resp.status}")
            if resp.status == 204:
                return None
            resp.raise_for_status()
            if "json" not in resp.headers.get("Content-Type", ""):
                raise PlenitudeSessionExpired(f"{path}: answer is {resp.headers.get('Content-Type')}, not JSON")
            return await resp.json()

    def has_portal_session(self) -> bool:
        names = {cookie.key for cookie in self._session.cookie_jar}
        return all(name in names for name in PORTAL_SESSION_COOKIES)

    # ------------------------------------------------------------- authentication

    async def login(self, email: str, password: str, session_expiration: int = 3000) -> dict[str, int]:
        """Full login with the credentials. Returns the lifetimes observed (seconds)."""
        # Landing page: the F5 application firewall sets its TS* cookies here.
        async with self._session.get(PAGE_URL, headers=self._headers()) as resp:
            resp.raise_for_status()
        # Gigya bootstrap: device cookies (gmid, ucid) used by Gigya's risk assessment.
        async with self._session.get(
            f"{GIGYA_BASE}/accounts.webSdkBootstrap",
            params={"apiKey": GIGYA_API_KEY, "pageURL": PAGE_URL, "sdk": "js_latest", "format": "json"},
            headers=self._headers(),
        ) as resp:
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
        self.login_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
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
            headers=self._headers({"JWT": self._last_jwt, "Accept": "application/json, text/plain, */*"}),
        ) as resp:
            if resp.status in (401, 403):
                raise PlenitudeSessionExpired(f"getJwe: HTTP {resp.status}")
            resp.raise_for_status()
            await resp.read()
        if not self.has_portal_session():
            raise PlenitudeError("getJwe did not set the portal session cookies")
        return jwt_seconds

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
            Supply(kind=str(item.get("tipo")), pod=item.get("pod") or None, pdr=item.get("pdr") or None)
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
        return DayConsumption(
            day=day,
            status=(data or {}).get("status"),
            hours=_readings(total.get("data")),
            quarter_hours=_readings((data or {}).get("additionalData")),
        )

    async def get_monthly_by_band(self, account: Account) -> list[dict[str, Any]]:
        """Monthly consumption per time band F1/F2/F3 (kWh, billing data), raw as returned."""
        data = await self._service("GET", "/api/consumptionData", params={"codiceContoCliente": account.account_code})
        return (data or {}).get("supplies", [])
