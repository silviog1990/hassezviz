"""Integration tests for the EZVIZ HP5 Gate Controller config entry lifecycle."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ezviz_hp5.client import EzvizAuthError
from custom_components.ezviz_hp5.const import DOMAIN

USER_INPUT = {
    "account": "user@example.com",
    "password": "secret",
    "serial": "ABC123",
    "api_url": "apiieu.ezvizlife.com",
}


def _make_entry(**overrides) -> MockConfigEntry:
    data = {**USER_INPUT, **overrides}
    return MockConfigEntry(domain=DOMAIN, data=data, unique_id=data["serial"])


async def test_setup_creates_two_lock_entities_and_unloads_cleanly(
    hass: HomeAssistant,
) -> None:
    entry = _make_entry()
    entry.add_to_hass(hass)

    with (
        patch("custom_components.ezviz_hp5.client.EzvizHp5Client.login"),
        patch("custom_components.ezviz_hp5.client.EzvizHp5Client.close"),
        patch(
            "custom_components.ezviz_hp5.client.EzvizHp5Client.gate_unlock",
            return_value=True,
        ),
        patch(
            "custom_components.ezviz_hp5.client.EzvizHp5Client.door_unlock",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        lock_entity_ids = hass.states.async_entity_ids("lock")
        assert len(lock_entity_ids) == 2

        # Exercise the unlock service on one entity end-to-end.
        target_entity_id = lock_entity_ids[0]
        await hass.services.async_call(
            "lock",
            "unlock",
            {"entity_id": target_entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hass.states.get(target_entity_id).state == "unlocked"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_unlock_auth_failure_triggers_reauth_flow(hass: HomeAssistant) -> None:
    entry = _make_entry()
    entry.add_to_hass(hass)

    with (
        patch("custom_components.ezviz_hp5.client.EzvizHp5Client.login"),
        patch("custom_components.ezviz_hp5.client.EzvizHp5Client.close"),
        patch(
            "custom_components.ezviz_hp5.client.EzvizHp5Client.gate_unlock",
            side_effect=EzvizAuthError("bad credentials"),
        ),
        patch(
            "custom_components.ezviz_hp5.client.EzvizHp5Client.door_unlock",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        lock_entity_ids = sorted(hass.states.async_entity_ids("lock"))
        gate_entity_id = next(e for e in lock_entity_ids if "gate" in e)

        # The gate unlock call raises EzvizAuthError -> ConfigEntryAuthFailed,
        # which propagates to the service caller as a HomeAssistantError.
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "lock",
                "unlock",
                {"entity_id": gate_entity_id},
                blocking=True,
            )
        await hass.async_block_till_done()

    reauth_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"].get("source") == config_entries.SOURCE_REAUTH
        and flow["context"].get("entry_id") == entry.entry_id
    ]
    assert len(reauth_flows) == 1


async def test_duplicate_serial_aborts_already_configured(hass: HomeAssistant) -> None:
    existing_entry = _make_entry()
    existing_entry.add_to_hass(hass)

    with (
        patch("custom_components.ezviz_hp5.config_flow.EzvizHp5Client.login"),
        patch("custom_components.ezviz_hp5.config_flow.EzvizHp5Client.close"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_legacy_entry_without_device_type_is_hp5(hass: HomeAssistant) -> None:
    entry = _make_entry()  # no device_type key
    entry.add_to_hass(hass)
    with (
        patch("custom_components.ezviz_hp5.client.EzvizHp5Client.login"),
        patch("custom_components.ezviz_hp5.client.EzvizHp5Client.close"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("lock")) == 2
    assert hass.states.async_entity_ids("button") == []


async def test_hp5_and_ptz_camera_coexist(hass: HomeAssistant) -> None:
    from custom_components.ezviz_hp5.client import Preset

    hp5 = _make_entry()
    cam = _make_entry(serial="CAM123", device_type="ptz_camera")
    hp5.add_to_hass(hass)
    cam.add_to_hass(hass)
    with (
        patch("custom_components.ezviz_hp5.client.EzvizHp5Client.login"),
        patch("custom_components.ezviz_hp5.client.EzvizHp5Client.close"),
        patch("custom_components.ezviz_hp5.client.EzvizCameraClient.login"),
        patch("custom_components.ezviz_hp5.client.EzvizCameraClient.close"),
        patch(
            "custom_components.ezviz_hp5.client.EzvizCameraClient.list_presets",
            return_value=[Preset(1, "Entrance")],
        ),
    ):
        # Setting up the domain loads every entry of that domain.
        assert await hass.config_entries.async_setup(hp5.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_entity_ids("lock")) == 2
        assert len(hass.states.async_entity_ids("button")) == 2  # preset + refresh
        assert await hass.config_entries.async_unload(cam.entry_id)
        assert await hass.config_entries.async_unload(hp5.entry_id)


async def test_ptz_setup_auth_failure_triggers_reauth(hass: HomeAssistant) -> None:
    cam = _make_entry(serial="CAM123", device_type="ptz_camera")
    cam.add_to_hass(hass)
    with (
        patch("custom_components.ezviz_hp5.client.EzvizCameraClient.close"),
        patch(
            "custom_components.ezviz_hp5.client.EzvizCameraClient.list_presets",
            side_effect=EzvizAuthError("bad"),
        ),
    ):
        assert not await hass.config_entries.async_setup(cam.entry_id)
    assert cam.state is config_entries.ConfigEntryState.SETUP_ERROR


async def test_ptz_setup_command_failure_retries_later(hass: HomeAssistant) -> None:
    from custom_components.ezviz_hp5.client import EzvizCommandError

    cam = _make_entry(serial="CAM123", device_type="ptz_camera")
    cam.add_to_hass(hass)
    with (
        patch("custom_components.ezviz_hp5.client.EzvizCameraClient.close"),
        patch(
            "custom_components.ezviz_hp5.client.EzvizCameraClient.list_presets",
            side_effect=EzvizCommandError("down"),
        ),
    ):
        assert not await hass.config_entries.async_setup(cam.entry_id)
    assert cam.state is config_entries.ConfigEntryState.SETUP_RETRY
