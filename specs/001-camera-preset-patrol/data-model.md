# Data Model

## Config entry data (extended)
| Field | Type | Notes |
|-------|------|-------|
| account, password, serial, api_url | str | unchanged |
| device_type | `"hp5"` \| `"ptz_camera"` | new; absent => `hp5` |

`unique_id` = serial. Reauth only updates `password`.

## Preset (runtime, not persisted)
| Field | Source | Notes |
|-------|--------|-------|
| index | `index` | int >= 1, unique per camera; used to invoke |
| name | `name` | shown as entity name |
| channel_no | `channelNo` | always 1 here |
| pic_url | `picUrl` | ignored (thumbnails out of scope) |

Held in `hass.data[DOMAIN][entry_id]` next to the client; replaced wholesale on reload.

## Entities (PTZ camera entry)
- `button` per preset: unique_id `{serial}_preset_{index}`, name = preset name.
- `button` "Refresh presets": unique_id `{serial}_refresh_presets`.
- All grouped in one device (`identifiers={(DOMAIN, serial)}`, model "PTZ Camera").

## State transitions
None: buttons are stateless; a press is request -> success | error.
