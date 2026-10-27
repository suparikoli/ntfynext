# Architecture

## Overview

```
Notification (Send via NTFY ✓) ─┐
                                 ├─► resolve recipients → users → topics ─┐
Email Queue.after_insert (mirror)┘        (per-user opt-in + topic)        │
                                                                           ▼
mith_ntfy.notify(...) ──────────────────────────────────────► enqueue_publish
                                                                           │  (Queued log)
                                                                           ▼
                                                          frappe.enqueue (worker)
                                                                           │
                                                                           ▼
                                                   NtfyProvider.publish_payload  ──► NTFY Notification Log
                                                     (requests + auth/timeout)         (Success / Retrying / Failed)
                                                                           │
                                                                   retry sweeper (cron)
```

Two entry paths feed one transport, and every attempt is logged.

## Delivery paths

1. **Precise (Notification).** `override_doctype_class` replaces the standard
   `Notification` controller with `NTFYNotification` (a loader-enforced subclass —
   not a monkeypatch). It overrides `send_notification_by_channel`: calls `super()`
   so email/Slack/SMS/system delivery is unchanged, then, when **Send via NTFY** is
   ticked, pushes to ntfy — reusing the inherited `get_list_of_recipients()`.

2. **Global mirror (optional, off).** A `doc_events` hook on **Email Queue**
   `after_insert` mirrors every outgoing email to opted-in users. It does only cheap
   checks on the request path and defers parsing/delivery to a background job. It is
   skipped for emails already handled by the precise path (via `frappe.flags.ntfynext_inline`).

3. **Developer API.** `mith_ntfy.notify()` / `send_notification()` / `publish()`.

## Modules

| Module | Responsibility |
|---|---|
| `providers/base.py` | `PushMessage`, `ProviderResponse`, `NotificationProvider` (the extensibility seam). |
| `providers/ntfy.py` | ntfy transport over `requests` (JSON API), auth headers, single-attempt publish. |
| `config.py` | `get_ntfy_config(user)` → immutable `ResolvedConfig` (global + user overrides). |
| `recipients.py` | Recipients (ids/emails) → opted-in `UserTarget`s. |
| `dispatch.py` | `enqueue_publish` / `publish_job` / `publish_now`, and the Email Queue mirror. |
| `api.py` | Developer API + whitelisted desk endpoints. |
| `overrides/notification.py` | `NTFYNotification` (precise path). |
| `tasks.py` | `retry_failed_notifications` cron sweep. |
| `user.py` | Auto-generate an unguessable topic on opt-in; optional `sync_backntfy` hook enqueues a backntfy provisioning job. |
| `install.py` | Custom fields, role, default settings (idempotent). |
| `utils.py` | URL/SSRF validation, priority/tag normalisation, header redaction, logging. |
| `backntfy.py` | Optional client for a [backntfy](https://github.com/mithtech/backntfy) admin-panel instance — `provision_user` / `deprovision_user` / `test_connection`. Same never-raise style as `providers/ntfy.py`. |

## Key design decisions

- **No monkeypatching.** The Notification doctype has no channel-registration hook, so
  extension is done through the supported `override_doctype_class` (subclass + `super()`).
- **Reuse, don't reimplement.** Recipient resolution is inherited from Frappe's
  Notification, so every recipient mechanism is honoured for free.
- **Never block the request.** All network I/O runs in a worker; the request path only
  writes a Queued log and enqueues after commit.
- **The log owns its lifecycle.** `apply_response()` / `schedule_retry()` on
  `NTFY Notification Log` implement the Success/Retrying/Failed state machine and backoff.
- **Secrets never leave the vault.** Password fields store credentials encrypted; the job
  rebuilds auth headers from config at send time and stores **redacted** headers on the log.

## Data model

- **NTFY Settings** (Single) — global config.
- **NTFY Notification Log** — one row per attempt (indexed on `status, next_retry_at`).
- **Custom Fields** — the User NTFY tab and the Notification **Send via NTFY** options.

## Extending to new providers

`dispatch` and the log speak only to `NotificationProvider` + `PushMessage`.
A new channel (Telegram, Gotify, Discord, Matrix, …) is a new
`providers/<name>.py` implementing `publish`, selected via settings — no changes
to dispatch, queueing, retries, or logging.

## Optional backntfy provisioning flow

`backntfy.py` is a separate concern from the transport — it never runs at
publish time. It's only invoked from `user.sync_backntfy` on `User.on_update`,
via `frappe.enqueue(..., queue="short", enqueue_after_commit=True)`.

```
User.on_update ──► sync_backntfy (guard: enable_ntfy + topic + settings.backntfy_enabled)
                         │
                         ▼
                enqueue_after_commit  ────► worker runs _provision_via_backntfy
                                                      │
                                                      ▼
                                             backntfy.provision_user
                                              (POST /api/users, POST /api/access)
                                                      │
                                                      ▼
                                    frappe.db.set_value: ntfy_provisioned + ntfy_client_password
```

Failures are logged and the User save is unaffected — the transport path (the
diagram at the top) has no dependency on backntfy.
