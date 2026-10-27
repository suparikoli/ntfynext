# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Integration tests for the retry backoff state machine on the log."""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from mith_ntfy.providers.base import ProviderResponse


class TestRetryBackoff(IntegrationTestCase):
	def _log(self):
		return frappe.get_doc(
			{"doctype": "NTFY Notification Log", "status": "Queued", "topic": "t"}
		).insert(ignore_permissions=True)

	def test_backoff_walks_to_failed(self):
		log = self._log()
		fail = ProviderResponse(ok=False, error="boom")
		statuses = []
		for _ in range(6):
			log.apply_response(fail, max_retries=5)
			statuses.append(log.status)
		self.assertEqual(statuses, ["Retrying"] * 5 + ["Failed"])
		self.assertEqual(log.retry_count, 6)
		self.assertIsNone(log.next_retry_at)

	def test_success_terminates(self):
		log = self._log()
		log.apply_response(ProviderResponse(ok=True, status_code=200, body="ok"), max_retries=5)
		self.assertEqual(log.status, "Success")
		self.assertEqual(log.response_code, 200)
		self.assertIsNone(log.next_retry_at)

	def test_respects_lower_max_retries(self):
		log = self._log()
		fail = ProviderResponse(ok=False, error="x")
		log.apply_response(fail, max_retries=1)  # rc1 Retrying
		self.assertEqual(log.status, "Retrying")
		log.apply_response(fail, max_retries=1)  # rc2 > max -> Failed
		self.assertEqual(log.status, "Failed")
