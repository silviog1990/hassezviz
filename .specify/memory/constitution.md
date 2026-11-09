<!--
Sync Impact Report (temporary, remove before commit)
- Version change: (unfilled template) -> 1.0.0
- Modified principles: none renamed (all principles newly defined)
- Added sections: Core Principles I-V, Technical Constraints, Development Workflow, Governance
- Removed sections: none
- Deferred TODOs: none
-->

# hassezviz Constitution

## Core Principles

### I. Native Home Assistant Integration
Every capability MUST be exposed as native Home Assistant entities configured through the UI
config flow (with reauth), never via YAML or an external service. Entities that cannot read
back real device state MUST declare assumed state. Rationale: this project exists to replace
external glue (the former REST microservice) with a first-class integration.

### II. Cloud Calls Mirror the Official App
Device commands MUST reproduce request formats observed in the official EZVIZ app traffic,
and MUST go over HTTPS to the EZVIZ cloud only. `pyezvizapi` MAY be used for login and
session handling; where it does not support a device, requests are built directly and the
reason is documented. Rationale: the cloud API is undocumented, so captured app behaviour is
the only reliable contract.

### III. No Polling, No Background Load
The integration MUST NOT poll devices or run a coordinator; state changes happen only on
user-initiated actions, setup, or explicit refresh. Each command MUST re-authenticate and
retry at most once on failure. Rationale: battery-powered devices and the shared cloud account
must not be hit with unrequested traffic.

### IV. Credentials and Privacy (NON-NEGOTIABLE)
Credentials, session IDs and tokens MUST never be logged or committed, and are stored only in
the Home Assistant config entry. Captured traffic files and virtualenvs MUST NOT be committed
with real secrets or force-added. Test data MUST use fictional serials, names and accounts.

### V. Backward Compatibility and Tests
Changes MUST NOT break existing config entries or entities (the domain stays `ezviz_hp5`
until a migration is explicitly designed). Every behaviour change MUST be covered by pytest
tests with mocked HTTP, and the full suite MUST pass before merging. Rationale: users already
run this integration at their gate.

## Technical Constraints

- Language: Python, compatible with Home Assistant's supported version (tests run in the
  Python 3.13 venv `.venv-test`).
- Distribution: HACS custom repository and manual copy; metadata in `manifest.json`,
  `hacs.json`.
- User-facing strings MUST be provided in English and Italian (`strings.json`,
  `translations/en.json`, `translations/it.json`).
- Commented reference code (e.g. the unused `_lock` request) MUST be kept, not deleted.

## Development Workflow

- Features follow Spec Kit: spec, plan, tasks, then implementation, on a dedicated branch;
  `main` is merged only after validation on real hardware where the feature depends on it.
- Project documentation (`CLAUDE.md`, READMEs) MUST be updated in the same change when
  architecture or user-visible behaviour changes.
- Features MUST be generic: no hardcoded user names, serials, preset names or regions.

## Governance

This constitution supersedes other practices. Amendments require a documented change to this
file with a version bump (MAJOR for removing or redefining a principle, MINOR for adding or
materially expanding one, PATCH for clarifications). Plans and reviews MUST check compliance
with the principles above, and any deviation MUST be justified in the plan's Complexity
Tracking section. `CLAUDE.md` provides runtime development guidance.

**Version**: 1.0.0 | **Ratified**: 2026-08-28 | **Last Amended**: 2026-11-09
