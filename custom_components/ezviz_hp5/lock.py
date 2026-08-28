"""Lock platform for EZVIZ HP5 Gate Controller."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .client import EzvizAuthError, EzvizCommandError, EzvizHp5Client
from .const import CONF_SERIAL, DOMAIN, UNLOCK_RESET_DELAY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EZVIZ HP5 lock entities from a config entry."""
    client: EzvizHp5Client = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data[CONF_SERIAL]

    async_add_entities(
        [
            EzvizHp5Lock(serial, "gate", "Gate", client.gate_unlock),
            EzvizHp5Lock(serial, "door", "Door", client.door_unlock),
        ]
    )


class EzvizHp5Lock(LockEntity):
    """Representation of an EZVIZ HP5 gate/door impulse lock."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self,
        serial: str,
        key: str,
        name: str,
        unlock_func: Callable[[], bool],
    ) -> None:
        self._unlock_func = unlock_func
        self._attr_is_locked = True
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"EZVIZ HP5 ({serial})",
            manufacturer="EZVIZ",
            model="HP5",
        )

    async def async_lock(self, **kwargs: Any) -> None:
        """No EZVIZ lock command is sent; just reflect the locked state."""
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send the unlock command, then revert to locked after a timeout."""
        _LOGGER.debug("Unlocking %s", self.entity_id)
        try:
            await self.hass.async_add_executor_job(self._unlock_func)
        except EzvizAuthError as err:
            _LOGGER.warning("Unlock of %s failed due to auth error: %s", self.entity_id, err)
            if self.platform.config_entry:
                self.platform.config_entry.async_start_reauth(self.hass)
            raise ConfigEntryAuthFailed(str(err)) from err
        except EzvizCommandError as err:
            _LOGGER.warning("Unlock of %s failed: %s", self.entity_id, err)
            raise HomeAssistantError(str(err)) from err

        self._attr_is_locked = False
        self.async_write_ha_state()
        async_call_later(self.hass, UNLOCK_RESET_DELAY, self._reset_to_locked)

    async def _reset_to_locked(self, _now: Any) -> None:
        self._attr_is_locked = True
        self.async_write_ha_state()
