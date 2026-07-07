# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Shared helpers for NTFYnext: URL validation/SSRF guard, priority and tag
normalisation, secret redaction, and logging.

These functions are deliberately light on Frappe coupling so the pure ones
(:func:`priority_to_int`, :func:`normalize_tags`, :func:`redact_headers`,
:func:`validate_server_url`) can be unit-tested without a live site.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import frappe
from frappe import _

# ntfy priority names → integer (1=min … 5=max). ntfy's JSON API expects an int.
PRIORITY_MAP: dict[str, int] = {
	"min": 1,
	"low": 2,
	"default": 3,
	"high": 4,
	"max": 5,
	"1": 1,
	"2": 2,
	"3": 3,
	"4": 4,
	"5": 5,
}

DEFAULT_PRIORITY = 3
_REDACTED = "***REDACTED***"
_SENSITIVE_HEADERS = {"authorization", "x-token", "cookie"}


def priority_to_int(priority: str | int | None) -> int:
	"""Map an ntfy priority (name, int, or numeric string) to an int in 1..5.

	Unknown or missing values fall back to :data:`DEFAULT_PRIORITY` (3).
	"""
	if priority is None or priority == "":
		return DEFAULT_PRIORITY
	if isinstance(priority, int):
		return priority if 1 <= priority <= 5 else DEFAULT_PRIORITY
	return PRIORITY_MAP.get(str(priority).strip().lower(), DEFAULT_PRIORITY)


def normalize_tags(tags: str | list | tuple | None) -> list[str]:
	"""Return a clean list of tag strings from a comma-separated string or list."""
	if not tags:
		return []
	if isinstance(tags, str):
		items = tags.split(",")
	else:
		items = list(tags)
	return [t.strip() for t in (str(i) for i in items) if t and t.strip()]


def redact_headers(headers: dict | None) -> dict:
	"""Return a copy of ``headers`` with sensitive values masked, for safe logging."""
	if not headers:
		return {}
	return {
		k: (_REDACTED if k.lower() in _SENSITIVE_HEADERS else v)
		for k, v in headers.items()
	}


def validate_server_url(url: str, *, allow_private: bool = True) -> str:
	"""Validate an ntfy server URL and return it normalised (no trailing slash).

	Enforces an ``http``/``https`` scheme with a hostname and rejects inline
	credentials. This is the practical SSRF guard: the global server URL is
	System-Manager-only, and per-user override URLs pass through here too.

	Args:
		url: The URL to validate.
		allow_private: When ``False``, also reject hosts that resolve to
			loopback/link-local/private/reserved ranges. Left ``True`` by
			default because self-hosted ntfy commonly lives on a private LAN.

	Raises:
		frappe.ValidationError: If the URL is malformed or disallowed.
	"""
	if not url or not isinstance(url, str):
		frappe.throw(_("NTFY Server URL is required."), frappe.ValidationError)

	parsed = urlparse(url.strip())
	if parsed.scheme not in ("http", "https"):
		frappe.throw(
			_("NTFY Server URL must start with http:// or https:// (got {0}).").format(
				parsed.scheme or "no scheme"
			),
			frappe.ValidationError,
		)
	if not parsed.hostname:
		frappe.throw(_("NTFY Server URL must include a hostname."), frappe.ValidationError)
	if parsed.username or parsed.password:
		frappe.throw(
			_("Put credentials in the Authentication fields, not in the URL."),
			frappe.ValidationError,
		)

	if not allow_private and _resolves_to_private(parsed.hostname):
		frappe.throw(
			_("NTFY Server URL resolves to a private/loopback address, which is not allowed."),
			frappe.ValidationError,
		)

	return url.strip().rstrip("/")


def _resolves_to_private(hostname: str) -> bool:
	"""Best-effort check whether ``hostname`` resolves to a non-public address."""
	try:
		infos = socket.getaddrinfo(hostname, None)
	except OSError:
		# Can't resolve — treat as suspicious when the caller asked to block private.
		return True
	for info in infos:
		addr = info[4][0]
		try:
			ip = ipaddress.ip_address(addr)
		except ValueError:
			continue
		if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
			return True
	return False


def strip_to_text(value: str | None, limit: int | None = None) -> str:
	"""Strip HTML tags, collapse whitespace, and optionally truncate.

	Used to turn HTML notification/email bodies into a clean plain-text push body.
	"""
	if not value:
		return ""
	text = " ".join(frappe.utils.strip_html_tags(value).split())
	return text[:limit] if limit else text


def get_logger():
	"""Return the NTFYnext site logger (integrates with Frappe's log files)."""
	return frappe.logger("ntfynext", allow_site=True, file_count=50)
