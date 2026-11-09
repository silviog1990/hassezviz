"""EZVIZ HP5 cloud client.

Bypasses pyezvizapi's remote_unlock() which uses the wrong request format
for the HP5. Uses direct HTTP requests matching the EZVIZ mobile app's
format:
- Resource identifier "Video" in URL (not UUID)
- Body wrapped in {"value": {...}}
- featureCode sent as HTTP header
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Any

import requests
from pyezvizapi.client import EzvizClient

from .const import DEFAULT_CHANNEL_NO, LOCK_NO_DOOR, LOCK_NO_GATE

_LOGGER = logging.getLogger(__name__)

# Derived from uuid.getnode() (the host's MAC address). If the Home Assistant
# host/container is ever recreated with a different MAC, this value changes —
# worth knowing if EZVIZ ever starts rejecting bindCode after an environment
# change.
_mac_int = uuid.getnode()
_mac_str = ":".join(f"{(_mac_int >> i) & 0xFF:02x}" for i in range(40, -1, -8))
FEATURE_CODE = hashlib.md5(_mac_str.encode("utf-8")).hexdigest()


class EzvizAuthError(Exception):
    """Raised when EZVIZ authentication fails (invalid credentials)."""


class EzvizCommandError(Exception):
    """Raised when an EZVIZ command (e.g. unlock) fails."""


class EzvizBaseClient:
    """Manages the EZVIZ session shared by all supported devices."""

    def __init__(self, account: str, password: str, serial: str, api_url: str) -> None:
        self._account = account
        self._password = password
        self._serial = serial
        self._api_url = api_url
        self._client: EzvizClient | None = None
        self._session_id: str | None = None
        self._user_id: str | None = None
        self._authenticated = False
        # Serializes calls so parallel/rapid commands cannot race on re-login.
        self._lock = threading.RLock()

    @property
    def authenticated(self) -> bool:
        return self._authenticated

    def login(self) -> None:
        """Authenticate with EZVIZ cloud. Raises EzvizAuthError on failure."""
        _LOGGER.debug("Authenticating with EZVIZ cloud as %s", self._account)
        try:
            self._client = EzvizClient(
                account=self._account,
                password=self._password,
                url=self._api_url,
            )
            self._client.login()

            token = self._client._token
            self._session_id = token.get("session_id")
            self._user_id = str(token.get("username", ""))
            self._authenticated = True
        except Exception as err:
            self._authenticated = False
            raise EzvizAuthError(str(err)) from err

        _LOGGER.debug(
            "EZVIZ auth OK for serial %s (user: %s)", self._serial, self._user_id
        )

    def close(self) -> None:
        if self._client:
            try:
                self._client.close_session()
            except Exception:
                _LOGGER.exception("Error closing EZVIZ session")
            finally:
                self._authenticated = False
                self._client = None
                self._session_id = None
                self._user_id = None

    def _execute_with_retry(self, func, *args) -> Any:
        """Execute a sync function with auto re-auth on failure."""
        with self._lock:
            if not self._authenticated:
                self.login()

            try:
                return func(*args)
            except Exception as first_error:
                _LOGGER.warning("Command failed, re-authenticating: %s", first_error)
                self.close()
                try:
                    self.login()
                except EzvizAuthError as auth_error:
                    raise EzvizAuthError(str(auth_error)) from first_error

                return func(*args)


class EzvizHp5Client(EzvizBaseClient):
    """EZVIZ HP5 video intercom: gate/door unlock commands."""

    def _unlock(self, lock_no: int) -> bool:
        """Send unlock request matching EZVIZ app format."""
        if not self._session_id:
            raise EzvizCommandError("Not authenticated")

        api_url = f"https://{self._api_url}"
        url = (
            f"{api_url}/v3/iot-feature/action/{self._serial}"
            "/Video/0/DoorLockMgr/RemoteUnlockReq"
        )

        bind_code = f"{FEATURE_CODE}{self._user_id}"
        payload = {
            "value": {
                "unLockInfo": {
                    "bindCode": bind_code,
                    "streamToken": "",
                    "lockNo": lock_no,
                    "userName": self._user_id,
                }
            }
        }

        headers = {
            "sessionId": self._session_id,
            "Content-Type": "application/json",
            "featureCode": FEATURE_CODE,
        }

        _LOGGER.debug("Sending unlock request: serial=%s lockNo=%d", self._serial, lock_no)
        resp = requests.put(url, json=payload, headers=headers, timeout=15)
        body = resp.json()
        meta_code = body.get("meta", {}).get("code")
        meta_msg = body.get("meta", {}).get("message", "")

        if meta_code == 200:
            _LOGGER.debug("Unlock OK: lockNo=%d meta=%s", lock_no, meta_msg)
            return True

        _LOGGER.warning(
            "Unlock failed: lockNo=%d meta=%s %s", lock_no, meta_code, meta_msg
        )
        raise EzvizCommandError(f"EZVIZ API error: code={meta_code} message={meta_msg}")

    # def _lock(self, lock_no: int) -> bool:
    #     """Send lock request matching EZVIZ app format. Not wired up.
    #
    #     Request format verified against app traffic but intentionally not
    #     exposed — see docs/superpowers/specs/2026-08-28-hacs-integration-design.md.
    #     """
    #     if not self._session_id:
    #         raise EzvizCommandError("Not authenticated")
    #
    #     api_url = f"https://{self._api_url}"
    #     url = (
    #         f"{api_url}/v3/iot-feature/action/{self._serial}"
    #         "/Video/0/DoorLockMgr/RemoteLockReq"
    #     )
    #
    #     bind_code = f"{FEATURE_CODE}{self._user_id}"
    #     payload = {
    #         "value": {
    #             "lockInfo": {
    #                 "bindCode": bind_code,
    #                 "streamToken": "",
    #                 "lockNo": lock_no,
    #                 "userName": self._user_id,
    #             }
    #         }
    #     }
    #
    #     headers = {
    #         "sessionId": self._session_id,
    #         "Content-Type": "application/json",
    #         "featureCode": FEATURE_CODE,
    #     }
    #
    #     resp = requests.put(url, json=payload, headers=headers, timeout=15)
    #     body = resp.json()
    #     meta_code = body.get("meta", {}).get("code")
    #     meta_msg = body.get("meta", {}).get("message", "")
    #
    #     if meta_code == 200:
    #         return True
    #     raise EzvizCommandError(f"EZVIZ API error: code={meta_code} message={meta_msg}")

    def gate_unlock(self) -> bool:
        """Unlock (open) the gate (lockNo=1)."""
        return self._execute_with_retry(self._unlock, LOCK_NO_GATE)

    def door_unlock(self) -> bool:
        """Unlock (open) the door (lockNo=2)."""
        return self._execute_with_retry(self._unlock, LOCK_NO_DOOR)


@dataclass(frozen=True)
class Preset:
    """A saved camera position (index >= 1, unique per camera)."""

    index: int
    name: str


class EzvizCameraClient(EzvizBaseClient):
    """EZVIZ PTZ camera: list presets and move the camera to one of them."""

    def _post_form(self, path: str, extra_fields: dict[str, Any]) -> dict[str, Any]:
        """POST a form-encoded request in the EZVIZ app's format."""
        if not self._session_id:
            raise EzvizCommandError("Not authenticated")

        fields = {
            "sessionId": self._session_id,
            "subSerial": self._serial,
            "channelNo": DEFAULT_CHANNEL_NO,
            "featureCode": FEATURE_CODE,
            "clientType": 1,
            "clientVersion": "7.6.7.2915967",
            "customno": "1000001",
            "netType": "WIFI",
            "osVersion": "17.0",
            "clientNo": "",
            **extra_fields,
        }
        url = f"https://{self._api_url}{path}"
        try:
            resp = requests.post(url, data=fields, timeout=15)
            body = resp.json()
        except (requests.RequestException, ValueError) as err:
            raise EzvizCommandError(f"EZVIZ request failed: {err}") from err

        code = str(body.get("resultCode"))
        if code != "0":
            msg = body.get("resultDes", "")
            _LOGGER.warning("EZVIZ request %s failed: code=%s %s", path, code, msg)
            raise EzvizCommandError(f"EZVIZ API error: code={code} message={msg}")
        return body

    def _list_presets(self) -> list[Preset]:
        body = self._post_form("/api/device/preset/list", {})
        return [
            Preset(index=int(item["index"]), name=str(item.get("name", "")))
            for item in body.get("data") or []
        ]

    def _goto_preset(self, index: int) -> bool:
        _LOGGER.debug("Moving camera %s to preset %d", self._serial, index)
        self._post_form(
            "/api/device/preset/config",
            {"configPreset": "GOTO_PRESET", "index": index},
        )
        return True

    def list_presets(self) -> list[Preset]:
        """Return the presets defined on the camera."""
        return self._execute_with_retry(self._list_presets)

    def goto_preset(self, index: int) -> bool:
        """Move the camera to the preset with the given index."""
        return self._execute_with_retry(self._goto_preset, index)
