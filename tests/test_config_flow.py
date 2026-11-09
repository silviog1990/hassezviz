"""Tests for the EZVIZ HP5 Gate Controller config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ezviz_hp5.client import EzvizAuthError
from custom_components.ezviz_hp5.const import DOMAIN

USER_INPUT = {
    "account": "user@example.com",
    "password": "secret",
    "serial": "ABC123",
    "api_url": "apiieu.ezvizlife.com",
}


async def test_user_flow_success(hass: HomeAssistant) -> None:
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

    assert result["type"] == "create_entry"
    assert result["title"] == "EZVIZ HP5 (ABC123)"
    assert result["data"] == {**USER_INPUT, "device_type": "hp5"}


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.ezviz_hp5.config_flow.EzvizHp5Client.login",
        side_effect=EzvizAuthError("bad credentials"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="ABC123")
    entry.add_to_hass(hass)

    with (
        patch("custom_components.ezviz_hp5.config_flow.EzvizHp5Client.login"),
        patch("custom_components.ezviz_hp5.config_flow.EzvizHp5Client.close"),
        patch("custom_components.ezviz_hp5.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-secret"}
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new-secret"


async def test_user_flow_ptz_camera(hass: HomeAssistant) -> None:
    data = {**USER_INPUT, "device_type": "ptz_camera"}
    with (
        patch("custom_components.ezviz_hp5.config_flow.EzvizCameraClient.login"),
        patch("custom_components.ezviz_hp5.config_flow.EzvizCameraClient.close"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], data
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "EZVIZ PTZ Camera (ABC123)"
    assert result["data"]["device_type"] == "ptz_camera"


async def test_reauth_preserves_device_type(hass: HomeAssistant) -> None:
    data = {**USER_INPUT, "device_type": "ptz_camera"}
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id="ABC123")
    entry.add_to_hass(hass)

    with (
        patch("custom_components.ezviz_hp5.config_flow.EzvizCameraClient.login") as login,
        patch("custom_components.ezviz_hp5.config_flow.EzvizCameraClient.close"),
        patch("custom_components.ezviz_hp5.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-secret"}
        )
        await hass.async_block_till_done()

    login.assert_called_once()
    assert result["reason"] == "reauth_successful"
    assert entry.data["device_type"] == "ptz_camera"
    assert entry.data["password"] == "new-secret"
