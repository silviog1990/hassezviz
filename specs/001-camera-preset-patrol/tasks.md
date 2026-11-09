---

description: "Task list for Camera Preset Patrol (CB8 Lite)"
---

# Tasks: Camera Preset Patrol for PTZ Cameras (verified on CB8 Lite)

**Input**: Design documents from `/specs/001-camera-preset-patrol/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: Included, because the repo already has a pytest suite per module (`tests/test_*.py`); run with `.venv-test/bin/pytest tests/ -v`. HTTP is always mocked.

**Organization**: Grouped by user story. Source root is `custom_components/ezviz_hp5/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on incomplete tasks)
- **[Story]**: US1 move to preset, US2 list presets, US3 patrol/refresh, US4 HP5 unchanged

## Phase 1: Setup

- [X] T001 Add constants to `custom_components/ezviz_hp5/const.py`: `CONF_DEVICE_TYPE = "device_type"`, `DEVICE_TYPE_HP5 = "hp5"`, `DEVICE_TYPE_PTZ_CAMERA = "ptz_camera"`, `DEFAULT_DEVICE_TYPE = DEVICE_TYPE_HP5`, `DEFAULT_CHANNEL_NO = 1`

---

## Phase 2: Foundational (blocks all stories)

- [X] T002 In `custom_components/ezviz_hp5/client.py`, extract the shared `__init__`, `authenticated`, `login`, `close` and `_execute_with_retry` into a base class `EzvizBaseClient`; make `EzvizHp5Client(EzvizBaseClient)` keep `_unlock`, `gate_unlock`, `door_unlock` and the commented-out `_lock` block unchanged. Public behaviour and names used by existing tests must not change.
- [X] T003 Add `EzvizCameraClient(EzvizBaseClient)` in `custom_components/ezviz_hp5/client.py` with a helper `_post_form(path, extra_fields)` that POSTs `application/x-www-form-urlencoded` to `https://{api_url}{path}` with `sessionId`, `subSerial`, `channelNo=1`, `featureCode=FEATURE_CODE`, `clientType=1`, `clientVersion=7.6.7.2915967`, `customno=1000001`, `netType=WIFI`, `osVersion`, `clientNo=` (see `contracts/ezviz-preset-api.md`), timeout 15 s, returns parsed JSON, raises `EzvizCommandError` if `resultCode != "0"` or the response is not valid JSON. Never log `sessionId`.
- [X] T004 [P] Add a "client factory" in `custom_components/ezviz_hp5/__init__.py`: build `EzvizCameraClient` when `entry.data.get(CONF_DEVICE_TYPE, DEFAULT_DEVICE_TYPE) == DEVICE_TYPE_PTZ_CAMERA`, else `EzvizHp5Client`; expose a helper `platforms_for(entry)` returning `[Platform.LOCK]` for HP5 (the `button` platform is wired in by T010, once `button.py` exists) and use it in `async_setup_entry`/`async_unload_entry`.
- [X] T005 [P] Update `custom_components/ezviz_hp5/config_flow.py`: add `vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPE_HP5)` as a selector with options `hp5`/`ptz_camera` (labels "HP5" and "PTZ camera (e.g. CB8 Lite)") to `STEP_USER_DATA_SCHEMA`; `_validate_login` uses the matching client class; entry title is `EZVIZ HP5 ({serial})` or `EZVIZ PTZ Camera ({serial})`; reauth keeps `device_type` from the existing entry data.

**Checkpoint**: HP5 flow and all pre-existing tests still work; PTZ camera entries are recognised by the config flow and client factory but get no platforms until T010.

---

## Phase 3: User Story 2 - See existing presets (P1)

**Goal**: A PTZ camera entry shows one entity per preset, named like in the EZVIZ app.

**Independent Test**: Mock the list response (three fictional presets); setting up the entry yields three buttons with those names; an empty list yields none and no error.

- [X] T006 [P] [US2] Add `tests/test_client.py` cases for `EzvizCameraClient.list_presets()`: parses the captured shape `{"data":[{"subSerial","channelNo","index","name","picUrl"}],"resultCode":"0"}` into `[Preset(index, name)]`; empty `data` -> `[]`; `resultCode != "0"` -> `EzvizCommandError`; retried once after re-login (reuse the existing retry-test style).
- [X] T007 [P] [US2] Add `tests/test_button.py` with a fixture that sets up a `ptz_camera` entry with mocked presets; assert three `button` entities with fictional names (e.g. Entrance/Garden/Street, not the captured ones) and unique IDs `{serial}_preset_{index}`; assert zero preset buttons for an empty list.
- [X] T008 [US2] Implement in `custom_components/ezviz_hp5/client.py`: a frozen dataclass `Preset(index: int, name: str)` (index: int >= 1, unique per camera; ignore `picUrl`) and `EzvizCameraClient.list_presets()` using `_execute_with_retry` and `POST /api/device/preset/list`.
- [X] T009 [US2] In `custom_components/ezviz_hp5/__init__.py`, for PTZ camera entries call `list_presets` in the executor before forwarding platforms and store `{"client": client, "presets": presets}` for that entry; `EzvizAuthError` -> `ConfigEntryAuthFailed`, other `EzvizCommandError`/network errors -> `ConfigEntryNotReady`. Keep HP5 storing the bare client exactly as today (adjust `async_unload_entry` accordingly).
- [X] T010 [US2] Create `custom_components/ezviz_hp5/button.py` with `async_setup_entry` adding one `EzvizPresetButton` per preset: `_attr_has_entity_name = True`, `_attr_name = preset.name`, `_attr_unique_id = f"{serial}_preset_{index}"`, shared `DeviceInfo(identifiers={(DOMAIN, serial)}, name=f"EZVIZ PTZ Camera ({serial})", manufacturer="EZVIZ", model="PTZ Camera")`. `async_press` is a stub here (implemented in T013). Also make `platforms_for(entry)` in `__init__.py` return `[Platform.BUTTON]` for PTZ camera entries (this is the point where the `button` platform starts being forwarded).

---

## Phase 4: User Story 1 - Move camera to a preset (P1)

**Goal**: Pressing a preset button turns the camera to that preset; failures are visible.

**Independent Test**: Press a preset button with a mocked success response -> a `GOTO_PRESET` request with the right `index` is sent; with an error response -> `HomeAssistantError`.

- [X] T011 [P] [US1] Add `tests/test_client.py` cases for `EzvizCameraClient.goto_preset(index)`: request path `/api/device/preset/config`, form body contains `configPreset=GOTO_PRESET` and `index=<n>`; success on `resultCode "0"`; `EzvizCommandError` otherwise; one re-login retry; `EzvizAuthError` when re-login fails.
- [X] T012 [P] [US1] Add `tests/test_button.py` cases: pressing a preset button calls `goto_preset(index)`; `EzvizCommandError` -> `HomeAssistantError`; `EzvizAuthError` -> `async_start_reauth` called and `ConfigEntryAuthFailed` raised (mirror `tests/test_lock.py`).
- [X] T013 [US1] Implement `EzvizCameraClient.goto_preset(index: int)` in `custom_components/ezviz_hp5/client.py` (POST `/api/device/preset/config` with `configPreset=GOTO_PRESET`, `index`) and the real `EzvizPresetButton.async_press` in `custom_components/ezviz_hp5/button.py` (run in executor, same error mapping and reauth handling as `lock.py`'s `async_unlock`).

- [X] T026 [US1] Serialize EZVIZ calls per client: add a `threading.Lock` in `EzvizBaseClient` held around `_execute_with_retry`, so rapid or parallel button presses (patrol scripts) cannot race on the shared session during re-login; add a test in `tests/test_client.py` running two `goto_preset` calls concurrently with a forced first failure and asserting both complete with a single re-login.

---

## Phase 5: User Story 3 - Patrol via automations (P2)

**Goal**: Users can refresh the preset list and compose a patrol from standard automations.

**Independent Test**: Press "Refresh presets" after the mocked list changes; entities reflect the new list. A sample script pressing buttons with delays is documented.

- [X] T014 [P] [US3] Add `tests/test_button.py` case: after changing the mocked list (rename + add one), pressing the refresh button reloads the entry and the new button set matches.
- [X] T015 [US3] Add `EzvizRefreshPresetsButton` to `custom_components/ezviz_hp5/button.py` (unique_id `{serial}_refresh_presets`, name "Refresh presets"; `async_press` calls `hass.config_entries.async_reload(entry.entry_id)`), added alongside preset buttons.
- [X] T016 [P] [US3] Document in `README.md` and `README.it.md`: how to add a PTZ camera (device type, serial), a note that `api_url` must be changed for non-European accounts, the limits (cloud only, channel 1 only, verified on CB8 Lite only, presets are created in the EZVIZ app), and a "Patrol with automations" example script (`button.press` on each preset, `delay` between).

- [X] T025 [US3] Handle presets deleted in the EZVIZ app: in `custom_components/ezviz_hp5/button.py` setup, remove preset button entries from the entity registry whose `{serial}_preset_{index}` unique ID is no longer in the fresh list (so they do not linger as unavailable orphans); add a case to `tests/test_button.py` (preset removed from the mocked list -> its entity is gone after refresh, others remain). Failure when pressing a preset that no longer exists on the camera must still raise `HomeAssistantError` (covered by T012).

---

## Phase 6: User Story 4 - HP5 unchanged (P1)

**Goal**: Existing HP5 entries and tests keep working; HP5 and CB8 Lite coexist.

**Independent Test**: Full existing suite passes untouched; an entry without `device_type` behaves as HP5.

- [X] T017 [P] [US4] Add `tests/test_init.py` cases: legacy entry data without `device_type` sets up `lock` entities only; a `ptz_camera` entry sets up `button` entities only; both entries loaded together do not interfere (distinct serials).
- [X] T018 [P] [US4] Add `tests/test_config_flow.py` cases: user step with `device_type=ptz_camera` creates an entry titled `EZVIZ PTZ Camera (<serial>)` storing `device_type`; default is `hp5`; `already_configured` still aborts on duplicate serial; reauth preserves `device_type`.
- [X] T019 [US4] Run `.venv-test/bin/pytest tests/ -v` and fix any regression in pre-existing HP5 tests (`test_client.py`, `test_lock.py`, `test_init.py`, `test_config_flow.py`) caused by T002-T005/T009.

---

## Phase 7: Polish & Cross-Cutting

- [X] T020 [P] Update `custom_components/ezviz_hp5/strings.json`, `translations/en.json`, `translations/it.json`: `device_type` field label and option names (HP5 / PTZ camera (e.g. CB8 Lite)), updated user-step description mentioning both devices; keep existing keys.
- [X] T021 [P] Update `custom_components/ezviz_hp5/manifest.json` and `hacs.json` name/description wording to cover both devices (keep `domain` = `ezviz_hp5`), and bump `version` to `0.2.0`.
- [X] T022 [P] Update `CLAUDE.md` architecture section: device types, `EzvizBaseClient`/`EzvizCameraClient`, `button.py`, preset endpoints and the "no polling, refresh = reload" decision.
- [ ] T023 Live validation on a real CB8 Lite following `quickstart.md` steps 3-7; record findings (required form fields, behaviour when the camera is asleep, session-expiry `resultCode`, preset change time, and the outcome of ~20 consecutive presses for SC-002/SC-004) in `research.md` R1/R5 and trim the `_post_form` fields if some are unnecessary.
- [X] T024 Verify no credentials or `sessionId` appear in log output at any level (grep `_LOGGER` calls in `client.py`, `button.py`).

---

## Dependencies & Execution Order

- T026 (US1) follows T013; T025 (US3) follows T015. Both were added after the first analysis, hence their out-of-sequence IDs.
- Phase 1 -> Phase 2 -> stories. Phase 2: T002 -> T003; T004 and T005 parallel after T001 (T004 touches `__init__.py`, T005 `config_flow.py`).
- US2 (T006-T010) before US1 (needs the button class and stored presets). US3 depends on US2 (button.py) and can run after US1. US4 tests (T017, T018) can be written after Phase 2 and verified at the end.
- Polish after all stories; T023 needs T013 and T015 complete.

## Parallel Examples

- After T003: T004 and T005 together.
- US2: T006 and T007 together (tests, different files), then T008 -> T009 -> T010.
- US1: T011 and T012 together, then T013.
- Polish: T020, T021, T022 together.

## Implementation Strategy

- **MVP**: Phases 1-4 (US2 + US1): PTZ camera entry with preset buttons that move the camera. Validate with T023 steps 3-4 before continuing.
- Then US3 (refresh + patrol docs), then US4 verification, then polish.
- Commit per phase on branch `001-camera-preset-patrol`; merge to `main` only after live validation (T023).
