"""Tests for EzvizHp5Client."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.ezviz_hp5.client import (
    EzvizAuthError,
    EzvizCommandError,
    EzvizHp5Client,
)


def _client() -> EzvizHp5Client:
    return EzvizHp5Client(
        account="user@example.com",
        password="secret",
        serial="ABC123",
        api_url="apiieu.ezvizlife.com",
    )


@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_login_success(mock_ezviz_client):
    mock_instance = MagicMock()
    mock_instance._token = {"session_id": "sess-1", "username": "user1"}
    mock_ezviz_client.return_value = mock_instance

    client = _client()
    client.login()

    assert client.authenticated is True


@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_login_failure_raises_auth_error(mock_ezviz_client):
    mock_instance = MagicMock()
    mock_instance.login.side_effect = Exception("bad credentials")
    mock_ezviz_client.return_value = mock_instance

    client = _client()
    with pytest.raises(EzvizAuthError):
        client.login()

    assert client.authenticated is False


@patch("custom_components.ezviz_hp5.client.requests.put")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_gate_unlock_success(mock_ezviz_client, mock_put):
    mock_instance = MagicMock()
    mock_instance._token = {"session_id": "sess-1", "username": "user1"}
    mock_ezviz_client.return_value = mock_instance

    mock_response = MagicMock()
    mock_response.json.return_value = {"meta": {"code": 200, "message": "OK"}}
    mock_put.return_value = mock_response

    client = _client()
    result = client.gate_unlock()

    assert result is True
    called_url = mock_put.call_args.args[0]
    assert "/Video/0/DoorLockMgr/RemoteUnlockReq" in called_url
    sent_payload = mock_put.call_args.kwargs["json"]
    assert sent_payload["value"]["unLockInfo"]["lockNo"] == 1


@patch("custom_components.ezviz_hp5.client.requests.put")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_door_unlock_uses_lock_no_2(mock_ezviz_client, mock_put):
    mock_instance = MagicMock()
    mock_instance._token = {"session_id": "sess-1", "username": "user1"}
    mock_ezviz_client.return_value = mock_instance

    mock_response = MagicMock()
    mock_response.json.return_value = {"meta": {"code": 200, "message": "OK"}}
    mock_put.return_value = mock_response

    client = _client()
    client.door_unlock()

    sent_payload = mock_put.call_args.kwargs["json"]
    assert sent_payload["value"]["unLockInfo"]["lockNo"] == 2


@patch("custom_components.ezviz_hp5.client.requests.put")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_gate_unlock_api_error_raises_command_error(mock_ezviz_client, mock_put):
    mock_instance = MagicMock()
    mock_instance._token = {"session_id": "sess-1", "username": "user1"}
    mock_ezviz_client.return_value = mock_instance

    mock_response = MagicMock()
    mock_response.json.return_value = {"meta": {"code": 500, "message": "boom"}}
    mock_put.return_value = mock_response

    client = _client()
    with pytest.raises(EzvizCommandError):
        client.gate_unlock()


@patch("custom_components.ezviz_hp5.client.requests.put")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_unlock_retries_after_failure_then_succeeds(mock_ezviz_client, mock_put):
    mock_instance = MagicMock()
    mock_instance._token = {"session_id": "sess-1", "username": "user1"}
    mock_ezviz_client.return_value = mock_instance

    failing_response = MagicMock()
    failing_response.json.return_value = {"meta": {"code": 500, "message": "boom"}}
    ok_response = MagicMock()
    ok_response.json.return_value = {"meta": {"code": 200, "message": "OK"}}
    mock_put.side_effect = [failing_response, ok_response]

    client = _client()
    result = client.gate_unlock()

    assert result is True
    assert mock_put.call_count == 2
    assert mock_ezviz_client.call_count == 2
