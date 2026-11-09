# Contract: EZVIZ cloud preset API (observed, not official)

Base: `https://{api_url}` (default `apiieu.ezvizlife.com`). Method POST, `Content-Type: application/x-www-form-urlencoded`.

Common form fields: `sessionId`, `subSerial`, `channelNo=1`, `featureCode`, `clientType=1`, `clientVersion=7.6.7.2915967`, `customno=1000001`, `netType=WIFI`, `osVersion`, `clientNo=` (empty). Subset required: to be verified live.

## List
`POST /api/device/preset/list`
Response (success): `{"data":[{"subSerial":"...","channelNo":1,"index":1,"name":"Sud","picUrl":"..."}],"resultCode":"0","resultDes":"Request successfully"}`

## Go to preset
`POST /api/device/preset/config` + `configPreset=GOTO_PRESET`, `index=<n>`
Response (success): `{"resultCode":"0","resultDes":"Request successfully"}`

## Errors
Any `resultCode != "0"` (or HTTP/JSON failure) => command error. Session-expiry codes are not yet known; they are handled by the generic re-login + single retry.
