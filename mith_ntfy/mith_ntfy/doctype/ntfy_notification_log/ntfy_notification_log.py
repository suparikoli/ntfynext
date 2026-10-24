# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Controller for ``NTFY Notification Log``.

Each row records one ntfy push attempt. The document owns its own lifecycle:
:meth:`apply_response` records the outcome and, on failure, :meth:`schedule_retry`
moves it through the backoff schedule until it succeeds or is exhausted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime

if TYPE_CHECKING:
	from frappe.types import DF

	from mith_ntfy.providers.base import ProviderResponse

# Escalating retry delays (seconds): 1m → 5m → 30m → 2h → 24h.
RETRY_BACKOFF: tuple[int, ...] = (60, 300, 1800, 7200, 86400)


class NTFYNotificationLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.
	if TYPE_CHECKING:
		duration: DF.Float
		error: DF.SmallText | None
		headers: DF.Code | None
		next_retry_at: DF.Datetime | None
		payload: DF.Code | None
		provider: DF.Data | None
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		response: DF.Code | None
		response_code: DF.Int
		retry_count: DF.Int
		server: DF.Data | None
		status: DF.Literal["Queued", "Retrying", "Success", "Failed"]
		timestamp: DF.Datetime | None
		title: DF.Data | None
		topic: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	def apply_response(self, result: ProviderResponse, max_retries: int) -> None:
		"""Record a publish outcome; schedule a retry if it failed."""
		self.response_code = result.status_code
		self.response = result.body
		self.error = result.error
		self.duration = result.duration
		if result.ok:
			self.status = "Success"
			self.next_retry_at = None
		else:
			self.schedule_retry(max_retries)

	def schedule_retry(self, max_retries: int) -> None:
		"""Advance to the next backoff slot, or mark Failed when exhausted."""
		self.retry_count = (self.retry_count or 0) + 1
		idx = self.retry_count - 1
		if self.retry_count > max_retries or idx >= len(RETRY_BACKOFF):
			self.status = "Failed"
			self.next_retry_at = None
		else:
			self.status = "Retrying"
			self.next_retry_at = add_to_date(now_datetime(), seconds=RETRY_BACKOFF[idx])

	@staticmethod
	def create_log(**kwargs) -> NTFYNotificationLog:
		"""Insert a log row (system-owned, so permissions are bypassed).

		``payload``/``headers`` may be passed as dicts and are JSON-encoded.
		"""
		for key in ("payload", "headers"):
			value = kwargs.get(key)
			if value is not None and not isinstance(value, str):
				kwargs[key] = frappe.as_json(value)

		doc: NTFYNotificationLog = frappe.new_doc("NTFY Notification Log")
		doc.update(kwargs)
		if not doc.timestamp:
			doc.timestamp = now_datetime()
		# A log must never fail to record — tolerate a since-deleted reference doc.
		doc.flags.ignore_links = True
		doc.insert(ignore_permissions=True)
		return doc


def on_doctype_update():
	"""Index the columns the retry sweeper filters on."""
	frappe.db.add_index("NTFY Notification Log", ["status", "next_retry_at"])
