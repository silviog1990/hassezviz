# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration (`custom_components/ezviz_hp5/`) that unlocks the gate/door relay on an
EZVIZ HP5 video intercom via the EZVIZ cloud API, exposed as native `lock` entities. Installable via HACS
(custom repository) or by copying the folder into a Home Assistant `custom_components` directory.

This replaces an earlier standalone FastAPI microservice (deleted from this repo) that HA would call via
`rest_command`, since the official HA EZVIZ integration doesn't expose lock/unlock entities for the HP5.
The integration now does the same job natively, with a config flow for setup/reauth instead of a `.env` file.

## Commands

```bash
# Tests (Python 3.14, the interpreter used for day-to-day dev in this repo, does not yet
# support homeassistant's pinned dependencies, hence a separate Python 3.13 test venv)
.venv-test/bin/pytest tests/ -v
```

There is no linter or CI config in this repo (see "Explicitly not done" note below if one is ever added).

## Architecture

- **`const.py`** — `DOMAIN`, config-entry data keys (`CONF_SERIAL`, `CONF_API_URL`), `DEFAULT_API_URL`,
  lock numbers (`LOCK_NO_GATE` / `LOCK_NO_DOOR`), and `UNLOCK_RESET_DELAY` (seconds before a `lock` entity
  reverts from "unlocked" back to "locked" after an impulse-unlock command).
- **`client.py`** — `EzvizHp5Client` holds the EZVIZ session (`login()`/`close()`) and exposes `gate_unlock()`
  / `door_unlock()`. This is the core of the integration; see "Why the unlock call bypasses `pyezvizapi`" below.
- **`config_flow.py`** — `EzvizHp5ConfigFlow`: a `user` step that validates credentials with a real EZVIZ
  login before creating the entry (aborting with `already_configured` if the serial's unique ID already
  exists), and a `reauth`/`reauth_confirm` step pair for credential rotation.
- **`__init__.py`** — `async_setup_entry` builds one `EzvizHp5Client` per config entry, stores it in
  `hass.data[DOMAIN][entry.entry_id]`, and forwards setup to `PLATFORMS = [Platform.LOCK]`.
  `async_unload_entry` unloads the platform and closes the client's session.
- **`lock.py`** — `EzvizHp5Lock(LockEntity)`, two per config entry (gate, door). `async_unlock` runs the
  client's blocking unlock call in the executor, then schedules a callback via `async_call_later` to flip
  the entity back to "locked" after `UNLOCK_RESET_DELAY` — this is what models the physical impulse relay
  (there is no persistent "unlocked" state to poll). `async_lock` is a local no-op: it flips the entity state
  back to "locked" without sending any command to EZVIZ.
- **`manifest.json` / `strings.json` / `translations/{en,it}.json` / `hacs.json`** — HACS/HA integration
  metadata and the user-facing strings for the config flow steps and error messages, in English and Italian.

### Why the unlock call bypasses `pyezvizapi`

`pyezvizapi`'s `remote_unlock()` targets the HP7/HPD7 family and its request format doesn't work on the HP5.
The correct HP5 format was reverse-engineered from the official EZVIZ app's traffic (via mitmproxy) and
differs in three ways, all implemented directly in `client.py`'s `_unlock`:

- URL resource identifier is the literal string `"Video"`, not a UUID
- request body is wrapped in `{"value": {...}}`
- a `featureCode` header (MD5 hash of the calling machine's MAC address, computed once at import time as
  `FEATURE_CODE` from `uuid.getnode()`) must be present — note this means `FEATURE_CODE` changes if the HA
  host/container is ever recreated with a different MAC, which is worth remembering if EZVIZ ever starts
  rejecting `bindCode` after an environment change

`pyezvizapi` is still used, but only for `EzvizClient.login()` / session management — the actual unlock PUT
request is built and sent by hand with `requests`.

`lockNo=1` is the gate, `lockNo=2` is the door (`LOCK_NO_GATE` / `LOCK_NO_DOOR` constants).

### Lock (close) command is intentionally never called

A `_lock` method exists in `client.py` as commented-out reference code (request format verified against app
traffic) but is never wired up to a `gate_lock`/`door_lock` method or exposed anywhere. The `lock.py` entity's
"lock" action is purely local UI state, never an EZVIZ API call — see `LockEntity.async_lock` above. If ever
re-enabling a real lock/close command, uncomment `_lock` and add the corresponding public method deliberately;
don't delete the commented block, it's kept in sync as reference.

### Session/auth design — no coordinator, no polling

This integration has no `DataUpdateCoordinator` and does not poll the device. Each `EzvizHp5Client` keeps
`_session_id`/`_user_id`/`_authenticated` in memory for as long as the config entry is loaded; there's no
persistence across HA restarts. Every gate/door call goes through `_execute_with_retry`: if not authenticated,
it logs in first; if the sync call raises, it closes the session, re-logs in, and retries **once** before
giving up. `iot_class` in `manifest.json` is `assumed_state` (matching `_attr_assumed_state = True` on the
lock entities) because there's no way to read back the physical lock state from EZVIZ.

### Reauth flow

If a command fails due to invalid credentials, `EzvizAuthError` is raised inside `lock.py`'s `async_unlock`.
Raising `ConfigEntryAuthFailed` alone does **not** trigger HA's reauth repair flow when it originates from an
entity service call (only `ConfigEntry.async_setup`/a coordinator does that automatically) — so `async_unlock`
explicitly calls `self.platform.config_entry.async_start_reauth(self.hass)` before raising
`ConfigEntryAuthFailed`. The config flow's `async_step_reauth`/`async_step_reauth_confirm` then re-validate a
new password and use `self.async_update_reload_and_abort(...)` to update the entry and reload it.

## Security notes specific to this project

- The integration has no authentication of its own beyond what HA's config entry system provides — it should
  only ever talk to the EZVIZ cloud API over HTTPS; there's no local network exposure to worry about since
  there's no standalone server anymore.
- Credentials are stored in Home Assistant's config entry storage (`.storage/core.config_entries`), never in
  YAML, and must never be logged. Note `.storage` is plaintext JSON on disk (not encrypted at rest) — that's
  an HA platform property, not something this integration controls.
- `.venv-test/`, `venv/`, and other virtualenvs are gitignored (`.venv*/`, `venv/` in `.gitignore`) — never
  force-add them.

## Explicitly not done (by design, not an oversight)

- No GitHub Actions CI (hassfest/HACS validation workflows) exists yet.
- `manifest.json`'s `documentation`/`issue_tracker`/`codeowners` URLs are placeholders pending repo/GitHub
  identity confirmation from the owner.
