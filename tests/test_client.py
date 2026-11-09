"""Tests for EzvizHp5Client."""

from unittest.mock import MagicMock, patch

import pytest

import threading

from custom_components.ezviz_hp5.client import (
    EzvizAuthError,
    EzvizCameraClient,
    EzvizCommandError,
    EzvizHp5Client,
    Preset,
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


def _camera() -> EzvizCameraClient:
    return EzvizCameraClient(
        account="user@example.com",
        password="secret",
        serial="CAM123",
        api_url="apiieu.ezvizlife.com",
    )


def _ezviz(mock_ezviz_client):
    inst = MagicMock()
    inst._token = {"session_id": "sess-1", "username": "user1"}
    mock_ezviz_client.return_value = inst
    return inst


def _resp(body):
    r = MagicMock()
    r.json.return_value = body
    return r


@patch("custom_components.ezviz_hp5.client.requests.post")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_list_presets_parses_response(mock_ezviz_client, mock_post):
    _ezviz(mock_ezviz_client)
    mock_post.return_value = _resp(
        {
            "data": [
                {"subSerial": "CAM123", "channelNo": 1, "index": 1, "name": "Door", "picUrl": "x"},
                {"subSerial": "CAM123", "channelNo": 1, "index": 2, "name": "Garden", "picUrl": "y"},
            ],
            "resultCode": "0",
            "resultDes": "Request successfully",
        }
    )

    presets = _camera().list_presets()

    assert presets == [Preset(1, "Door"), Preset(2, "Garden")]
    assert mock_post.call_args.args[0].endswith("/api/device/preset/list")
    form = mock_post.call_args.kwargs["data"]
    assert form["subSerial"] == "CAM123"
    assert form["sessionId"] == "sess-1"


@patch("custom_components.ezviz_hp5.client.requests.post")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_list_presets_empty(mock_ezviz_client, mock_post):
    _ezviz(mock_ezviz_client)
    mock_post.return_value = _resp({"data": [], "resultCode": "0"})
    assert _camera().list_presets() == []


@patch("custom_components.ezviz_hp5.client.requests.post")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_list_presets_error_code_raises(mock_ezviz_client, mock_post):
    _ezviz(mock_ezviz_client)
    mock_post.return_value = _resp({"resultCode": "-1", "resultDes": "nope"})
    with pytest.raises(EzvizCommandError):
        _camera().list_presets()


@patch("custom_components.ezviz_hp5.client.requests.post")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_list_presets_retries_once_after_failure(mock_ezviz_client, mock_post):
    _ezviz(mock_ezviz_client)
    mock_post.side_effect = [
        _resp({"resultCode": "-1", "resultDes": "expired"}),
        _resp({"data": [{"index": 1, "name": "A"}], "resultCode": "0"}),
    ]
    assert _camera().list_presets() == [Preset(1, "A")]
    assert mock_ezviz_client.call_count == 2


@patch("custom_components.ezviz_hp5.client.requests.post")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_goto_preset_sends_expected_form(mock_ezviz_client, mock_post):
    _ezviz(mock_ezviz_client)
    mock_post.return_value = _resp({"resultCode": "0", "resultDes": "ok"})

    assert _camera().goto_preset(3) is True

    assert mock_post.call_args.args[0].endswith("/api/device/preset/config")
    form = mock_post.call_args.kwargs["data"]
    assert form["configPreset"] == "GOTO_PRESET"
    assert form["index"] == 3


@patch("custom_components.ezviz_hp5.client.requests.post")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_goto_preset_error_raises_after_retry(mock_ezviz_client, mock_post):
    _ezviz(mock_ezviz_client)
    mock_post.return_value = _resp({"resultCode": "-1", "resultDes": "bad"})
    with pytest.raises(EzvizCommandError):
        _camera().goto_preset(1)
    assert mock_post.call_count == 2


@patch("custom_components.ezviz_hp5.client.requests.post")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_goto_preset_auth_failure_on_relogin(mock_ezviz_client, mock_post):
    inst = _ezviz(mock_ezviz_client)
    mock_post.return_value = _resp({"resultCode": "-1"})
    client = _camera()
    client.login()
    inst.login.side_effect = Exception("bad credentials")
    with pytest.raises(EzvizAuthError):
        client.goto_preset(1)


@patch("custom_components.ezviz_hp5.client.requests.post")
@patch("custom_components.ezviz_hp5.client.EzvizClient")
def test_concurrent_presses_relogin_once(mock_ezviz_client, mock_post):
    _ezviz(mock_ezviz_client)
    ok = _resp({"resultCode": "0"})
    mock_post.side_effect = [_resp({"resultCode": "-1"}), ok, ok]
    client = _camera()

    threads = [threading.Thread(target=client.goto_preset, args=(i,)) for i in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # one initial login + a single re-login despite two parallel calls
    assert mock_ezviz_client.call_count == 2
    assert mock_post.call_count == 3
