"""Button platform for EZVIZ PTZ cameras: one button per preset + refresh."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import EzvizAuthError, EzvizCameraClient, EzvizCommandError, Preset
from .const import CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _device_info(serial: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        name=f"EZVIZ PTZ Camera ({serial})",
        manufacturer="EZVIZ",
        model="PTZ Camera",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up preset buttons from the preset list loaded at entry setup."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: EzvizCameraClient = data["client"]
    presets: list[Preset] = data["presets"]
    serial = entry.data[CONF_SERIAL]

    # Drop buttons of presets that no longer exist on the camera.
    wanted = {f"{serial}_preset_{p.index}" for p in presets}
    registry = er.async_get(hass)
    prefix = f"{serial}_preset_"
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id.startswith(prefix) and reg_entry.unique_id not in wanted:
            registry.async_remove(reg_entry.entity_id)

    async_add_entities(
        [EzvizPresetButton(client, serial, preset) for preset in presets]
        + [EzvizRefreshPresetsButton(entry, serial)]
    )


class EzvizPresetButton(ButtonEntity):
    """Moves the camera to one saved preset."""

    _attr_has_entity_name = True

    def __init__(self, client: EzvizCameraClient, serial: str, preset: Preset) -> None:
        self._client = client
        self._preset = preset
        self._attr_unique_id = f"{serial}_preset_{preset.index}"
        self._attr_name = preset.name or f"Preset {preset.index}"
        self._attr_device_info = _device_info(serial)

    async def async_press(self) -> None:
        _LOGGER.debug("Moving to preset %d (%s)", self._preset.index, self.entity_id)
        try:
            await self.hass.async_add_executor_job(
                self._client.goto_preset, self._preset.index
            )
        except EzvizAuthError as err:
            _LOGGER.warning("Preset %s failed due to auth error: %s", self.entity_id, err)
            if self.platform.config_entry:
                self.platform.config_entry.async_start_reauth(self.hass)
            raise ConfigEntryAuthFailed(str(err)) from err
        except EzvizCommandError as err:
            _LOGGER.warning("Preset %s failed: %s", self.entity_id, err)
            raise HomeAssistantError(str(err)) from err


class EzvizRefreshPresetsButton(ButtonEntity):
    """Reloads the entry so the preset list is read again from the camera."""

    _attr_has_entity_name = True
    _attr_name = "Refresh presets"

    def __init__(self, entry: ConfigEntry, serial: str) -> None:
        self._entry = entry
        self._attr_unique_id = f"{serial}_refresh_presets"
        self._attr_device_info = _device_info(serial)

    async def async_press(self, **kwargs: Any) -> None:
        self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
