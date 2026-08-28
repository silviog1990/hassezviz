"""The EZVIZ HP5 Gate Controller integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .client import EzvizHp5Client
from .const import CONF_API_URL, CONF_SERIAL, DOMAIN

PLATFORMS = [Platform.LOCK]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EZVIZ HP5 Gate Controller from a config entry."""
    client = EzvizHp5Client(
        account=entry.data["account"],
        password=entry.data["password"],
        serial=entry.data[CONF_SERIAL],
        api_url=entry.data[CONF_API_URL],
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client: EzvizHp5Client = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(client.close)
    return unload_ok
