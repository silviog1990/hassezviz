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
