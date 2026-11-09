# Contract: Home Assistant surface

- Config flow user step: fields `account`, `password`, `serial`, `api_url` (optional), `device_type` (select: HP5 / PTZ camera (e.g. CB8 Lite), default HP5). Errors: `invalid_auth`, `unknown`; abort `already_configured`.
- PTZ camera entry entities: `button.<preset name>` (press = move to preset), `button.refresh_presets` (press = reload entry).
- Press failure: `HomeAssistantError` with the EZVIZ message; auth failure: start reauth + `ConfigEntryAuthFailed`.
- Patrol example (user-built, not shipped code): automation/script that calls `button.press` on preset buttons with `delay` between steps.
- HP5 entry: unchanged (`lock.gate`, `lock.door`).
