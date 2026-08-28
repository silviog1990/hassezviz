"""Tests for the EZVIZ HP5 Gate Controller lock platform."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.ezviz_hp5.client import EzvizCommandError
from custom_components.ezviz_hp5.const import UNLOCK_RESET_DELAY
from custom_components.ezviz_hp5.lock import EzvizHp5Lock


async def test_unlock_success_then_resets_to_locked(hass: HomeAssistant) -> None:
    unlock_func = MagicMock(return_value=True)

    entity = EzvizHp5Lock("ABC123", "gate", "Gate", unlock_func)
    entity.hass = hass
    entity.entity_id = "lock.test_gate"

    assert entity.is_locked is True

    await entity.async_unlock()
    assert entity.is_locked is False
    unlock_func.assert_called_once()

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=UNLOCK_RESET_DELAY + 1)
    )
    await hass.async_block_till_done()

    assert entity.is_locked is True


async def test_unlock_command_error_raises_homeassistant_error(
    hass: HomeAssistant,
) -> None:
    unlock_func = MagicMock(side_effect=EzvizCommandError("boom"))

    entity = EzvizHp5Lock("ABC123", "gate", "Gate", unlock_func)
    entity.hass = hass
    entity.entity_id = "lock.test_gate"

    with pytest.raises(HomeAssistantError):
        await entity.async_unlock()

    assert entity.is_locked is True


async def test_manual_lock_does_not_call_ezviz(hass: HomeAssistant) -> None:
    unlock_func = MagicMock(return_value=True)

    entity = EzvizHp5Lock("ABC123", "door", "Door", unlock_func)
    entity.hass = hass
    entity.entity_id = "lock.test_door"

    await entity.async_unlock()
    assert entity.is_locked is False

    await entity.async_lock()
    assert entity.is_locked is True
    unlock_func.assert_called_once()  # only the unlock call, never a lock call
