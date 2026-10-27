# Configuration

## Global — NTFY Settings (System Manager only)

| Field | Purpose |
|---|---|
| **Enabled** | Master switch. When off, nothing is queued or sent. |
| **NTFY Server URL** | Base URL of any ntfy server, e.g. `https://ntfy.sh` or `https://notify.company.com`. |
| **Mirror All Notification Emails** | When on, *every* outgoing notification email is also pushed to opted-in users (not just Notifications with **Send via NTFY**). Off by default. |
| **Default Priority / Tags / Icon URL / Click URL** | Applied when a message doesn't specify its own. |
| **Authentication Type** | `None`, `Basic` (Username + Password), or `Bearer` (Token). Secrets are stored encrypted. |
| **Request Timeout** | HTTP timeout in seconds (default 10). |
| **Verify SSL** | Verify the server's TLS certificate (disable only for trusted internal self-signed servers). |
| **Max Retry Count** | Automatic retries before a push is marked **Failed** (default 5). |
| **Enable backntfy Auto-Provisioning** | When on, opting a user into NTFY also creates their ntfy account + topic ACL via [backntfy](https://github.com/mithtech/backntfy). See [backntfy integration](#backntfy-auto-provisioning-optional). |
| **backntfy URL** | Base URL of the backntfy admin panel, e.g. `https://backntfy.example.com`. Not the ntfy server URL. |
| **backntfy API Token** | Bearer token accepted by backntfy's API (the `API_TOKEN` env var on the backntfy container). Stored encrypted. |

Use **Test Connection** to publish a test message and see the server response.
Use **Test backntfy Connection** to confirm the panel is reachable and the token is accepted.

## Per-user — the NTFY tab on User

Each user opts in on their own **User** record (or via **My Settings**):

| Field | Purpose |
|---|---|
| **Enable NTFY Notifications** | Opt in. On first enable, an unguessable topic is generated. |
| **NTFY Topic** | The topic to receive on. **Subscribe to it in your ntfy app.** Keep it secret on public servers. |
| **Override Server URL** | Optional; use a different ntfy server than the global one. |
| **Notification Priority / Tags** | Personal overrides of the global defaults. |
| **Silent Mode** | Temporarily pause delivery without losing settings. |
| **backntfy Provisioned** | Read-only. Set to 1 automatically after backntfy creates the user's ntfy account + ACL. Uncheck to force re-provisioning on next save. Only present when backntfy auto-provisioning is enabled globally. |
| **NTFY Account Password** | Read-only, encrypted. The auto-generated password for the user's ntfy account — hand this to them so they can sign into the ntfy mobile/web app. |

A user only receives a push if they are **enabled**, **not silent**, and **have a topic**.

## Per-notification — Send via NTFY

On any standard **Notification**, tick **Send via NTFY**. Optional fields:

- **Direct Topic** — also publish to a fixed topic (e.g. a shared team channel),
  regardless of recipients.
- **Priority / Tags** — override for this notification.

Recipients come from Frappe's normal Notification recipient rules (document field,
role, assignees, cc/bcc) — only those who have opted in receive a push.

## Priority

ntfy priorities map as: `min`=1, `low`=2, `default`=3, `high`=4, `max`=5.

## Retry policy

Failed pushes retry on an escalating schedule — **1m → 5m → 30m → 2h → 24h** —
until they succeed or reach **Max Retry Count**, then they are marked **Failed**.
A scheduled task runs each minute to release due retries.

## backntfy auto-provisioning (optional)

Skip this section if your ntfy server accepts anonymous reads/writes
(`NTFY_AUTH_DEFAULT_ACCESS=read-write`) or you don't mind hand-creating an ntfy
account for every user via the `ntfy` CLI.

For a locked-down (`deny-all`) self-hosted ntfy, [backntfy](https://github.com/mithtech/backntfy)
provides a web panel + REST API for user/ACL/token management. When mith_ntfy is
told about it, opting a user into NTFY also:

1. Creates an ntfy account with the user's Frappe username and a random password.
2. Grants that account **read-only** access to the user's generated topic.
3. Persists `ntfy_provisioned=1` + the generated password back on the User doc
   (encrypted) so you can hand credentials over once.

### Setup

1. Deploy backntfy alongside your ntfy container (see the
   [backntfy README](https://github.com/mithtech/backntfy)). Set an `API_TOKEN`
   env var (at least 32 chars).
2. In backntfy, create a `frappe-publisher` user with role `admin` and issue a
   never-expiring token for it. This token goes into NTFY Settings ▸
   **Authentication Type: Bearer** and lets mith_ntfy publish to any topic.
3. In NTFY Settings ▸ **backntfy Auto-Provision** section:
   - Tick **Enable backntfy Auto-Provisioning**
   - **backntfy URL**: `https://backntfy.example.com`
   - **backntfy API Token**: the `API_TOKEN` from step 1 (not the `tk_…` publisher token)
   - Save, then click **Test backntfy Connection** — should say "API token accepted".

### Runtime behaviour

- The hook is `mith_ntfy.user.sync_backntfy` on `User.on_update`. It enqueues a
  short-queue job (`enqueue_after_commit=True`), so a slow or unreachable
  backntfy never blocks a User save.
- Idempotent: users with `ntfy_provisioned=1` are skipped unless their topic
  changed. A "user already exists" (4xx) from backntfy is treated as success and
  the flow proceeds to the ACL grant.
- Failures are logged to the site log (`mith_ntfy` logger) — the User still saves.
- Uncheck **backntfy Provisioned** on a User to force re-provisioning on the
  next save.
