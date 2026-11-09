# Research: Camera Preset Patrol

## R1 - How does the app list and invoke presets?
**Decision**: Reuse the app's legacy form-encoded API on the same host already used for login (`apiieu.ezvizlife.com`, configurable `api_url`):
- `POST /api/device/preset/list` -> `{"data":[{"subSerial","channelNo","index","name","picUrl"}],"resultCode":"0","resultDes":"..."}`
- `POST /api/device/preset/config` with `configPreset=GOTO_PRESET&index=N` -> `{"resultCode":"0","resultDes":"Request successfully"}`

Both are `application/x-www-form-urlencoded` with `sessionId`, `subSerial`, `channelNo=1`, `featureCode` and app metadata (clientType, clientVersion, customno, netType, osVersion). Observed in `.asset/flows.txt` (3 presets: Sud=1, Ovest=2, Nord=3; GOTO issued for each).
**Rationale**: Exact app behaviour; same session as login. **Alternatives**: `pyezvizapi` PTZ helpers - target different endpoints/devices and, as with HP5 unlock, are not verified for this model.
**Open**: Which metadata fields are strictly required - verify live, send the captured set by default. Non-"0" `resultCode` values (expired session etc.) are unknown; treat any non-"0" as failure and let the existing re-login-and-retry-once path handle session expiry.

## R2 - Which Home Assistant entity model?
**Decision**: One `button` entity per preset (`button.press` -> go to preset) + one "Refresh presets" button.
**Rationale**: Presets are momentary actions with no readable state (assumed-state, like the HP5). Buttons are trivially usable in automations/UI. Names come from the camera.
**Alternatives**: `select` (implies a known current position - false); a custom service (not discoverable in UI); `camera` entity (streaming out of scope).

## R3 - Keeping the preset list fresh
**Decision**: Load presets at setup. "Refresh presets" button reloads the config entry, which recreates buttons from a fresh list. No polling.
**Rationale**: Matches "no coordinator, no polling" design; presets change rarely.
**Alternatives**: coordinator polling (wastes battery-camera/cloud calls); dynamic add/remove without reload (more code, little benefit).

## R4 - Setup failure when the list cannot be fetched
**Decision**: Auth failure -> `ConfigEntryAuthFailed` (HA starts reauth); other failure -> `ConfigEntryNotReady` (HA retries). Empty list -> no preset buttons, no error.

## R5 - Battery camera wake-up behaviour
**Decision**: Unknown; plan to verify in quickstart step 4. Surface whatever the cloud returns; do not add wake logic. If the cloud returns an error for a sleeping camera, it appears as a failed button press (FR-005).

## R6 - Config model / backward compatibility
**Decision**: Add `device_type` (`hp5` default, `ptz_camera`) to the user step; missing key == `hp5`. Same `unique_id` = serial. Domain stays `ezviz_hp5`.

## R7 - Client structure
**Decision**: Extract shared login/close/retry into a base class; `EzvizHp5Client` keeps its public API (tests keep passing); add `EzvizCameraClient`.

## R8 - Generality
**Decision**: Device type is the generic `ptz_camera` (UI label "PTZ camera (e.g. CB8 Lite)"). Presets are always read dynamically; channel fixed to 1; `api_url` is user-configurable for non-EU regions. Nothing in code or tests depends on the preset names seen in the capture (use fictional names/serials in tests).
**Rationale**: Other EZVIZ PTZ cameras likely share the preset endpoints, but only the CB8 Lite is verified, so no compatibility is promised.

## R9 - Concurrency and removed presets
**Decision**: A per-client lock serializes calls (patrol scripts can press buttons in quick succession); stale preset entities are removed from the registry on reload.
