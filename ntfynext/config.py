# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Configuration resolution for NTFYnext.

:func:`get_ntfy_config` merges the global ``NTFY Settings`` singleton with an
optional user's per-user overrides into an immutable :class:`ResolvedConfig`
that the provider and dispatch layers consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import frappe

from ntfynext.utils import normalize_tags

SETTINGS_DOCTYPE = "NTFY Settings"


@dataclass(frozen=True)
class ResolvedConfig:
	"""Effective, ready-to-use NTFYnext configuration."""

	enabled: bool
	server_url: str
	auth_type: str
	username: str | None
	password: str | None
	token: str | None
	default_priority: str
	default_tags: list[str] = field(default_factory=list)
	default_icon_url: str | None = None
	default_click_url: str | None = None
	request_timeout: int = 10
	verify_ssl: bool = True
	retry_count: int = 5
	mirror_all_emails: bool = False


def get_settings():
	"""Return the cached ``NTFY Settings`` singleton document."""
	return frappe.get_cached_doc(SETTINGS_DOCTYPE)


def is_ntfy_enabled() -> bool:
	"""Cheap gate used by hot paths (e.g. the Email Queue hook)."""
	return bool(frappe.get_cached_value(SETTINGS_DOCTYPE, SETTINGS_DOCTYPE, "enabled"))


def get_ntfy_config(user: str | None = None) -> ResolvedConfig:
	"""Resolve effective config, optionally layering a user's overrides on top.

	A per-user ``ntfy_override_server_url`` replaces the global server (global
	auth still applies); ``ntfy_priority``/``ntfy_tags`` override the defaults.
	"""
	settings = get_settings()

	server_url = (settings.server_url or "").strip().rstrip("/")
	default_priority = settings.default_priority or "default"
	default_tags = normalize_tags(settings.default_tags)

	if user:
		overrides = _user_overrides(user)
		if overrides.get("ntfy_override_server_url"):
			server_url = overrides["ntfy_override_server_url"].strip().rstrip("/")
		if overrides.get("ntfy_priority"):
			default_priority = overrides["ntfy_priority"]
		if overrides.get("ntfy_tags"):
			default_tags = normalize_tags(overrides["ntfy_tags"])

	return ResolvedConfig(
		enabled=bool(settings.enabled),
		server_url=server_url,
		auth_type=settings.auth_type or "None",
		username=settings.username,
		password=settings.get_password("password", raise_exception=False) if settings.auth_type == "Basic" else None,
		token=settings.get_password("token", raise_exception=False) if settings.auth_type == "Bearer" else None,
		default_priority=default_priority,
		default_tags=default_tags,
		default_icon_url=settings.default_icon_url,
		default_click_url=settings.default_click_url,
		request_timeout=settings.request_timeout or 10,
		verify_ssl=bool(settings.verify_ssl),
		retry_count=settings.retry_count if settings.retry_count is not None else 5,
		mirror_all_emails=bool(settings.mirror_all_emails),
	)


def _user_overrides(user: str) -> dict:
	"""Read a user's NTFY override fields, tolerating their absence (pre-install)."""
	meta = frappe.get_meta("User")
	if not meta.has_field("enable_ntfy"):
		return {}
	row = frappe.db.get_value(
		"User",
		user,
		["ntfy_override_server_url", "ntfy_priority", "ntfy_tags"],
		as_dict=True,
	)
	return row or {}
