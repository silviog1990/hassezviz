"""Config flow for EZVIZ HP5 Gate Controller."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant

from .client import EzvizAuthError, EzvizHp5Client
from .const import CONF_API_URL, CONF_SERIAL, DEFAULT_API_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("account"): str,
        vol.Required("password"): str,
        vol.Required(CONF_SERIAL): str,
        vol.Optional(CONF_API_URL, default=DEFAULT_API_URL): str,
    }
)


async def _validate_login(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Attempt a real EZVIZ login; raises EzvizAuthError on failure."""
    client = EzvizHp5Client(
        account=data["account"],
        password=data["password"],
        serial=data[CONF_SERIAL],
        api_url=data[CONF_API_URL],
    )
    await hass.async_add_executor_job(client.login)
    await hass.async_add_executor_job(client.close)


class EzvizHp5ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EZVIZ HP5 Gate Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SERIAL])
            self._abort_if_unique_id_configured()

            try:
                await _validate_login(self.hass, user_input)
            except EzvizAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error validating EZVIZ credentials")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"EZVIZ HP5 ({user_input[CONF_SERIAL]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth triggered by ConfigEntryAuthFailed."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            data = {**reauth_entry.data, "password": user_input["password"]}
            try:
                await _validate_login(self.hass, data)
            except EzvizAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error validating EZVIZ credentials")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(reauth_entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("password"): str}),
            errors=errors,
        )
