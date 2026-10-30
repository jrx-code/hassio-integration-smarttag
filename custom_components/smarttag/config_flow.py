"""Konfiguracja przez UI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmartTagApiError, SmartTagAuthError, SmartThingsClient
from .const import (
    CONF_AWAY_SECONDS,
    CONF_PAT,
    CONF_TOKEN_SOURCE,
    DEFAULT_AWAY_SECONDS,
    DOMAIN,
    SOURCE_PAT,
    SOURCE_SMARTTHINGS,
)
from .coordinator import borrow_smartthings_token


class SmartTagConfigFlow(ConfigFlow, domain=DOMAIN):
    """Wybór źródła tokenu: wbudowana integracja SmartThings albo PAT."""

    VERSION = 1

    async def _validate(self, token: str) -> tuple[str | None, int]:
        client = SmartThingsClient(async_get_clientsession(self.hass), token)
        try:
            tags = await client.async_list_tags()
        except SmartTagAuthError:
            return "invalid_auth", 0
        except SmartTagApiError:
            return "cannot_connect", 0
        return None, len(tags)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        has_st = borrow_smartthings_token(self.hass) is not None
        if user_input is not None:
            source = user_input[CONF_TOKEN_SOURCE]
            token = (
                borrow_smartthings_token(self.hass)
                if source == SOURCE_SMARTTHINGS
                else user_input.get(CONF_PAT, "").strip()
            )
            if not token:
                errors["base"] = "no_token"
            else:
                error, count = await self._validate(token)
                if error:
                    errors["base"] = error
                elif count == 0:
                    errors["base"] = "no_tags"
                else:
                    data = {CONF_TOKEN_SOURCE: source}
                    if source == SOURCE_PAT:
                        data[CONF_PAT] = token
                    return self.async_create_entry(title="SmartTag", data=data)
        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN_SOURCE, default=SOURCE_SMARTTHINGS if has_st else SOURCE_PAT): vol.In(
                    [SOURCE_SMARTTHINGS, SOURCE_PAT]
                ),
                vol.Optional(CONF_PAT): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            if entry.data.get(CONF_TOKEN_SOURCE) == SOURCE_PAT:
                token = user_input.get(CONF_PAT, "").strip()
            else:
                token = borrow_smartthings_token(self.hass) or ""
            error, _ = await self._validate(token) if token else ("no_token", 0)
            if not error:
                new = dict(entry.data)
                if entry.data.get(CONF_TOKEN_SOURCE) == SOURCE_PAT:
                    new[CONF_PAT] = token
                return self.async_update_reload_and_abort(entry, data=new)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PAT): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SmartTagOptionsFlow()


class SmartTagOptionsFlow(OptionsFlow):
    """Po ilu sekundach bez ramki tag uznajemy za nieobecny."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_AWAY_SECONDS, DEFAULT_AWAY_SECONDS)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_AWAY_SECONDS, default=current): vol.All(int, vol.Range(30, 3600))}
            ),
        )
