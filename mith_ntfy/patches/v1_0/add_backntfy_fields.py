# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Add the ``ntfy_provisioned`` and ``ntfy_client_password`` custom fields to
User on sites that installed Mith ntfy before backntfy auto-provisioning
existed. ``ensure_setup`` also runs ``_sync_custom_fields`` but is marked
executed on those older sites, so a dedicated patch is needed to fire once
on upgrade.

Idempotent — ``create_custom_fields`` skips fields that already exist.
"""

from mith_ntfy import install


def execute() -> None:
	install._sync_custom_fields()
