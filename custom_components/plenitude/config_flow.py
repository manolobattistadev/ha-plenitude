"""Configuration: credentials, choice of the supply, re-authentication, prices and additional costs."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlowWithReload,
    SubentryFlowResult,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import PlenitudeAuthError, PlenitudeClient, PlenitudeError, PlenitudeSessionExpired, Supply, safe_error
from .bands import PRICE_FIELDS, PRICE_MODE, PRICE_MODES, PRICE_NONE
from .const import CONF_SUPPLY, DOMAIN, supply_key
from .const import VERSION as INTEGRATION_VERSION
from .coordinator import PlenitudeConfigEntry
from .costs import (
    COST_AMOUNT,
    COST_EXEMPT,
    COST_KIND,
    COST_KINDS,
    COST_NAME,
    COST_POWER,
    COST_SUBENTRY,
    KIND_MONTHLY,
    KIND_PER_KW_MONTHLY,
    KIND_PER_KWH,
    KIND_PERCENT,
    CostItem,
    format_number,
    parse_number,
)
from .texts import text

_LOGGER = logging.getLogger(__name__)

CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)
# Numbers are typed as text and read by ``costs.parse_number``: a number field of the browser treats the decimal
# comma in its own way (refused, or lost, depending on the browser), while here "9,15" and "9.15" are the same and
# anything ambiguous gets a clear error.
PRICE_SELECTOR = TextSelector(TextSelectorConfig(suffix="€/kWh"))
PRICE_RANGE = (0.0, 10.0)
AMOUNT_RANGE = (-100000.0, 100000.0)  # negative for discounts and bonuses
POWER_RANGE = (0.1, 999.0)
PERCENT_RANGE = (-100.0, 100.0)
# A cost in two steps: name and kind, then the amount in the unit of the kind (euro, euro per kWh, euro per kW and
# the power, percent) and, for everything but the percentages, whether the percentages apply to it.
COST_SCHEMA = vol.Schema(
    {
        vol.Required(COST_NAME): TextSelector(),
        vol.Required(COST_KIND): SelectSelector(
            SelectSelectorConfig(options=list(COST_KINDS), mode=SelectSelectorMode.DROPDOWN, translation_key=COST_KIND)
        ),
    }
)
UNITS = {KIND_PER_KWH: "€/kWh", KIND_PER_KW_MONTHLY: "€/kW", KIND_PERCENT: "%"}
# Second step of each kind: its own texts (``step.<id>`` in the translations).
AMOUNT_STEPS = {KIND_PER_KW_MONTHLY: "per_kw", KIND_PERCENT: "percent"}


def _amount_schema(kind: str) -> vol.Schema:
    fields: dict[Any, Any] = {vol.Required(COST_AMOUNT): TextSelector(TextSelectorConfig(suffix=UNITS.get(kind, "€")))}
    if kind == KIND_PER_KW_MONTHLY:
        fields[vol.Required(COST_POWER)] = TextSelector(TextSelectorConfig(suffix="kW"))
    if kind != KIND_PERCENT:
        fields[vol.Required(COST_EXEMPT, default=False)] = BooleanSelector()
    return vol.Schema(fields)


async def _electric_supplies(hass: HomeAssistant, email: str, password: str) -> list[Supply]:
    """Log in with a throw-away session and return the supplies with the consumption analysis."""
    session = async_create_clientsession(hass, auto_cleanup=False, cookie_jar=aiohttp.CookieJar())
    try:
        client = PlenitudeClient(session)
        account = None
        try:
            await client.login(email, password)
            account = await client.get_account()
            supplies = await client.get_supplies(account)
        finally:
            # Close the throw-away login: the integration opens its own one when the entry is set up.
            await client.logout(account)
    finally:
        session.detach()  # the connector is shared with Home Assistant: detach, do not close
    return [s for s in supplies if s.pod and s.contract_id and s.house_id]


def _label(supply: Supply) -> str:
    pod = f"POD …{(supply.pod or '')[-4:]}"
    return f"{supply.address} ({pod})" if supply.address else pod


class PlenitudeConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, str] = {}
        self._supplies: list[Supply] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: PlenitudeConfigEntry) -> PlenitudeOptionsFlow:
        return PlenitudeOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {COST_SUBENTRY: CostSubentryFlow}

    async def _check(self, email: str, password: str) -> tuple[list[Supply], str | None]:
        try:
            supplies = await _electric_supplies(self.hass, email, password)
        except PlenitudeAuthError as err:
            _LOGGER.warning("Plenitude %s: login refused by Plenitude: %s", INTEGRATION_VERSION, safe_error(err))
            return [], "invalid_auth"
        except PlenitudeSessionExpired as err:
            # Login accepted, but the customer area refuses the data of the account (HTTP 401 from the services of
            # the account; on 2026-11-22 the cause was the cookie paths, see api._fix_cookie_paths). The login was
            # closed anyway.
            _LOGGER.warning(
                "Plenitude %s: login accepted, but the customer area refused the account data: %s",
                INTEGRATION_VERSION,
                safe_error(err),
            )
            return [], "portal_refused"
        except (PlenitudeError, aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Plenitude %s: cannot reach the customer area: %s", INTEGRATION_VERSION, safe_error(err))
            return [], "cannot_connect"
        except Exception:
            _LOGGER.exception("Plenitude %s: unexpected error during the login", INTEGRATION_VERSION)
            return [], "unknown"
        return supplies, None if supplies else "no_supplies"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            supplies, error = await self._check(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                self._credentials = {CONF_EMAIL: user_input[CONF_EMAIL], CONF_PASSWORD: user_input[CONF_PASSWORD]}
                self._supplies = supplies
                if len(supplies) == 1:
                    return await self._create(supplies[0], multiple=False)
                return await self.async_step_supply()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CREDENTIALS_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_supply(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            chosen = next(s for s in self._supplies if supply_key(s.pod or "") == user_input[CONF_SUPPLY])
            return await self._create(chosen, multiple=True)
        options = [SelectOptionDict(value=supply_key(s.pod or ""), label=_label(s)) for s in self._supplies]
        return self.async_show_form(
            step_id="supply",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SUPPLY): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
        )

    async def _create(self, supply: Supply, multiple: bool) -> ConfigFlowResult:
        key = supply_key(supply.pod or "")
        await self.async_set_unique_id(key)
        self._abort_if_unique_id_configured()
        title = text(self.hass.config.language, "title")
        if multiple:
            title = f"{title} …{(supply.pod or '')[-4:]}"
        return self.async_create_entry(
            title=title, data={**self._credentials, CONF_SUPPLY: key}, options={PRICE_MODE: PRICE_NONE}
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            supplies, error = await self._check(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            if not error and not any(supply_key(s.pod or "") == entry.data[CONF_SUPPLY] for s in supplies):
                error = "supply_missing"
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
                    )
                }
            ),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )


class PlenitudeOptionsFlow(OptionsFlowWithReload):
    """Price of the energy: none, single, two bands (F1, F23) or three bands (F1, F2, F3)."""

    def __init__(self) -> None:
        self._mode = PRICE_NONE

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._mode = user_input[PRICE_MODE]
            if self._mode == PRICE_NONE:
                return self.async_create_entry(data={PRICE_MODE: PRICE_NONE})
            return await self.async_step_prices()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        PRICE_MODE, default=self.config_entry.options.get(PRICE_MODE, PRICE_NONE)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=list(PRICE_MODES), mode=SelectSelectorMode.LIST, translation_key=PRICE_MODE
                        )
                    )
                }
            ),
        )

    async def async_step_prices(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        fields = PRICE_FIELDS[self._mode]
        errors: dict[str, str] = {}
        if user_input is not None:
            prices: dict[str, float] = {}
            for field in fields:
                price, error = parse_number(user_input.get(field), *PRICE_RANGE)
                if price is None or error:
                    errors[field] = "invalid_price"
                else:
                    prices[field] = price
            if not errors:
                return self.async_create_entry(data={PRICE_MODE: self._mode, **prices})
        current = self.config_entry.options
        schema = vol.Schema({vol.Required(field): PRICE_SELECTOR for field in fields})
        lang = self.hass.config.language
        known = user_input or {f: format_number(current[f], lang) for f in fields if f in current}
        return self.async_show_form(
            step_id="prices", data_schema=self.add_suggested_values_to_schema(schema, known), errors=errors
        )


class CostSubentryFlow(ConfigSubentryFlow):
    """An additional cost: free name and kind (monthly, two-monthly, yearly, per kW per month, per kWh, percentage),
    then the amount; the power of the contract for the costs per kW per month; whether the percentages apply.

    Home Assistant lists the costs under the entry, with buttons to add, edit and delete them. The entry is
    reloaded when they change (see ``__init__``), so that the cost history follows the costs per kWh and the
    percentages.
    """

    def __init__(self) -> None:
        self._name = ""
        self._kind = KIND_MONTHLY

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._first("user", user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._first("reconfigure", user_input)

    def _editing(self) -> dict[str, Any]:
        """Data of the cost being edited, empty for a new one."""
        return dict(self._get_reconfigure_subentry().data) if self.source == "reconfigure" else {}

    async def _first(self, step_id: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        """Name and kind."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._name = str(user_input[COST_NAME]).strip()
            self._kind = user_input[COST_KIND]
            if self._name:
                return await self._amount(None)
            errors[COST_NAME] = "empty_name"
        editing = self._editing()
        suggested = (
            user_input or {k: editing[k] for k in (COST_NAME, COST_KIND) if k in editing} or {COST_KIND: KIND_MONTHLY}
        )
        return self.async_show_form(
            step_id=step_id, data_schema=self.add_suggested_values_to_schema(COST_SCHEMA, suggested), errors=errors
        )

    async def async_step_amount(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._amount(user_input)

    async def async_step_per_kw(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._amount(user_input)

    async def async_step_percent(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._amount(user_input)

    async def _amount(self, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        """Amount in the unit of the kind, the power for the costs per kW, the exemption from the percentages."""
        kind = self._kind
        errors: dict[str, str] = {}
        if user_input is not None:
            if kind == KIND_PERCENT:
                amount, error = parse_number(user_input.get(COST_AMOUNT), *PERCENT_RANGE)
                error = error and "invalid_percent"
            else:
                amount, error = parse_number(user_input.get(COST_AMOUNT), *AMOUNT_RANGE)
            if error:
                errors[COST_AMOUNT] = error
            power = None
            if kind == KIND_PER_KW_MONTHLY:
                power, power_error = parse_number(user_input.get(COST_POWER), *POWER_RANGE)
                if power_error:
                    errors[COST_POWER] = "invalid_power"
            if amount is not None and not errors:
                exempt = bool(user_input.get(COST_EXEMPT, False)) and kind != KIND_PERCENT
                return self._save(CostItem(name=self._name, kind=kind, amount=amount, power=power, exempt=exempt))
        return self.async_show_form(
            step_id=AMOUNT_STEPS.get(kind, "amount"),
            data_schema=self.add_suggested_values_to_schema(_amount_schema(kind), user_input or self._known()),
            description_placeholders={"name": self._name},
            errors=errors,
        )

    def _known(self) -> dict[str, Any]:
        """What the second step proposes: the values of the cost being edited (the amount only if its unit is the
        same), and for the costs per kW the power of the customer area when none was entered."""
        editing = self._editing()
        lang = self.hass.config.language
        known: dict[str, Any] = {}
        if editing and UNITS.get(editing[COST_KIND], "€") == UNITS.get(self._kind, "€"):
            known[COST_AMOUNT] = format_number(float(editing[COST_AMOUNT]), lang)
        if self._kind == KIND_PER_KW_MONTHLY and (power := editing.get(COST_POWER) or self._portal_power()):
            known[COST_POWER] = format_number(float(power), lang)
        if self._kind != KIND_PERCENT:
            known[COST_EXEMPT] = bool(editing.get(COST_EXEMPT, False))
        return known

    def _portal_power(self) -> float | None:
        coordinator = getattr(self._get_entry(), "runtime_data", None)
        return getattr(coordinator, "contract_power", None)

    def _save(self, item: CostItem) -> SubentryFlowResult:
        data = item.as_dict()
        if self.source == "reconfigure":
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), title=item.name, data=data
            )
        return self.async_create_entry(title=item.name, data=data)
