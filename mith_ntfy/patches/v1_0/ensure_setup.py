# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Ensure Mith ntfy setup exists on sites upgrading from an earlier state.

Idempotent and safe to re-run: (re)creates the custom fields, the NTFY Manager
role, and default settings. Mirrors ``install.after_migrate`` so that a site
which somehow missed the install hook still converges.
"""

from mith_ntfy import install


def execute() -> None:
	install._sync_custom_fields()
	install.ensure_roles()
	install.ensure_default_settings()
