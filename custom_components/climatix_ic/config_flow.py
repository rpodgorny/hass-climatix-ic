"""Config and options flow for Climatix IC."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .client import AuthError, ClimatixClient
from .const import (
    CONF_PLANT_ID,
    CONF_SCAN_INTERVAL,
    CONF_TOTP_SECRET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MIN_SCAN_INTERVAL,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_TOTP_SECRET): str,
    }
)


class ClimatixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow: credentials -> (pick plant) -> entry."""

    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict[str, Any] = {}
        self._plants: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = ClimatixClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], user_input[CONF_TOTP_SECRET]
            )
            try:
                plants = await self.hass.async_add_executor_job(_login_and_list, client)
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001 - surfaced to the user as a generic error
                LOGGER.exception("Climatix IC login failed")
                errors["base"] = "cannot_connect"
            else:
                if not plants:
                    errors["base"] = "no_plants"
                else:
                    self._creds = user_input
                    self._plants = plants
                    if len(plants) == 1:
                        return await self._create(plants[0])
                    return await self.async_step_plant()
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Triggered when stored credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            client = ClimatixClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], user_input[CONF_TOTP_SECRET]
            )
            try:
                await self.hass.async_add_executor_job(client.login)
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Climatix IC reauth failed")
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reauth_confirm", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_plant(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            plant = next(p for p in self._plants if p["id"] == user_input[CONF_PLANT_ID])
            return await self._create(plant)
        schema = vol.Schema(
            {vol.Required(CONF_PLANT_ID): vol.In({p["id"]: p["name"] for p in self._plants})}
        )
        return self.async_show_form(step_id="plant", data_schema=schema)

    async def _create(self, plant: dict) -> ConfigFlowResult:
        await self.async_set_unique_id(plant["id"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=plant["name"], data={**self._creds, CONF_PLANT_ID: plant["id"]}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ClimatixOptionsFlow()


class ClimatixOptionsFlow(OptionsFlow):
    """Just the poll interval for now."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema(
            {vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL))}
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _login_and_list(client: ClimatixClient) -> list[dict]:
    """Blocking: validate credentials and return the account's plants."""
    client.login()
    return client.list_plants()
