# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small FastAPI microservice that unlocks the gate/door relay on an EZVIZ HP5 video intercom via the EZVIZ cloud API. Intended to be called by Home Assistant's `rest_command` integration (or any HTTP client) since the official HA EZVIZ integration doesn't expose lock/unlock entities.

## Commands

```bash
# Local run (requires a filled-in .env, see .env.example)
pip install -r requirements.txt
python app.py

# Docker
./docker_build.sh    # cross-builds linux/amd64 image, tags amd64-<git-sha> and amd64-latest; reads REGISTRY from .env.build
./docker_push.sh     # pushes both tags to ${REGISTRY}
./docker_run.sh      # pulls amd64-latest from ${REGISTRY} and runs it, reading credentials from .env
docker compose up -d # alternative: build+run locally, reads .env automatically
```

There is no test suite, linter, or CI config in this repo.

## Architecture

Three files carry all the logic:

- **`config.py`** — loads required (`EZVIZ_ACCOUNT`, `EZVIZ_PASSWORD`, `EZVIZ_SERIAL`) and optional (`EZVIZ_API_URL`, `API_HOST`, `API_PORT`) env vars via `python-dotenv`. Missing required vars cause an immediate `sys.exit(1)`, not an exception — keep that behavior if refactoring.
- **`ezviz_service.py`** — `EzvizGateService` holds the EZVIZ session and does the unlock call. This is the core of the project.
- **`app.py`** — FastAPI app wiring: `lifespan` logs in on startup (best-effort — failure just logs, since `_execute_with_retry` re-authenticates on demand) and closes the session on shutdown; endpoints translate `RuntimeError` → HTTP 401, anything else → HTTP 500.

### Why the unlock call bypasses `pyezvizapi`

`pyezvizapi`'s `remote_unlock()` targets the HP7/HPD7 family and its request format doesn't work on the HP5. The correct HP5 format was reverse-engineered from the official EZVIZ app's traffic (via mitmproxy) and differs in three ways, all implemented directly in `ezviz_service.py._unlock_sync`:

- URL resource identifier is the literal string `"Video"`, not a UUID
- request body is wrapped in `{"value": {...}}`
- a `featureCode` header (MD5 hash of the calling machine's MAC address, computed once at import time as `FEATURE_CODE`) must be present

`pyezvizapi` is still used, but only for `EzvizClient.login()` / session management — the actual unlock PUT request is built and sent by hand with `requests`.

`lockNo=1` is the gate, `lockNo=2` is the door (`LOCK_NO_GATE` / `LOCK_NO_DOOR` constants).

### Session/auth flow

1. On startup, `lifespan` calls `service.login()` once (failure is logged, not fatal — the service will retry lazily).
2. `EzvizGateService` keeps `_session_id`/`_user_id`/`_authenticated` in memory for the process lifetime; there's no persistence across restarts.
3. Every gate/door call goes through `_execute_with_retry`: if not authenticated, logs in first; if the sync call raises, it closes the session, re-logs in, and retries **once** before giving up.
4. `/health` reports `service.authenticated` so callers (e.g. HA) can surface auth failures.

### Lock endpoints are intentionally disabled

`/gate/lock` and `/door/lock` (and their `_lock_sync`/`gate_lock`/`door_lock` implementations) exist but are commented out in both `app.py` and `ezviz_service.py`. If re-enabling them, uncomment both the route and the corresponding service method/import together — they're kept in sync as commented pairs, not deleted, because the request format was already verified against app traffic.

### Docker build/tag scheme

`docker_build.sh` always cross-builds for `linux/amd64` (development happens on Apple Silicon, deploy target is an amd64 Linux host). Each build produces an immutable `amd64-<git-short-sha>` tag (or a timestamp if there's no git history) plus a moving `amd64-latest` tag, so a specific build can be pinned on the deploy host via `TAG=amd64-<version> ./docker_run.sh`.

## Security notes specific to this project

- The service has no authentication of its own — it must only ever be exposed on the local network, never on the internet.
- `.env`, `.env.build`, all `*.json` (session token, device list), and `appunti.txt` are gitignored because they can contain live credentials/tokens — never force-add or commit these.
- Credentials are read from env vars only and must never be logged.
