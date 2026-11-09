# hassezviz (formerly "EZVIZ HP5 Gate Controller")

A Home Assistant custom integration for EZVIZ devices that the official
integration does not cover well:

- **EZVIZ HP5 video intercom** — unlocks the gate/door relay via the EZVIZ
  cloud API, exposed as native `lock` entities (no separate service, no
  `rest_command` needed).
- **EZVIZ PTZ cameras (e.g. CB8 Lite)** — lists the camera presets and lets
  you trigger them from Home Assistant, so you can build a patrol even on
  battery cameras.

The official Home Assistant EZVIZ integration doesn't expose lock/unlock
entities for this device, and the HP5 uses a request format that differs
from what `pyezvizapi`'s built-in unlock support expects. This integration
implements the correct format directly.

## Installation

### Via HACS (custom repository)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=silviog1990&repository=hassezviz&category=integration)

Click the badge above to add this repository to HACS on your own instance, or do it manually:

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/silviog1990/hassezviz`, category **Integration**.
3. Install "hassezviz" (previously listed as "EZVIZ HP5 Gate Controller") from HACS.
4. Restart Home Assistant.

### Manual

Copy `custom_components/ezviz_hp5` into your Home Assistant `custom_components`
directory, then restart Home Assistant.

## Configuration

Go to **Settings → Devices & Services → Add Integration**, search for
"hassezviz" (previously "EZVIZ HP5 Gate Controller"), and enter:

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

## PTZ cameras: preset buttons and patrol (e.g. CB8 Lite)

Choose **PTZ camera** as device type when adding the integration. The
integration reads the presets saved on the camera in the EZVIZ app and
creates one `button` per preset (named like the preset) plus a
**Refresh presets** button. Pressing a preset button moves the camera
there. After adding, renaming or deleting presets in the EZVIZ app, press
**Refresh presets** (or reload the integration) to update the list.

A patrol — useful for battery cameras that cannot patrol on their own —
is a plain script or automation:

```yaml
script:
  camera_patrol:
    sequence:
      - action: button.press
        target: {entity_id: button.ezviz_ptz_camera_xxx_entrance}
      - delay: "00:00:20"
      - action: button.press
        target: {entity_id: button.ezviz_ptz_camera_xxx_garden}
      - delay: "00:00:20"
      - action: button.press
        target: {entity_id: button.ezviz_ptz_camera_xxx_street}
```

Limits: cloud only; only channel 1 is supported; verified on the CB8 Lite
only; presets are created in the EZVIZ app. If your EZVIZ account is not
on the European server, set the **API URL** accordingly.

## Security

Credentials are stored in Home Assistant's config entry storage (`.storage`),
never in YAML and never logged.
