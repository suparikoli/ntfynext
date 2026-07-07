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

Use **Test Connection** to publish a test message and see the server response.

## Per-user — the NTFY tab on User

Each user opts in on their own **User** record (or via **My Settings**):

| Field | Purpose |
|---|---|
| **Enable NTFY Notifications** | Opt in. On first enable, an unguessable topic is generated. |
| **NTFY Topic** | The topic to receive on. **Subscribe to it in your ntfy app.** Keep it secret on public servers. |
| **Override Server URL** | Optional; use a different ntfy server than the global one. |
| **Notification Priority / Tags** | Personal overrides of the global defaults. |
| **Silent Mode** | Temporarily pause delivery without losing settings. |

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
