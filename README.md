# NTFYnext

Deliver Frappe notifications as [ntfy](https://ntfy.sh) push notifications — as an
**additional** channel alongside email, never a replacement.

Whenever Frappe sends a notification, users who have opted in receive the same
message as a push on their phone or desktop through **any** ntfy server
(self-hosted or public). Works with `ntfy.sh` or your own `https://notify.company.com`.

- **Publisher:** MithTech Innovative Solutions · **License:** MIT · **Frappe:** v16+

---

## Features

- **Two delivery paths, one transport**
  - *Precise:* a **Send via NTFY** checkbox on the standard **Notification** doctype
    (reuses Frappe's own recipient resolution — document field, role, assignees, cc/bcc).
  - *Global mirror (optional, off by default):* mirror **every** outgoing notification
    email to opted-in users.
- **Per-user opt-in** with an auto-generated, unguessable topic (override allowed),
  priority, tags, server override, and a silent-mode switch.
- **Full ntfy field support** — title, message, priority, tags, click, attach,
  filename, icon, actions, markdown, delay, email, call.
- **Never blocks saves** — every push runs in a background worker.
- **Delivery log** with status, response, duration, payload, and **redacted** headers.
- **Automatic retries** with escalating backoff: 1m → 5m → 30m → 2h → 24h.
- **Test tooling** — a Test Connection button, an **NTFY Test** desk page, and a
  **Send NTFY Notification** action on every document.
- **Secure** — secrets in encrypted password fields, headers redacted in logs,
  URL/SSRF validation, TLS verification.
- **Extensible** — a provider interface so Telegram / Gotify / Discord / Matrix / …
  can be added later without touching dispatch, queueing, or logging.

## Quick start

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench --site your.site install-app ntfynext
```

Then, as a System Manager:

1. Open **NTFY Settings**, set the **Server URL** (e.g. `https://ntfy.sh`), tick
   **Enabled**, choose an auth type, and click **Test Connection**.
2. On your **User** record, open the **NTFY** tab, tick **Enable NTFY Notifications**
   (a private topic is generated), and **subscribe to that topic** in your ntfy app.
3. Add **Send via NTFY** to any Notification, or use the **NTFY Test** page.

## Developer API

```python
from ntfynext import notify

notify(users=["Administrator"], title="Lead Assigned",
       message="A new lead has been assigned.", url="/app/lead/LEAD-0001")

notify(topic="sales-team", title="New Opportunity", message="…")
```

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Developer API](docs/developer-api.md)
- [Architecture](docs/architecture.md)

## Tests

```bash
bench --site your.site set-config allow_tests true
bench --site your.site run-tests --app ntfynext
```

## Contributing

This app uses `pre-commit` (ruff, eslint, prettier, pyupgrade):

```bash
cd apps/ntfynext
pre-commit install
```

## License

MIT
