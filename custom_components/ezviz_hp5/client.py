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
import uuid

import requests
from pyezvizapi.client import EzvizClient

from .const import LOCK_NO_DOOR, LOCK_NO_GATE

_LOGGER = logging.getLogger(__name__)

_mac_int = uuid.getnode()
_mac_str = ":".join(f"{(_mac_int >> i) & 0xFF:02x}" for i in range(40, -1, -8))
FEATURE_CODE = hashlib.md5(_mac_str.encode("utf-8")).hexdigest()


class EzvizAuthError(Exception):
    """Raised when EZVIZ authentication fails (invalid credentials)."""


class EzvizCommandError(Exception):
    """Raised when an EZVIZ command (e.g. unlock) fails."""


class EzvizHp5Client:
    """Manages EZVIZ authentication and gate/door unlock commands for HP5."""

    def __init__(self, account: str, password: str, serial: str, api_url: str) -> None:
        self._account = account
        self._password = password
        self._serial = serial
        self._api_url = api_url
        self._client: EzvizClient | None = None
        self._session_id: str | None = None
        self._user_id: str | None = None
        self._authenticated = False

    @property
    def authenticated(self) -> bool:
        return self._authenticated

    def login(self) -> None:
        """Authenticate with EZVIZ cloud. Raises EzvizAuthError on failure."""
        _LOGGER.info("Authenticating with EZVIZ cloud as %s", self._account)
        try:
            self._client = EzvizClient(
                account=self._account,
                password=self._password,
                url=self._api_url,
            )
            self._client.login()
        except Exception as err:
            self._authenticated = False
            raise EzvizAuthError(str(err)) from err

        token = self._client._token
        self._session_id = token.get("session_id")
        self._user_id = str(token.get("username", ""))
        self._authenticated = True
        _LOGGER.info(
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

        _LOGGER.info("Sending unlock request: serial=%s lockNo=%d", self._serial, lock_no)
        resp = requests.put(url, json=payload, headers=headers, timeout=15)
        body = resp.json()
        meta_code = body.get("meta", {}).get("code")
        meta_msg = body.get("meta", {}).get("message", "")

        if meta_code == 200:
            _LOGGER.info("Unlock OK: lockNo=%d meta=%s", lock_no, meta_msg)
            return True

        _LOGGER.warning(
            "Unlock failed: lockNo=%d meta=%d %s", lock_no, meta_code, meta_msg
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

    def _execute_with_retry(self, func, *args) -> bool:
        """Execute a sync function with auto re-auth on failure."""
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

    def gate_unlock(self) -> bool:
        """Unlock (open) the gate (lockNo=1)."""
        return self._execute_with_retry(self._unlock, LOCK_NO_GATE)

    def door_unlock(self) -> bool:
        """Unlock (open) the door (lockNo=2)."""
        return self._execute_with_retry(self._unlock, LOCK_NO_DOOR)
