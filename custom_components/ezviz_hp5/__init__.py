"""The hassezviz integration (EZVIZ HP5 intercom and PTZ cameras)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .client import (
    EzvizAuthError,
    EzvizBaseClient,
    EzvizCameraClient,
    EzvizCommandError,
    EzvizHp5Client,
)
from .const import (
    CONF_API_URL,
    CONF_DEVICE_TYPE,
    CONF_SERIAL,
    DEFAULT_DEVICE_TYPE,
    DEVICE_TYPE_PTZ_CAMERA,
    DOMAIN,
)


def is_ptz_camera(entry: ConfigEntry) -> bool:
    """Entries without a device type are legacy HP5 entries."""
    return entry.data.get(CONF_DEVICE_TYPE, DEFAULT_DEVICE_TYPE) == DEVICE_TYPE_PTZ_CAMERA


def platforms_for(entry: ConfigEntry) -> list[Platform]:
    """Platforms to set up for this entry's device type."""
    return [Platform.BUTTON] if is_ptz_camera(entry) else [Platform.LOCK]


def create_client(entry: ConfigEntry) -> EzvizBaseClient:
    """Build the client matching the entry's device type."""
    client_cls = EzvizCameraClient if is_ptz_camera(entry) else EzvizHp5Client
    return client_cls(
        account=entry.data["account"],
        password=entry.data["password"],
        serial=entry.data[CONF_SERIAL],
        api_url=entry.data[CONF_API_URL],
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an EZVIZ device from a config entry."""
    client = create_client(entry)
    domain_data = hass.data.setdefault(DOMAIN, {})

    if is_ptz_camera(entry):
        try:
            presets = await hass.async_add_executor_job(client.list_presets)
        except EzvizAuthError as err:
            await hass.async_add_executor_job(client.close)
            raise ConfigEntryAuthFailed(str(err)) from err
        except EzvizCommandError as err:
            await hass.async_add_executor_job(client.close)
            raise ConfigEntryNotReady(str(err)) from err
        domain_data[entry.entry_id] = {"client": client, "presets": presets}
    else:
        domain_data[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, platforms_for(entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, platforms_for(entry)
    )
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client = data["client"] if is_ptz_camera(entry) else data
        await hass.async_add_executor_job(client.close)
    return unload_ok
