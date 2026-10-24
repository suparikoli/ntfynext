# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Install / migrate setup for Mith ntfy.

Idempotent: custom fields, the ``NTFY Manager`` role, and sensible default
``NTFY Settings`` are (re)ensured on both ``after_install`` and ``after_migrate``
so fresh installs and upgrades of existing sites converge to the same state.
"""

from __future__ import annotations

import frappe

# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------
# A dedicated "NTFY" tab on User + a "Send via NTFY" toggle (and options) on the
# standard Notification. Priority selects lead with a blank option meaning
# "inherit the global default".
_PRIORITY_OPTIONS = "\nmin\nlow\ndefault\nhigh\nmax"

CUSTOM_FIELDS: dict[str, list[dict]] = {
	"User": [
		{
			"fieldname": "ntfy_tab",
			"fieldtype": "Tab Break",
			"label": "NTFY",
			"insert_after": "active_sessions",
		},
		{
			"fieldname": "ntfy_prefs_section",
			"fieldtype": "Section Break",
			"label": "NTFY Push Notifications",
			"description": "Receive your Frappe notifications as ntfy push messages.",
			"insert_after": "ntfy_tab",
		},
		{
			"fieldname": "enable_ntfy",
			"fieldtype": "Check",
			"label": "Enable NTFY Notifications",
			"insert_after": "ntfy_prefs_section",
		},
		{
			"fieldname": "ntfy_topic",
			"fieldtype": "Data",
			"label": "NTFY Topic",
			"depends_on": "eval:doc.enable_ntfy",
			"description": "Auto-generated when you enable NTFY. Subscribe to it in your ntfy app. Keep it secret on public servers.",
			"insert_after": "enable_ntfy",
		},
		{
			"fieldname": "ntfy_override_server_url",
			"fieldtype": "Data",
			"label": "Override Server URL",
			"depends_on": "eval:doc.enable_ntfy",
			"description": "Optional. Leave blank to use the global NTFY server.",
			"insert_after": "ntfy_topic",
		},
		{
			"fieldname": "ntfy_col_break",
			"fieldtype": "Column Break",
			"insert_after": "ntfy_override_server_url",
		},
		{
			"fieldname": "ntfy_priority",
			"fieldtype": "Select",
			"label": "Notification Priority",
			"options": _PRIORITY_OPTIONS,
			"depends_on": "eval:doc.enable_ntfy",
			"description": "Leave blank to use the global default.",
			"insert_after": "ntfy_col_break",
		},
		{
			"fieldname": "ntfy_tags",
			"fieldtype": "Data",
			"label": "Notification Tags",
			"depends_on": "eval:doc.enable_ntfy",
			"description": "Comma-separated ntfy tags / emoji shortcodes.",
			"insert_after": "ntfy_priority",
		},
		{
			"fieldname": "ntfy_silent_mode",
			"fieldtype": "Check",
			"label": "Silent Mode",
			"depends_on": "eval:doc.enable_ntfy",
			"description": "Temporarily pause ntfy delivery without losing your settings.",
			"insert_after": "ntfy_tags",
		},
		{
			"fieldname": "ntfy_subscribe_section",
			"fieldtype": "Section Break",
			"label": "Subscribe on Your Device",
			"depends_on": "eval:doc.enable_ntfy && doc.ntfy_topic",
			"insert_after": "ntfy_silent_mode",
		},
		{
			"fieldname": "ntfy_subscribe_html",
			"fieldtype": "HTML",
			"depends_on": "eval:doc.enable_ntfy && doc.ntfy_topic",
			"insert_after": "ntfy_subscribe_section",
		},
		{
			"fieldname": "ntfy_provisioned",
			"fieldtype": "Check",
			"label": "backntfy Provisioned",
			"read_only": 1,
			"description": "Set to 1 by the backntfy auto-provision hook after a successful create + ACL grant. Uncheck to force re-provisioning on next save.",
			"depends_on": "eval:doc.enable_ntfy",
			"insert_after": "ntfy_subscribe_html",
		},
		{
			"fieldname": "ntfy_client_password",
			"fieldtype": "Password",
			"label": "NTFY Account Password",
			"read_only": 1,
			"description": "Auto-generated password for the ntfy account provisioned via backntfy. Use it (with this username) to sign into your ntfy mobile/web app. Only visible to System Manager and the user themselves.",
			"depends_on": "eval:doc.enable_ntfy && doc.ntfy_provisioned",
			"length": 300,
			"insert_after": "ntfy_provisioned",
		},
	],
	"Notification": [
		{
			"fieldname": "send_via_ntfy",
			"fieldtype": "Check",
			"label": "Send via NTFY",
			"description": "Also deliver this notification as an ntfy push to opted-in recipients.",
			"insert_after": "channel",
		},
		{
			"fieldname": "ntfy_section",
			"fieldtype": "Section Break",
			"label": "NTFY Options",
			"collapsible": 1,
			"depends_on": "eval:doc.send_via_ntfy",
			"insert_after": "send_via_ntfy",
		},
		{
			"fieldname": "ntfy_topic",
			"fieldtype": "Data",
			"label": "Direct Topic",
			"depends_on": "eval:doc.send_via_ntfy",
			"description": "Optional: also publish to this fixed topic (e.g. a shared team topic), regardless of recipients.",
			"insert_after": "ntfy_section",
		},
		{
			"fieldname": "ntfy_priority",
			"fieldtype": "Select",
			"label": "Priority",
			"options": _PRIORITY_OPTIONS,
			"depends_on": "eval:doc.send_via_ntfy",
			"insert_after": "ntfy_topic",
		},
		{
			"fieldname": "ntfy_tags",
			"fieldtype": "Data",
			"label": "Tags",
			"depends_on": "eval:doc.send_via_ntfy",
			"insert_after": "ntfy_priority",
		},
	],
}


def exported_custom_field_names() -> list[str]:
	"""Return the ``Custom Field`` record names (``{dt}-{fieldname}``) we own.

	Used by the ``fixtures`` hook so exports capture exactly our fields.
	"""
	return [
		f"{doctype}-{field['fieldname']}"
		for doctype, fields in CUSTOM_FIELDS.items()
		for field in fields
	]


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def after_install() -> None:
	"""Run once when the app is installed.

	``sync_for`` creates our doctypes just before this hook runs, but the
	``doctype_modules`` cache was populated earlier in the same request, so we
	refresh caches before touching freshly-synced doctypes.
	"""
	frappe.clear_cache()
	_sync_custom_fields()
	ensure_roles()
	ensure_default_settings()
	frappe.db.commit()


def after_migrate() -> None:
	"""Run on every ``bench migrate`` — keeps existing sites in sync."""
	_sync_custom_fields()
	ensure_roles()


def _sync_custom_fields() -> None:
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def ensure_roles() -> None:
	"""Create the ``NTFY Manager`` role if it is missing."""
	if not frappe.db.exists("Role", "NTFY Manager"):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": "NTFY Manager",
				"desk_access": 1,
			}
		).insert(ignore_permissions=True)


def ensure_default_settings() -> None:
	"""Seed the ``NTFY Settings`` singleton with safe defaults on first install.

	Uses ``set_single_value`` (writes straight to the ``Singles`` table) rather
	than ``get_single().save()`` so it never imports the controller — which is
	unsafe during ``after_install`` while the module cache is still warming.
	"""
	if not frappe.db.get_single_value("NTFY Settings", "server_url"):
		frappe.db.set_single_value(
			"NTFY Settings",
			{
				"server_url": "https://ntfy.sh",
				"default_priority": "default",
				"request_timeout": 10,
				"verify_ssl": 1,
				"retry_count": 5,
			},
		)
