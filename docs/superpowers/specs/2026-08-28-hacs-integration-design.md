# EZVIZ HP5 Gate Controller — HACS Custom Integration Design

Date: 2026-08-28
Status: Approved for planning

## Goal

Replace the current standalone FastAPI microservice with a native Home
Assistant custom integration, installable via HACS, that exposes
gate/door unlock control for the EZVIZ HP5 intercom directly as HA
`lock` entities — no separate Docker service, no `rest_command`
plumbing, credentials configured through the HA UI.

## Scope decision

The FastAPI microservice is fully replaced, not kept alongside. All
Docker/FastAPI-specific files are removed from the repo:
`app.py`, `ezviz_service.py`, `config.py`, `Dockerfile`, `docker_build.sh`,
`docker_push.sh`, `docker_run.sh`, `docker-compose.yml`,
`requirements.txt`, `ezviz_token.json`, `devices.json`, `appunti.txt`,
`.env`, `.env.build`, `.env.example`, `.env.build.example`.

The repo becomes exclusively a HACS-distributed custom integration.

## Repository structure

```
custom_components/ezviz_hp5/
    __init__.py            # async_setup_entry / async_unload_entry, builds EzvizHp5Client
    manifest.json
    config_flow.py          # ConfigFlow (user step) + reauth step
    const.py                 # DOMAIN, CONF_* keys, defaults, timeouts
    client.py                 # ported EzvizGateService logic (renamed EzvizHp5Client)
    lock.py                   # Lock platform: gate + door entities
    strings.json
    translations/
        en.json
        it.json
hacs.json
README.md
README.it.md
tests/
    conftest.py
    test_config_flow.py
    test_client.py
```

## Config flow

Single `user` step, form fields:
- `account` (email)
- `password`
- `serial` (EZVIZ device serial) — help text explains where to find it:
  in the EZVIZ app under *Device → settings (⚙️) → Device Info → Serial
  Number*, or on the physical label/QR code on the back of the HP5.
  Same explanation is duplicated in the README.
- `api_url` (advanced/optional, default `apiieu.ezvizlife.com`)

On submit, the flow performs a real login against EZVIZ to validate
credentials before creating the entry. Login failure surfaces
`invalid_auth` on the form instead of a generic exception. Unexpected
errors surface as `unknown`.

`unique_id` = `serial`, preventing duplicate entries for the same
intercom and enabling multiple devices/accounts to be configured
independently.

### Reauth flow

If a command fails due to invalid credentials, entities raise
`ConfigEntryAuthFailed`. Home Assistant surfaces its standard
reauth repair flow: a form pre-filled with the existing
account/serial, asking only for a new `password`. On success the
config entry is updated and reloaded.

## Session management

No `DataUpdateCoordinator`, no background polling. Each config entry
owns one `EzvizHp5Client` instance stored in
`hass.data[DOMAIN][entry.entry_id]`, shared by both lock entities.

- Login is lazy: first command triggers login if not already
  authenticated.
- On command failure, the client closes the session, re-logs in, and
  retries once (ported unchanged from `_execute_with_retry`).
- If retry still fails with an auth-shaped error, the entity raises
  `ConfigEntryAuthFailed`; other failures raise `HomeAssistantError`
  with the EZVIZ error message.

This mirrors the already-proven behavior of the current
`EzvizGateService`/`_execute_with_retry`, chosen over a polling
coordinator to avoid unnecessary background cloud API calls — there is
no real state to poll, only on-demand commands.

## Client (`client.py`)

Direct port of `EzvizGateService` → `EzvizHp5Client`:
- `_login_sync` / `login()` — unchanged, uses `pyezvizapi.EzvizClient` for
  session management only.
- `_unlock_sync(lock_no)` — unchanged hand-built PUT request: URL uses
  literal `"Video"` resource id, body wrapped in `{"value": {...}}},
  `featureCode` header (MD5 of host MAC, computed once at import as
  `FEATURE_CODE`).
- `_execute_with_retry` — unchanged retry-once-with-relogin behavior.
- `gate_unlock()` / `door_unlock()` — unchanged, `lockNo=1` / `lockNo=2`.
- `_lock_sync` and `gate_lock`/`door_lock` are **not** ported as active
  code — kept as commented-out code in `client.py` for reference,
  consistent with how the original repo preserved the
  already-verified-but-unused lock request format.
- All blocking calls (`requests`, `pyezvizapi`) still run via
  `asyncio.to_thread`, required for HA's event loop.

Note: `FEATURE_CODE` is now derived from the MAC address of the host
running Home Assistant (container/HAOS), not a dedicated server — this
is fine, the value only needs to be a stable per-client identifier for
EZVIZ, not tied to anything specific.

## Entities (`lock.py`)

Per config entry, two `LockEntity` instances — **Gate** and **Door** —
grouped under a single HA device named `EZVIZ HP5 (<serial>)`.

Behavior:
- Initial/default state: `locked`.
- `async_unlock()` calls `client.gate_unlock()` / `client.door_unlock()`.
  On success, state becomes `unlocked`.
- A fixed 5-second timer (`async_call_later`) then resets state back to
  `locked` locally, without any EZVIZ call — simulating the impulse
  behavior of the physical electric strike.
- `async_lock()` (user-triggered manual "lock" command): no EZVIZ call
  is made; state is set back to `locked` immediately. This reflects
  that the HP5 lock command is not exposed by this integration.
- Errors: `RuntimeError` from the client (EZVIZ API error / not
  authenticated) is translated to `HomeAssistantError` with a
  human-readable message, or to `ConfigEntryAuthFailed` when the
  failure is credential-related (post-retry).

## HACS / manifest metadata

- `manifest.json`: `domain: "ezviz_hp5"`, `name: "EZVIZ HP5 Gate
  Controller"`, `codeowners`, `requirements: ["pyezvizapi>=1.0.4",
  "requests>=2.31.0"]`, `iot_class: "assumed_state"`, `config_flow:
  true`, `version` tracking release tags, `integration_type: "hub"`.
- `hacs.json` (repo root): `{"name": "EZVIZ HP5 Gate Controller",
  "render_readme": true}`. Standard `custom_components/<domain>/`
  layout, no `content_in_root` needed.
- `README.md` / `README.it.md` rewritten: HACS custom-repository
  installation instructions (until/if accepted into the default HACS
  store), then UI setup via *Settings → Devices & Services → Add
  Integration*, serial-number lookup instructions, no more
  Docker/env-var content.
- `.gitignore` simplified: drop entries specific to the old service's
  `.env`/token files; credentials now live in HA's encrypted config
  entry storage.

## Testing

Basic test suite using `pytest-homeassistant-custom-component`:
- `test_config_flow.py`: successful setup, invalid credentials
  (`invalid_auth`), reauth flow success.
- `test_client.py`: `gate_unlock`/`door_unlock` success, EZVIZ API
  error surfaced as `RuntimeError`, retry-after-failure re-login path.

HTTP calls (`requests.put`, `pyezvizapi` login) are mocked; no real
network access in tests.

## Out of scope (YAGNI, not building)

- Lock (close) command — command format stays commented-out reference
  code only, never called.
- DataUpdateCoordinator / periodic polling of auth state.
- Options flow for changing settings after initial setup (can be added
  later if needed).
- Multi-language beyond `en`/`it`.
