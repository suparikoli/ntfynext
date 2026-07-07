# Developer API

## `notify(...)`

```python
from ntfynext import notify

# Notify users (only opted-in, non-silent users with a topic get a push):
notify(
    users=["Administrator", "sales@example.com"],
    title="Lead Assigned",
    message="A new lead has been assigned.",
    url="/app/lead/LEAD-0001",
)

# Publish directly to a fixed topic:
notify(topic="sales-team", title="New Opportunity", message="Acme just signed up.")
```

**Signature**

```python
notify(users=None, topic=None, title=None, message=None, url=None,
       priority=None, tags=None, doctype=None, docname=None, **kwargs) -> list[str]
```

| Arg | Meaning |
|---|---|
| `users` | User ids / emails. Resolved to opted-in recipients. |
| `topic` | Publish directly to this topic (in addition to `users`). |
| `title`, `message` | Notification title and body. |
| `url` | Click-through URL (ntfy `click`). |
| `priority` | `min`/`low`/`default`/`high`/`max` or `1`–`5`. Falls back to configured default. |
| `tags` | Comma string or list of ntfy tags/emoji. |
| `doctype`, `docname` | Originating document — linked on each log. |
| `**kwargs` | Extra ntfy fields: `icon`, `attach`, `filename`, `actions`, `markdown`, `delay`, `email`, `call`. |

Returns the created **NTFY Notification Log** names. Publishing happens in a
background worker; the master **Enabled** switch gates everything.

## Convenience wrappers

```python
from ntfynext import send_notification, publish

send_notification("Administrator", title="Hi", message="…", url="/app")
publish("ops-alerts", title="Disk 90%", message="…", priority="high", tags="warning")
```

## Whitelisted endpoints

| Method | Used by |
|---|---|
| `ntfynext.api.send_test` | The **NTFY Test** page (synchronous; returns the server response). |
| `ntfynext.api.send_manual` | The **Send NTFY Notification** document menu. |
| `NTFY Settings.test_connection` | The **Test Connection** button. |

Both `send_test` and `send_manual` require the **System Manager** or **NTFY Manager**
role; `send_manual` also checks read access to the referenced document.

## Jinja templates

Notification subjects and messages are rendered with Frappe's Jinja context
(`doc`, `alert`, `comments`, …). The HTML body is stripped to plain text and
capped at 1000 characters for the push.

## Adding another provider

Implement `ntfynext.providers.base.NotificationProvider` and map a
`PushMessage`; register it in the dispatch layer. Nothing in the dispatch,
queue, or log code needs to change. See [architecture](architecture.md).
