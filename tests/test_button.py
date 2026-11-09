"""Tests for the EZVIZ PTZ camera button platform."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ezviz_hp5.client import (
    EzvizAuthError,
    EzvizCommandError,
    Preset,
)
from custom_components.ezviz_hp5.const import DOMAIN

CLIENT = "custom_components.ezviz_hp5.client.EzvizCameraClient"
PRESETS = [Preset(1, "Entrance"), Preset(2, "Garden"), Preset(3, "Street")]


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "account": "user@example.com",
            "password": "secret",
            "serial": "CAM123",
            "api_url": "apiieu.ezvizlife.com",
            "device_type": "ptz_camera",
        },
        unique_id="CAM123",
    )


async def _setup(hass, entry, presets=PRESETS):
    entry.add_to_hass(hass)
    with patch(f"{CLIENT}.login"), patch(f"{CLIENT}.close"), patch(
        f"{CLIENT}.list_presets", return_value=list(presets)
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _button_ids(hass):
    return hass.states.async_entity_ids("button")


def _names(hass):
    registry = er.async_get(hass)
    return sorted(registry.async_get(e).original_name for e in _button_ids(hass))


async def test_presets_become_buttons(hass: HomeAssistant) -> None:
    await _setup(hass, _entry())
    assert _names(hass) == ["Entrance", "Garden", "Refresh presets", "Street"]
    assert hass.states.async_entity_ids("lock") == []


async def test_no_presets_only_refresh_button(hass: HomeAssistant) -> None:
    await _setup(hass, _entry(), presets=[])
    assert _names(hass) == ["Refresh presets"]


async def test_press_moves_to_preset(hass: HomeAssistant) -> None:
    await _setup(hass, _entry())
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("button", DOMAIN, "CAM123_preset_2")

    with patch(f"{CLIENT}.goto_preset", return_value=True) as goto:
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )
    goto.assert_called_once_with(2)


async def test_press_error_raises_homeassistant_error(hass: HomeAssistant) -> None:
    await _setup(hass, _entry())
    entity_id = er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, "CAM123_preset_1"
    )
    with patch(f"{CLIENT}.goto_preset", side_effect=EzvizCommandError("boom")):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "button", "press", {"entity_id": entity_id}, blocking=True
            )


async def test_press_auth_error_starts_reauth(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry)
    entity_id = er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, "CAM123_preset_1"
    )
    with patch(f"{CLIENT}.goto_preset", side_effect=EzvizAuthError("bad")):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "button", "press", {"entity_id": entity_id}, blocking=True
            )
    await hass.async_block_till_done()
    flows = [
        f
        for f in hass.config_entries.flow.async_progress()
        if f["context"].get("source") == config_entries.SOURCE_REAUTH
        and f["context"].get("entry_id") == entry.entry_id
    ]
    assert len(flows) == 1


async def test_refresh_reloads_and_removes_deleted_presets(
    hass: HomeAssistant,
) -> None:
    entry = _entry()
    await _setup(hass, entry)
    registry = er.async_get(hass)
    refresh_id = registry.async_get_entity_id("button", DOMAIN, "CAM123_refresh_presets")

    new_presets = [Preset(1, "Front door"), Preset(4, "Roof")]
    with patch(f"{CLIENT}.login"), patch(f"{CLIENT}.close"), patch(
        f"{CLIENT}.list_presets", return_value=new_presets
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": refresh_id}, blocking=True
        )
        await hass.async_block_till_done()

    assert _names(hass) == ["Front door", "Refresh presets", "Roof"]
    assert registry.async_get_entity_id("button", DOMAIN, "CAM123_preset_2") is None
    assert registry.async_get_entity_id("button", DOMAIN, "CAM123_preset_3") is None
