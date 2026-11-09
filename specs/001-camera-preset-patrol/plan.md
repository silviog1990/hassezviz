# Implementation Plan: Camera Preset Patrol for PTZ Cameras (verified on CB8 Lite)

**Branch**: `001-camera-preset-patrol` | **Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-camera-preset-patrol/spec.md`

## Summary

Add CB8 Lite support to the existing `ezviz_hp5` Home Assistant integration. A config entry gets a device type (`hp5` or the generic `ptz_camera`, verified only on the CB8 Lite). For a PTZ camera entry the integration fetches the camera's presets from the EZVIZ cloud and exposes one `button` entity per preset (pressing it moves the camera to that preset), plus a "Refresh presets" button. Patrols are plain HA automations/scripts pressing these buttons in sequence. HP5 entries are untouched. Request formats were taken from the mitmproxy capture (see [research.md](research.md)).

## Technical Context

**Language/Version**: Python 3.13 (test venv `.venv-test`; HA-compatible)

**Primary Dependencies**: Home Assistant core, `pyezvizapi>=1.0.4` (login/session only), `requests` (direct calls, as in HP5 unlock)

**Storage**: Config entry data only (adds `device_type`); no persistent preset cache

**Testing**: pytest + pytest-homeassistant-custom-component (existing `tests/`), HTTP mocked

**Target Platform**: Home Assistant (HACS custom integration)

**Project Type**: Home Assistant custom integration

**Performance Goals**: Preset command returns within ~10 s (SC-002); 15 s HTTP timeout as for unlock

**Constraints**: Cloud-only, no polling, no coordinator; credentials never logged; HP5 behaviour unchanged

**Scale/Scope**: One camera per entry, a handful (<=~10) of presets

## Constitution Check

`.specify/memory/constitution.md` is the unfilled template, so no gates are defined. Applying the project's CLAUDE.md rules instead: no polling/coordinator (kept), credentials not logged (kept), HP5 untouched (kept), EN+IT strings (planned), commented `_lock` reference code left in place (kept). Post-design re-check: pass.

## Project Structure

### Documentation (this feature)

```text
specs/001-camera-preset-patrol/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ezviz-preset-api.md
│   └── ha-entities.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
custom_components/ezviz_hp5/
├── const.py          # + CONF_DEVICE_TYPE, DEVICE_TYPE_HP5/PTZ_CAMERA
├── client.py         # extract shared session base; + EzvizCameraClient (list_presets, goto_preset)
├── config_flow.py    # + device type field; client chosen by type; title per model
├── __init__.py       # build client by type; PLATFORMS depends on type; load presets for camera
├── lock.py           # unchanged (HP5 only)
├── button.py         # NEW: preset buttons + refresh button (CB8 Lite only)
├── strings.json, translations/{en,it}.json   # new field/labels/errors
tests/
├── test_client.py, test_config_flow.py, test_init.py   # extended
└── test_button.py    # NEW
```

**Structure Decision**: Keep the single integration and domain `ezviz_hp5` (the rename to hassezviz is a separate task; changing the domain would break existing entries). Entries with no `device_type` are treated as `hp5`, so no migration is needed.

## Complexity Tracking

No constitution violations to justify.
