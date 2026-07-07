# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Controller for the ``NTFY Settings`` singleton.

Holds the global NTFYnext configuration (server, auth, defaults, retry policy)
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
		# Lazy import keeps this module loadable even before ntfynext.utils lands.
		from ntfynext.utils import validate_server_url

		if self.server_url:
			self.server_url = self.server_url.strip().rstrip("/")
			# Raises frappe.ValidationError on an unsafe/malformed URL.
			validate_server_url(self.server_url)

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

		from ntfynext.config import get_ntfy_config
		from ntfynext.providers.ntfy import NtfyMessage, NtfyProvider

		topic = (topic or self.test_topic or _random_test_topic()).strip()
		config = get_ntfy_config()  # global config, no per-user overrides

		provider = NtfyProvider(config)
		message = NtfyMessage(
			topic=topic,
			title=_("NTFYnext Test"),
			message=_("If you can read this, NTFYnext is configured correctly. 🎉"),
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


def _random_test_topic() -> str:
	"""Generate a hard-to-guess one-off topic for connection tests."""
	return f"ntfynext-test-{frappe.generate_hash(length=12)}"
