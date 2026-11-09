# Quickstart: validating the feature

1. **Tests**: `.venv-test/bin/pytest tests/ -v` - all green, including new client/config-flow/button tests and unchanged HP5 tests.
2. **Install**: copy `custom_components/ezviz_hp5` into HA, restart.
3. **Add CB8 Lite**: Settings > Devices & services > Add > EZVIZ HP5 Gate Controller; choose device type CB8 Lite, enter account/serial. Expect one button per preset in the EZVIZ app plus "Refresh presets".
4. **Invoke**: press a preset button; the camera turns to the same view as in the app. Note delay and behaviour when the camera is asleep (open question R5) and which form fields are really required (contract note).
5. **Refresh**: rename a preset in the EZVIZ app, press "Refresh presets"; the name updates.
6. **Patrol**: create a script pressing preset 1, delay 20 s, preset 2, delay 20 s, preset 3; run it and confirm order.
7. **HP5 regression**: an existing HP5 entry still unlocks gate/door.
