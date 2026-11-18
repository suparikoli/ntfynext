# NTFYnext: handoff (2026-10-18)

Status: **dormant**. Bench-level notes (how to start the bench, MariaDB dumps, versions): `../../HANDOFF.md`.

## Purpose

Delivers Frappe notifications as ntfy push notifications, as an extra channel next to email. A **Send via NTFY** checkbox on the Notification doctype, a per-user opt-in with a private topic (Subscribe card with QR code), a `ntfynext.notify()` Python API, and auto-provisioning through `backntfy` (the ntfy backend in `Coding/000-docker/NTFY/backntfy`).

## How to run

```bash
bench --site <site> install-app ntfynext      # requires-python >=3.14; dependency pyqrcode; no Node pin
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app ntfynext
```
Configure in **NTFY Settings** (server URL, auth type; password fields `token`, `password`, `backntfy_api_token`, stored in the site DB). No `.env` files. Docs in `docs/` (installation, configuration, developer API, architecture). External service: any ntfy server (ntfy.sh or self-hosted). Data home: local (no Offload profile).

## Last state

- Branch `version-16` at `3c9898d` (2026-07-15, "docs: document backntfy auto-provisioning integration"), in sync with `origin` (git@github.com:suparikoli/ntfynext). Working tree clean. TODO/FIXME/HACK: 0.
- No git actions on 2026-10-18. No Claude sessions or plans for this app since July (only a passing mention on 2026-10-12).
- Pulse has its own ntfy notifications; Medusa uses ntfy for operator alerts.

## Next steps

None pending. If revived: restore a site, install, and run the tests against a live ntfy server.
