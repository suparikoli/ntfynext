# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Controller for the ``NTFY Settings`` singleton.

Holds the global Mith ntfy configuration (server, auth, defaults, retry policy)
and exposes a whitelisted :meth:`NTFYSettings.test_connection` used by the
"Test Connection" button and the NTFY Test page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.types import DF


class NTFYSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.
	if TYPE_CHECKING:
		auth_type: DF.Literal["None", "Basic", "Bearer"]
		backntfy_api_token: DF.Password | None
		backntfy_enabled: DF.Check
		backntfy_url: DF.Data | None
		default_click_url: DF.Data | None
		default_icon_url: DF.Data | None
		default_priority: DF.Literal["min", "low", "default", "high", "max"]
		default_tags: DF.Data | None
		enabled: DF.Check
		mirror_all_emails: DF.Check
		password: DF.Password | None
		request_timeout: DF.Int
		retry_count: DF.Int
		server_url: DF.Data | None
		test_topic: DF.Data | None
		token: DF.Password | None
		username: DF.Data | None
		verify_ssl: DF.Check
	# end: auto-generated types

	def validate(self) -> None:
		"""Normalise and sanity-check the settings before saving."""
		# Lazy import keeps this module loadable even before mith_ntfy.utils lands.
		from mith_ntfy.utils import validate_server_url

		if self.server_url:
			self.server_url = self.server_url.strip().rstrip("/")
			# Raises frappe.ValidationError on an unsafe/malformed URL.
			validate_server_url(self.server_url)

		if self.backntfy_url:
			self.backntfy_url = self.backntfy_url.strip().rstrip("/")
			validate_server_url(self.backntfy_url)

		if self.request_timeout is not None and self.request_timeout <= 0:
			self.request_timeout = 10
		if self.retry_count is not None and self.retry_count < 0:
			self.retry_count = 0

	@frappe.whitelist()
	def test_connection(self, topic: str | None = None) -> dict:
		"""Publish a test message using the current settings and return the result.

		Args:
			topic: Topic to publish to. Falls back to ``test_topic``; if both are
				empty a random one-off topic is generated and returned so the
				admin knows where to look.

		Returns:
			A JSON-serialisable dict with ``ok``, ``status_code``, ``topic``,
			``server`` and ``response`` (or ``error``).
		"""
		frappe.only_for("System Manager")

		from mith_ntfy.config import get_ntfy_config
		from mith_ntfy.providers.ntfy import NtfyMessage, NtfyProvider

		topic = (topic or self.test_topic or _random_test_topic()).strip()
		config = get_ntfy_config()  # global config, no per-user overrides

		provider = NtfyProvider(config)
		message = NtfyMessage(
			topic=topic,
			title=_("Mith ntfy Test"),
			message=_("If you can read this, Mith ntfy is configured correctly. 🎉"),
			priority=config.default_priority,
			tags=["white_check_mark"],
		)
		result = provider.publish(message)
		return {
			"ok": result.ok,
			"status_code": result.status_code,
			"topic": topic,
			"server": config.server_url,
			"response": result.body,
			"error": result.error,
		}


	@frappe.whitelist()
	def test_backntfy_connection(self) -> dict:
		"""Verify backntfy is reachable and the API token is accepted.

		Uses ``GET /api/users`` — the cheapest authenticated endpoint. A 200
		means URL + token are both good; a 401 means the token is wrong; a
		network error is surfaced as ``ok: False`` with the message.
		"""
		frappe.only_for("System Manager")

		from mith_ntfy.backntfy import BackntfyConfig, test_connection

		if not self.backntfy_url:
			return {"ok": False, "error": _("backntfy URL is not set")}

		api_token = self.get_password("backntfy_api_token", raise_exception=False) or ""
		if not api_token:
			return {"ok": False, "error": _("backntfy API token is not set")}

		config = BackntfyConfig(
			url=self.backntfy_url,
			api_token=api_token,
			timeout=self.request_timeout or 10,
			verify_ssl=bool(self.verify_ssl),
		)
		result = test_connection(config)
		return {
			"ok": result.ok,
			"status_code": result.status_code,
			"url": self.backntfy_url,
			"error": result.error,
		}


def _random_test_topic() -> str:
	"""Generate a hard-to-guess one-off topic for connection tests."""
	return f"ntfynext-test-{frappe.generate_hash(length=12)}"
