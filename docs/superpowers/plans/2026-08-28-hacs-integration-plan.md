# EZVIZ HP5 HACS Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the FastAPI microservice with a native, HACS-installable Home Assistant custom integration exposing EZVIZ HP5 gate/door unlock as `lock` entities, configured entirely through the HA UI.

**Architecture:** A `custom_components/ezviz_hp5/` integration with a synchronous `EzvizHp5Client` (ported from `EzvizGateService`, called via `hass.async_add_executor_job`), a `ConfigFlow` with reauth support, and two `LockEntity` instances per config entry (Gate, Door) with optimistic/impulse behavior — no coordinator, no polling.

**Tech Stack:** Python, Home Assistant custom component APIs (`homeassistant.config_entries`, `homeassistant.components.lock`), `pyezvizapi` (session/login only), `requests` (hand-built unlock PUT), `pytest-homeassistant-custom-component` for tests.

**Spec:** `docs/superpowers/specs/2026-08-28-hacs-integration-design.md`

## Global Constraints

- Integration domain: `ezviz_hp5`.
- Dependencies in `manifest.json`: `pyezvizapi>=1.0.4`, `requests>=2.31.0` (same floor as the current `requirements.txt`).
- `iot_class: "assumed_state"` — no polling, no `DataUpdateCoordinator`.
- Lock (close) command is never called; the ported request format is kept only as commented-out reference code in `client.py`.
- `async_lock()` never calls EZVIZ; it just sets local state back to `locked`.
- Unlock impulse reset delay: 5 seconds (`UNLOCK_RESET_DELAY` constant), after which the entity reverts to `locked` locally.
- Config entry `unique_id` = EZVIZ device serial number; duplicate serials are rejected.
- Reauth (`ConfigEntryAuthFailed` → HA reauth flow) is required whenever a command fails due to invalid credentials.
- The FastAPI microservice files are fully removed: `app.py`, `ezviz_service.py`, `config.py`, `Dockerfile`, `docker_build.sh`, `docker_push.sh`, `docker_run.sh`, `docker-compose.yml`, `requirements.txt`, `ezviz_token.json`, `devices.json`, `appunti.txt`, `.env`, `.env.build`, `.env.example`, `.env.build.example`.
- Config flow form must explain, in the field description, how to find the EZVIZ device serial number (EZVIZ app → device → settings gear → Device Info → Serial Number, or the physical label/QR code on the HP5).

---

## Task 1: Remove legacy FastAPI/Docker files

**Files:**
- Delete: `app.py`, `ezviz_service.py`, `config.py`, `Dockerfile`, `docker_build.sh`, `docker_push.sh`, `docker_run.sh`, `docker-compose.yml`, `requirements.txt`, `ezviz_token.json`, `devices.json`, `appunti.txt`, `.env`, `.env.build`, `.env.example`, `.env.build.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: a clean repo root containing only `LICENSE`, `README.md`, `README.it.md`, `CLAUDE.md`, `docs/`, `.gitignore` — the base for the new `custom_components/` tree built in later tasks.

- [ ] **Step 1: Delete the legacy files**

```bash
git rm -f app.py ezviz_service.py config.py Dockerfile docker_build.sh docker_push.sh docker_run.sh docker-compose.yml requirements.txt
rm -f ezviz_token.json devices.json appunti.txt .env .env.build .env.example .env.build.example
```

(`ezviz_token.json`, `devices.json`, `appunti.txt`, and the `.env*` files were gitignored/untracked, so `rm -f` is enough for them; the rest were tracked, so `git rm -f`.)

- [ ] **Step 2: Simplify `.gitignore`**

Replace its contents with:

```
__pycache__/
*.pyc
.venv/
venv/
.DS_Store
**/.DS_Store
.pytest_cache/
```

(Drop the FastAPI-specific entries: `.env`, `*.json` allowlist tricks, `appunti.txt`, `.env.build`, `.docker_version`, `docs/*` — none of those apply to a HACS integration repo, and `docs/superpowers/` needs to stay tracked.)

- [ ] **Step 3: Verify the working tree**

Run: `git status`
Expected: only the deletions above and the modified `.gitignore` are staged/changed; no other unexpected files.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Remove legacy FastAPI microservice files

Replaced by the custom_components/ezviz_hp5 HACS integration built in
subsequent commits."
```

---

## Task 2: Core EZVIZ client (`client.py`)

**Files:**
- Create: `custom_components/ezviz_hp5/__init__.py` (empty package marker only — full setup logic added in Task 5)
- Create: `custom_components/ezviz_hp5/const.py`
- Create: `custom_components/ezviz_hp5/client.py`
- Test: `tests/test_client.py`
- Create: `tests/__init__.py` (empty)

**Interfaces:**
- Produces:
  - `const.DOMAIN = "ezviz_hp5"`
  - `const.CONF_SERIAL = "serial"`, `const.CONF_API_URL = "api_url"`, `const.DEFAULT_API_URL = "apiieu.ezvizlife.com"`
  - `const.LOCK_NO_GATE = 1`, `const.LOCK_NO_DOOR = 2`, `const.UNLOCK_RESET_DELAY = 5`
  - `client.EzvizAuthError(Exception)`, `client.EzvizCommandError(Exception)`
  - `client.EzvizHp5Client(account: str, password: str, serial: str, api_url: str)` with:
    - `.authenticated` (bool property)
    - `.login() -> None` (sync, raises `EzvizAuthError`)
    - `.close() -> None` (sync)
    - `.gate_unlock() -> bool` (sync, raises `EzvizCommandError` / `EzvizAuthError`)
    - `.door_unlock() -> bool` (sync, raises `EzvizCommandError` / `EzvizAuthError`)

- [ ] **Step 1: Create the package skeleton**

```bash
mkdir -p custom_components/ezviz_hp5 tests
touch custom_components/ezviz_hp5/__init__.py tests/__init__.py
```

- [ ] **Step 2: Write `const.py`**

```python
"""Constants for the EZVIZ HP5 Gate Controller integration."""

DOMAIN = "ezviz_hp5"

CONF_SERIAL = "serial"
CONF_API_URL = "api_url"

DEFAULT_API_URL = "apiieu.ezvizlife.com"

LOCK_NO_GATE = 1
LOCK_NO_DOOR = 2

UNLOCK_RESET_DELAY = 5
```

- [ ] **Step 3: Write the failing tests for `client.py`**

Create `tests/test_client.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `pytest tests/test_client.py -v`
Expected: FAIL / collection error — `custom_components.ezviz_hp5.client` does not exist yet.

- [ ] **Step 5: Write `client.py`**

```python
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
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_client.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
git add custom_components/ezviz_hp5/__init__.py custom_components/ezviz_hp5/const.py custom_components/ezviz_hp5/client.py tests/__init__.py tests/test_client.py
git commit -m "Add EzvizHp5Client (ported from EzvizGateService)"
```

---

## Task 3: HACS/manifest metadata and strings

**Files:**
- Create: `custom_components/ezviz_hp5/manifest.json`
- Create: `custom_components/ezviz_hp5/strings.json`
- Create: `custom_components/ezviz_hp5/translations/en.json`
- Create: `custom_components/ezviz_hp5/translations/it.json`
- Create: `hacs.json`

**Interfaces:**
- Consumes: `const.DOMAIN` value `"ezviz_hp5"` (Task 2) — must match `manifest.json`'s `"domain"`.
- Produces: the string keys `config.step.user`, `config.step.reauth_confirm`, `config.error.invalid_auth`, `config.error.unknown`, `config.abort.already_configured`, `config.abort.reauth_successful`, consumed by `config_flow.py` in Task 4 (HA resolves these by step id / error id / abort reason automatically — no direct import).

- [ ] **Step 1: Write `manifest.json`**

```json
{
  "domain": "ezviz_hp5",
  "name": "EZVIZ HP5 Gate Controller",
  "codeowners": ["@silviog1990"],
  "config_flow": true,
  "documentation": "https://github.com/silviog1990/ezviz-hp5-homeassistant-integration",
  "integration_type": "hub",
  "iot_class": "assumed_state",
  "issue_tracker": "https://github.com/silviog1990/ezviz-hp5-homeassistant-integration/issues",
  "requirements": ["pyezvizapi>=1.0.4", "requests>=2.31.0"],
  "version": "0.1.0"
}
```

- [ ] **Step 2: Write `strings.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "EZVIZ HP5 Gate Controller",
        "description": "Enter your EZVIZ account credentials and the intercom's serial number.\n\nTo find the serial number: open the EZVIZ app, select your HP5 device, tap the settings gear icon, then \"Device Info\" — the serial number is listed there. It is also printed on the physical label/QR code on the back of the device.",
        "data": {
          "account": "EZVIZ account (email)",
          "password": "EZVIZ password",
          "serial": "Device serial number",
          "api_url": "API URL (advanced, leave default unless instructed otherwise)"
        }
      },
      "reauth_confirm": {
        "title": "Reauthenticate EZVIZ HP5 Gate Controller",
        "description": "Your EZVIZ password is no longer valid. Enter the new password to continue.",
        "data": {
          "password": "EZVIZ password"
        }
      }
    },
    "error": {
      "invalid_auth": "Invalid EZVIZ credentials.",
      "unknown": "Unexpected error occurred."
    },
    "abort": {
      "already_configured": "This device is already configured.",
      "reauth_successful": "Re-authentication was successful."
    }
  }
}
```

- [ ] **Step 3: Copy it to `translations/en.json`**

```bash
mkdir -p custom_components/ezviz_hp5/translations
cp custom_components/ezviz_hp5/strings.json custom_components/ezviz_hp5/translations/en.json
```

- [ ] **Step 4: Write `translations/it.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "EZVIZ HP5 Gate Controller",
        "description": "Inserisci le credenziali del tuo account EZVIZ e il numero di serie del citofono.\n\nPer trovare il numero di serie: apri l'app EZVIZ, seleziona il tuo dispositivo HP5, tocca l'icona delle impostazioni (ingranaggio), poi \"Informazioni dispositivo\" — il numero di serie è indicato lì. È anche stampato sull'etichetta fisica/QR code sul retro del dispositivo.",
        "data": {
          "account": "Account EZVIZ (email)",
          "password": "Password EZVIZ",
          "serial": "Numero di serie del dispositivo",
          "api_url": "URL API (avanzato, lascia il valore predefinito salvo indicazioni diverse)"
        }
      },
      "reauth_confirm": {
        "title": "Reimposta le credenziali EZVIZ HP5 Gate Controller",
        "description": "La password EZVIZ non è più valida. Inserisci la nuova password per continuare.",
        "data": {
          "password": "Password EZVIZ"
        }
      }
    },
    "error": {
      "invalid_auth": "Credenziali EZVIZ non valide.",
      "unknown": "Si è verificato un errore imprevisto."
    },
    "abort": {
      "already_configured": "Questo dispositivo è già configurato.",
      "reauth_successful": "La reimpostazione delle credenziali è avvenuta con successo."
    }
  }
}
```

- [ ] **Step 5: Write `hacs.json`**

```json
{
  "name": "EZVIZ HP5 Gate Controller",
  "render_readme": true
}
```

- [ ] **Step 6: Validate JSON syntax**

Run: `python -c "import json; [json.load(open(f)) for f in ['custom_components/ezviz_hp5/manifest.json','custom_components/ezviz_hp5/strings.json','custom_components/ezviz_hp5/translations/en.json','custom_components/ezviz_hp5/translations/it.json','hacs.json']]"`
Expected: no output, exit code 0 (all files parse as valid JSON).

- [ ] **Step 7: Commit**

```bash
git add custom_components/ezviz_hp5/manifest.json custom_components/ezviz_hp5/strings.json custom_components/ezviz_hp5/translations hacs.json
git commit -m "Add HACS manifest, strings, and translations"
```

---

## Task 4: Config flow with reauth (`config_flow.py`)

**Files:**
- Create: `custom_components/ezviz_hp5/config_flow.py`
- Create: `tests/conftest.py`
- Create: `requirements_test.txt`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `client.EzvizAuthError`, `client.EzvizHp5Client` (Task 2); `const.DOMAIN`, `const.CONF_SERIAL`, `const.CONF_API_URL`, `const.DEFAULT_API_URL` (Task 2).
- Produces: `config_flow.EzvizHp5ConfigFlow` registered for `DOMAIN` via `config_entries.ConfigFlow(domain=DOMAIN)`; config entry `data` keys: `"account"`, `"password"`, `const.CONF_SERIAL`, `const.CONF_API_URL` — these exact keys are read by `__init__.py` in Task 5.

- [ ] **Step 1: Add test dependencies**

Create `requirements_test.txt`:

```
pytest-homeassistant-custom-component
pyezvizapi>=1.0.4
requests>=2.31.0
```

Run: `pip install -r requirements_test.txt`

- [ ] **Step 2: Add the shared test fixture**

Create `tests/conftest.py`:

```python
"""Fixtures for EZVIZ HP5 Gate Controller tests."""

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for every test in this suite."""
    yield
```

- [ ] **Step 3: Write the failing tests for the config flow**

Create `tests/test_config_flow.py`:

```python
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
    assert result["data"] == USER_INPUT


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
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `pytest tests/test_config_flow.py -v`
Expected: FAIL / collection error — `custom_components.ezviz_hp5.config_flow` does not exist yet.

- [ ] **Step 5: Write `config_flow.py`**

```python
"""Config flow for EZVIZ HP5 Gate Controller."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .client import EzvizAuthError, EzvizHp5Client
from .const import CONF_API_URL, CONF_SERIAL, DEFAULT_API_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("account"): str,
        vol.Required("password"): str,
        vol.Required(CONF_SERIAL): str,
        vol.Optional(CONF_API_URL, default=DEFAULT_API_URL): str,
    }
)


async def _validate_login(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Attempt a real EZVIZ login; raises EzvizAuthError on failure."""
    client = EzvizHp5Client(
        account=data["account"],
        password=data["password"],
        serial=data[CONF_SERIAL],
        api_url=data[CONF_API_URL],
    )
    await hass.async_add_executor_job(client.login)
    await hass.async_add_executor_job(client.close)


class EzvizHp5ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EZVIZ HP5 Gate Controller."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SERIAL])
            self._abort_if_unique_id_configured()

            try:
                await _validate_login(self.hass, user_input)
            except EzvizAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error validating EZVIZ credentials")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"EZVIZ HP5 ({user_input[CONF_SERIAL]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauth triggered by ConfigEntryAuthFailed."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None

        if user_input is not None:
            data = {**self._reauth_entry.data, "password": user_input["password"]}
            try:
                await _validate_login(self.hass, data)
            except EzvizAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error validating EZVIZ credentials")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=data
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("password"): str}),
            errors=errors,
        )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_config_flow.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add custom_components/ezviz_hp5/config_flow.py tests/conftest.py tests/test_config_flow.py requirements_test.txt
git commit -m "Add config flow with reauth support"
```

---

## Task 5: Integration setup/unload (`__init__.py`)

**Files:**
- Modify: `custom_components/ezviz_hp5/__init__.py`

**Interfaces:**
- Consumes: `client.EzvizHp5Client` (Task 2); config entry data keys `"account"`, `"password"`, `const.CONF_SERIAL`, `const.CONF_API_URL` (Task 4).
- Produces: `hass.data[DOMAIN][entry.entry_id]` holding the `EzvizHp5Client` instance for that entry — consumed by `lock.py` in Task 6. `PLATFORMS = ["lock"]`.

- [ ] **Step 1: Write `__init__.py`**

```python
"""The EZVIZ HP5 Gate Controller integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import EzvizHp5Client
from .const import CONF_API_URL, CONF_SERIAL, DOMAIN

PLATFORMS = ["lock"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EZVIZ HP5 Gate Controller from a config entry."""
    client = EzvizHp5Client(
        account=entry.data["account"],
        password=entry.data["password"],
        serial=entry.data[CONF_SERIAL],
        api_url=entry.data[CONF_API_URL],
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client: EzvizHp5Client = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(client.close)
    return unload_ok
```

- [ ] **Step 2: Run the full test suite to confirm nothing broke**

Run: `pytest tests/ -v`
Expected: PASS (all tests from Task 2 and Task 4 still pass — `__init__.py` has no dedicated unit test since it is thin wiring covered indirectly by the config flow tests' `async_setup_entry` patches).

- [ ] **Step 3: Commit**

```bash
git add custom_components/ezviz_hp5/__init__.py
git commit -m "Wire up config entry setup/unload"
```

---

## Task 6: Lock platform (`lock.py`)

**Files:**
- Create: `custom_components/ezviz_hp5/lock.py`
- Test: `tests/test_lock.py`

**Interfaces:**
- Consumes: `client.EzvizAuthError`, `client.EzvizCommandError`, `client.EzvizHp5Client` (Task 2); `const.DOMAIN`, `const.UNLOCK_RESET_DELAY` (Task 2); `hass.data[DOMAIN][entry.entry_id]` (Task 5).
- Produces: `lock.EzvizHp5Lock(serial, key, name, unlock_func)` — a `LockEntity` subclass, and its module-level `async_setup_entry(hass, entry, async_add_entities)` platform hook. `client`/`entry` are not stored on the entity: `unlock_func` is a bound method that already closes over the client, and the entity never needs the config entry object directly.

- [ ] **Step 1: Write the failing tests for the lock entity**

Create `tests/test_lock.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_lock.py -v`
Expected: FAIL / collection error — `custom_components.ezviz_hp5.lock` does not exist yet.

- [ ] **Step 3: Write `lock.py`**

```python
"""Lock platform for EZVIZ HP5 Gate Controller."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .client import EzvizAuthError, EzvizCommandError, EzvizHp5Client
from .const import DOMAIN, UNLOCK_RESET_DELAY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EZVIZ HP5 lock entities from a config entry."""
    client: EzvizHp5Client = hass.data[DOMAIN][entry.entry_id]
    serial = entry.data["serial"]

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
        unlock_func,
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
        try:
            await self.hass.async_add_executor_job(self._unlock_func)
        except EzvizAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EzvizCommandError as err:
            raise HomeAssistantError(str(err)) from err

        self._attr_is_locked = False
        self.async_write_ha_state()
        async_call_later(self.hass, UNLOCK_RESET_DELAY, self._reset_to_locked)

    async def _reset_to_locked(self, _now: Any) -> None:
        self._attr_is_locked = True
        self.async_write_ha_state()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_lock.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests from Tasks 2, 4, 6)

- [ ] **Step 6: Commit**

```bash
git add custom_components/ezviz_hp5/lock.py tests/test_lock.py
git commit -m "Add lock platform with impulse unlock behavior"
```

---

## Task 7: Documentation and final repo review

**Files:**
- Modify: `README.md`
- Modify: `README.it.md`

**Interfaces:**
- None (documentation only).

- [ ] **Step 1: Rewrite `README.md`**

```markdown
# EZVIZ HP5 Gate Controller

A Home Assistant custom integration that unlocks the gate/door relay on an
EZVIZ HP5 video intercom via the EZVIZ cloud API, exposed as native `lock`
entities — no separate service, no `rest_command` needed.

The official Home Assistant EZVIZ integration doesn't expose lock/unlock
entities for this device, and the HP5 uses a request format that differs
from what `pyezvizapi`'s built-in unlock support expects. This integration
implements the correct format directly.

## Installation

### Via HACS (custom repository)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add this repository's URL, category **Integration**.
3. Install "EZVIZ HP5 Gate Controller" from HACS.
4. Restart Home Assistant.

### Manual

Copy `custom_components/ezviz_hp5` into your Home Assistant `custom_components`
directory, then restart Home Assistant.

## Configuration

Go to **Settings → Devices & Services → Add Integration**, search for
"EZVIZ HP5 Gate Controller", and enter:

- **EZVIZ account** (email) and **password**
- **Device serial number** — find it in the EZVIZ app: select your HP5
  device, tap the settings gear icon, then "Device Info". It's also
  printed on the physical label/QR code on the back of the device.
- **API URL** (advanced) — leave the default (`apiieu.ezvizlife.com`)
  unless your EZVIZ account is registered on a different region.

Two `lock` entities are created: **Gate** and **Door**. Unlocking sends
the command to EZVIZ; the entity reverts to "locked" locally after a few
seconds, matching the impulse behavior of the physical electric strike.
Locking manually (from the UI) does not send any command to EZVIZ.

If your EZVIZ password changes, Home Assistant will prompt you to
re-authenticate via a repair notification.

## Security

Credentials are stored in Home Assistant's encrypted config entry storage.
No credentials are logged.
```

- [ ] **Step 2: Rewrite `README.it.md`**

```markdown
# EZVIZ HP5 Gate Controller

Un'integrazione custom per Home Assistant che apre il relè del
cancello/porta di un videocitofono EZVIZ HP5 tramite le API cloud EZVIZ,
esposta come entità `lock` native — nessun servizio separato, nessun
`rest_command` necessario.

L'integrazione ufficiale EZVIZ di Home Assistant non espone entità
lock/unlock per questo dispositivo, e l'HP5 usa un formato di richiesta
diverso da quello atteso dal supporto unlock integrato di `pyezvizapi`.
Questa integrazione implementa direttamente il formato corretto.

## Installazione

### Tramite HACS (repository personalizzata)

1. In HACS, vai su **Integrazioni → ⋮ → Repository personalizzate**.
2. Aggiungi l'URL di questo repository, categoria **Integrazione**.
3. Installa "EZVIZ HP5 Gate Controller" da HACS.
4. Riavvia Home Assistant.

### Manuale

Copia `custom_components/ezviz_hp5` nella cartella `custom_components` di
Home Assistant, poi riavvia Home Assistant.

## Configurazione

Vai su **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**,
cerca "EZVIZ HP5 Gate Controller" e inserisci:

- **Account EZVIZ** (email) e **password**
- **Numero di serie del dispositivo** — lo trovi nell'app EZVIZ:
  seleziona il tuo dispositivo HP5, tocca l'icona delle impostazioni
  (ingranaggio), poi "Informazioni dispositivo". È anche stampato
  sull'etichetta fisica/QR code sul retro del dispositivo.
- **URL API** (avanzato) — lascia il valore predefinito
  (`apiieu.ezvizlife.com`) a meno che il tuo account EZVIZ non sia
  registrato in una regione diversa.

Vengono create due entità `lock`: **Gate** e **Door**. Sbloccare invia il
comando a EZVIZ; l'entità torna a "locked" localmente dopo pochi secondi,
replicando il comportamento a impulso dell'elettroserratura fisica.
Bloccare manualmente (dalla UI) non invia alcun comando a EZVIZ.

Se la password EZVIZ cambia, Home Assistant chiederà di reinserire le
credenziali tramite una notifica di riparazione.

## Sicurezza

Le credenziali sono salvate nello storage cifrato delle config entry di
Home Assistant. Nessuna credenziale viene mai loggata.
```

- [ ] **Step 3: Run the full test suite one last time**

Run: `pytest tests/ -v`
Expected: PASS (all tests from Tasks 2, 4, 6)

- [ ] **Step 4: Verify repo cleanliness**

Run: `git status`
Expected: only `README.md` and `README.it.md` modified; no stray legacy files remain (confirms Task 1's removal held).

- [ ] **Step 5: Commit**

```bash
git add README.md README.it.md
git commit -m "Rewrite README for HACS installation and UI configuration"
```
