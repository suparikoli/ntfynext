# Installation

## Requirements

- Frappe **v16+** (Python 3.14).
- Redis running (background jobs) and at least one worker.
- Network access from the Frappe server to your ntfy server.

## Install

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench --site your.site install-app ntfynext
bench --site your.site migrate      # if upgrading an existing install
bench restart                       # so workers/scheduler pick up the new hooks
```

`install-app` runs `after_install`, which:

- creates the custom fields (a **NTFY** tab on **User**, a **Send via NTFY** toggle
  and options on **Notification**);
- creates the **NTFY Manager** role;
- seeds sensible defaults into **NTFY Settings** (server `https://ntfy.sh`, timeout 10s,
  5 retries).

> After installing an app you must **restart** the bench (or your process manager)
> so the web, worker, and scheduler processes load the new hooks. Until then,
> the settings/console work but live notifications and async delivery won't fire.

## Verify

1. **NTFY Settings → Test Connection** should return HTTP `200`.
2. `bench --site your.site execute ntfynext.api.notify --kwargs '{"topic":"my-topic","title":"Hi","message":"test"}'`
   then watch `https://ntfy.sh/my-topic`.
3. Check **NTFY Notification Log** for a `Success` row.

## Upgrade

`bench --site your.site migrate` runs `after_migrate` and the
`ntfynext.patches.v1_0.ensure_setup` patch — both idempotent — to (re)ensure the
custom fields, role, and defaults.

## Uninstall

```bash
bench --site your.site uninstall-app ntfynext
```

This removes the doctypes, custom fields, role, workspace, and page.
