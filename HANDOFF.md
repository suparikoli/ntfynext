# ntfynext: handoff

Updated 2026-11-19.

## What it is

Delivers Frappe notifications as ntfy push notifications, as an extra channel next to email.
It adds a "Send via NTFY" checkbox on the Notification doctype, a per-user opt-in with a private topic (Subscribe card with QR code), a `ntfynext.notify()` Python API, and auto-provisioning through `backntfy`.

## State

- Status: dormant.
- Default branch: `main` (`34c6361`, merged from `version-16` in the branch consolidation). Local checkout is on `wip`. Ship with `git ship`.
- Gate: `bench --site <site> run-tests --app ntfynext` (needs `allow_tests` set). Run tests against a live ntfy server before a release.
- Deploy target: none recorded. The app ships with the bench that installs it.
- Python `>=3.14`, dependency `pyqrcode`. No Node pin.
- Last notable work: `3c9898d` (2026-07-15) documented the backntfy auto-provisioning integration.
- Bench notes (start, dumps, versions): `../../HANDOFF.md`.

## Open work

- None pending.
- If revived: restore a site, install the app, run the tests against a live ntfy server.
- Configuration lives in NTFY Settings (server URL, auth type). Password fields (`token`, `password`, `backntfy_api_token`) sit in the site DB. Do not commit them.
- Pulse and Medusa run their own ntfy alerts. Changes here do not affect them.

## Read next

- `docs/`: installation, configuration, developer API, architecture.
- `README.md`: overview.
- `mith_ntfy/` and `ntfynext/`: app code.
- `../../../000-docker/NTFY/backntfy`: the ntfy admin backend (own repo).
