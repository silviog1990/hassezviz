# Feature Specification: Camera Preset Patrol for PTZ Cameras (verified on CB8 Lite)

**Feature Branch**: `001-camera-preset-patrol`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Add support for the EZVIZ CB8 Lite camera to the existing integration (the project is being renamed to hassezviz; its GitHub repository is currently named ezviz-hp5-homeassistant-integration). Goal: list the camera's existing presets and invoke them from Home Assistant, so that a 'patrol' can be built with automations, which the camera does not offer natively because it is battery powered. Existing HP5 behaviour must remain unchanged. A captured app traffic flow is available in .asset/flows.txt."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Move the camera to a saved preset from Home Assistant (Priority: P1)

As a Home Assistant user with a CB8 Lite, I want to point the camera at one of the presets I saved in the EZVIZ app (e.g. "Sud", "Ovest", "Nord") by triggering it from Home Assistant, so I can control where the camera looks without opening the EZVIZ app.

**Why this priority**: Invoking a preset is the core capability; the list and the patrol both depend on it.

**Independent Test**: With a CB8 Lite configured, trigger one preset from Home Assistant and verify the camera physically turns to the same view the EZVIZ app shows for that preset.

**Acceptance Scenarios**:

1. **Given** the camera has presets saved in the EZVIZ app, **When** the user triggers a preset in Home Assistant, **Then** the camera moves to that preset's position.
2. **Given** a preset is triggered, **When** the EZVIZ cloud rejects or cannot deliver the request, **Then** Home Assistant shows a clear error.

---

### User Story 2 - See the camera's existing presets in Home Assistant (Priority: P1)

As a user, I want Home Assistant to show the list of presets already defined on my camera, using their names, so I can pick them in the UI and in automations without knowing numeric indexes.

**Why this priority**: Required to make presets usable; without it users would have to hard-code indexes.

**Independent Test**: Add the camera and verify that each preset visible in the EZVIZ app appears in Home Assistant with the same name.

**Acceptance Scenarios**:

1. **Given** the camera has three presets named "Sud", "Ovest", "Nord", **When** the integration is set up, **Then** Home Assistant offers exactly those three presets by name.
2. **Given** the user adds, renames or deletes a preset in the EZVIZ app, **When** the user reloads the integration or refreshes the list, **Then** Home Assistant reflects the change.

---

### User Story 3 - Build a patrol with Home Assistant automations (Priority: P2)

As a user whose camera is battery powered (no built-in patrol), I want to chain preset invocations in an automation or script on a schedule, so the camera "patrols" through its viewpoints.

**Why this priority**: This is the end goal, but it is achieved by composing Stories 1 and 2 with standard Home Assistant automations, so no extra dedicated patrol feature is built.

**Independent Test**: Create an automation that visits presets in sequence with a delay between them and verify the camera visits each one in order.

**Acceptance Scenarios**:

1. **Given** an automation that triggers presets 1, 2, 3 with a delay between each, **When** it runs, **Then** the camera visits each preset in order.
2. **Given** a patrol is running and one preset command fails, **When** the failure occurs, **Then** the failure is reported so the automation can handle it, and later steps are not blocked by the integration.

---

### User Story 4 - Existing HP5 setup keeps working (Priority: P1)

As an existing user of the HP5 gate/door unlock, I want my current setup to keep working unchanged after this feature is added, and to be able to add a CB8 Lite alongside it.

**Why this priority**: Regression protection for the current working functionality.

**Independent Test**: With an existing HP5 entry, upgrade and verify gate/door unlock still works; add a CB8 Lite and verify both coexist.

**Acceptance Scenarios**:

1. **Given** an existing HP5 configuration, **When** the integration is updated, **Then** the gate and door controls still work without reconfiguration.
2. **Given** an HP5 and a CB8 Lite are both configured, **When** the user uses either device, **Then** each acts only on its own device.

---

### Edge Cases

- The camera has no presets saved: Home Assistant shows none and no error is raised.
- A preset is deleted in the EZVIZ app but still referenced by an automation: triggering it fails with a clear message.
- The battery camera is asleep or offline when a preset is requested: the user sees an explicit failure (or the camera wakes and moves), not a silent success.
- Presets are triggered in rapid succession (e.g. an aggressive patrol): the integration does not crash or lock up; failures are reported per request.
- Credentials expire or are rotated: the user is prompted to re-authenticate, as already done for the HP5.
- The same EZVIZ account owns several cameras: only the configured camera is affected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to add a CB8 Lite camera to the integration through the Home Assistant UI, identified by its serial number, validating credentials like the existing HP5 setup.
- **FR-002**: The system MUST retrieve the list of presets defined on the camera (index and name).
- **FR-003**: The system MUST expose each preset in Home Assistant so users can select and trigger it by name in the UI, automations and scripts.
- **FR-004**: Triggering a preset MUST move the camera to the corresponding saved position.
- **FR-005**: The system MUST report failures (network, authentication, unknown preset, device unavailable) to the user and to the calling automation.
- **FR-006**: The system MUST re-authenticate or retry once on session expiry, and start the reauth flow when credentials are invalid, consistent with existing behaviour.
- **FR-007**: The system MUST allow the preset list to be refreshed so changes made in the EZVIZ app become visible.
- **FR-008**: Existing HP5 gate and door unlock behaviour and existing configurations MUST remain unchanged.
- **FR-009**: Multiple devices (HP5 and CB8 Lite, or several cameras) MUST be configurable side by side, each acting only on its own device.
- **FR-010**: Credentials MUST NOT be logged, and all communication MUST use the EZVIZ cloud over a secure connection.
- **FR-011**: User-facing text for the new setup steps and errors MUST be provided in English and Italian.
- **FR-012**: The feature MUST NOT include a dedicated built-in patrol scheduler; patrols are composed by users with Home Assistant automations.

### Key Entities

- **Camera**: A configured PTZ camera (verified on the CB8 Lite), identified by serial number and tied to one EZVIZ account.
- **Preset**: A saved camera position, with an index and a user-defined name, owned by one camera (thumbnails are ignored).
- **Preset invocation**: A request to move a camera to a preset, with a success or failure result.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the presets visible in the EZVIZ app for the camera are listed in Home Assistant with matching names.
- **SC-002**: A user can trigger a preset from Home Assistant and see the camera reach that position within 10 seconds when the camera is online and reachable.
- **SC-003**: A user can build a working multi-preset patrol using only the Home Assistant UI, in under 10 minutes, with no custom code.
- **SC-004**: At least 95% of preset requests when the camera is online and reachable succeed on the first attempt (or after the single automatic retry).
- **SC-005**: Existing HP5 users see no change: gate/door unlock works after the update without any reconfiguration.
- **SC-006**: Every failed preset request produces a visible, understandable error rather than a silent failure.

## Assumptions

- The CB8 Lite supports pan/tilt presets defined in the EZVIZ app; creating and editing presets stays in the EZVIZ app and is out of scope.
- The feature works through the EZVIZ cloud, with the same account credentials used today; the captured traffic in `.asset/flows.txt` shows the app listing presets and moving to them (including three presets named "Sud", "Ovest", "Nord").
- The camera is one channel (channel 1) and the camera's serial number is the identifier supplied by the user.
- Whether and how fast the battery camera wakes from sleep when a preset is requested is not known and will be verified during planning; the spec requires only that outcomes are reported honestly.
- Live video streaming, snapshots, motion detection and battery status are out of scope.
- Repository/project rename to "hassezviz" (including the GitHub repository name and any resulting metadata or documentation links) is a separate housekeeping task and not part of this feature's requirements, although the integration's own functionality is unaffected by it.
- The preset list is refreshed on setup, on reload, and on demand; automatic background polling is not required.
- The feature is generic: it works with whatever presets the camera reports (any number, any names, including none) and nothing is tied to specific preset names or to one user's account or serial.
- The device type offered in the setup form is a generic "PTZ camera"; only the CB8 Lite has been verified, other EZVIZ PTZ models may work but are not guaranteed.
- Only channel 1 is supported (single-camera devices); multi-channel recorders are out of scope.
- The default EZVIZ server is the European one; users in other regions must set the API URL in the setup form.
