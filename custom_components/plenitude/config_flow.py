"""Configuration: credentials, choice of the supply, re-authentication and price options."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import PlenitudeAuthError, PlenitudeClient, PlenitudeError, Supply
from .bands import PRICE_FIELDS, PRICE_MODE, PRICE_MODES, PRICE_NONE
from .const import CONF_SUPPLY, DOMAIN, supply_key
from .coordinator import PlenitudeConfigEntry

_LOGGER = logging.getLogger(__name__)

CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)
PRICE_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=0, max=10, step="any", mode=NumberSelectorMode.BOX, unit_of_measurement="€/kWh")
)


async def _electric_supplies(hass: HomeAssistant, email: str, password: str) -> list[Supply]:
    """Log in with a throw-away session and return the supplies with the consumption analysis."""
    session = async_create_clientsession(hass, auto_cleanup=False, cookie_jar=aiohttp.CookieJar())
    try:
        client = PlenitudeClient(session)
        await client.login(email, password)
        account = await client.get_account()
        supplies = await client.get_supplies(account)
    finally:
        session.detach()  # the connector is shared with Home Assistant: detach, do not close
    return [s for s in supplies if s.pod and s.contract_id and s.house_id]


def _label(supply: Supply) -> str:
    pod = supply.pod or ""
    return f"{supply.address or 'Fornitura luce'} (POD …{pod[-4:]})"


class PlenitudeConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, str] = {}
        self._supplies: list[Supply] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: PlenitudeConfigEntry) -> PlenitudeOptionsFlow:
        return PlenitudeOptionsFlow()

    async def _check(self, email: str, password: str) -> tuple[list[Supply], str | None]:
        try:
            supplies = await _electric_supplies(self.hass, email, password)
        except PlenitudeAuthError as err:
            _LOGGER.debug("Login refused: %s", err)
            return [], "invalid_auth"
        except (PlenitudeError, aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Cannot reach Plenitude: %s", err)
            return [], "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during the Plenitude login")
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
        title = f"Plenitude luce …{(supply.pod or '')[-4:]}" if multiple else "Plenitude luce"
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
                    vol.Required(PRICE_MODE, default=self.config_entry.options.get(PRICE_MODE, PRICE_NONE)): SelectSelector(
                        SelectSelectorConfig(
                            options=list(PRICE_MODES), mode=SelectSelectorMode.LIST, translation_key=PRICE_MODE
                        )
                    )
                }
            ),
        )

    async def async_step_prices(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        fields = PRICE_FIELDS[self._mode]
        if user_input is not None:
            return self.async_create_entry(
                data={PRICE_MODE: self._mode, **{field: float(user_input[field]) for field in fields}}
            )
        current = self.config_entry.options
        schema = vol.Schema({vol.Required(field): PRICE_SELECTOR for field in fields})
        return self.async_show_form(
            step_id="prices",
            data_schema=self.add_suggested_values_to_schema(schema, {f: current[f] for f in fields if f in current}),
            description_placeholders={"mode": self._mode},
        )
