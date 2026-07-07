# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Integration tests for the publish pipeline (HTTP mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from ntfynext.dispatch import enqueue_publish, publish_job
from ntfynext.providers.base import PushMessage


def _resp(status=200, text="{}"):
	return MagicMock(status_code=status, text=text)


@patch("ntfynext.providers.ntfy.get_logger", return_value=MagicMock())
class TestDispatch(IntegrationTestCase):
	def setUp(self):
		frappe.db.set_single_value(
			"NTFY Settings",
			{"enabled": 1, "server_url": "https://ntfy.example.com", "retry_count": 5, "auth_type": "None"},
		)

	def test_enqueue_creates_queued_log(self, _log):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "ref"}).insert(ignore_permissions=True)
		with patch("ntfynext.dispatch.frappe.enqueue") as menq:
			log = enqueue_publish(
				PushMessage(topic="t", title="Hi", message="body"),
				reference_doctype="ToDo",
				reference_name=todo.name,
			)
		self.assertIsNotNone(log)
		self.assertEqual(log.status, "Queued")
		self.assertEqual(log.topic, "t")
		self.assertEqual(log.reference_doctype, "ToDo")
		self.assertIn('"topic": "t"', log.payload)
		menq.assert_called_once()

	def test_disabled_is_noop(self, _log):
		frappe.db.set_single_value("NTFY Settings", "enabled", 0)
		with patch("ntfynext.dispatch.frappe.enqueue") as menq:
			log = enqueue_publish(PushMessage(topic="t", message="m"))
		self.assertIsNone(log)
		menq.assert_not_called()

	@patch("ntfynext.providers.ntfy.requests.post")
	def test_publish_job_success(self, mpost, _log):
		mpost.return_value = _resp(200)
		with patch("ntfynext.dispatch.frappe.enqueue"):
			log = enqueue_publish(PushMessage(topic="t", message="m"))
		publish_job(log.name)
		log.reload()
		self.assertEqual(log.status, "Success")
		self.assertEqual(log.response_code, 200)

	@patch("ntfynext.providers.ntfy.requests.post")
	def test_publish_job_failure_schedules_retry(self, mpost, _log):
		mpost.return_value = _resp(500, "server error")
		with patch("ntfynext.dispatch.frappe.enqueue"):
			log = enqueue_publish(PushMessage(topic="t", message="m"))
		publish_job(log.name)
		log.reload()
		self.assertEqual(log.status, "Retrying")
		self.assertEqual(log.retry_count, 1)
		self.assertIsNotNone(log.next_retry_at)
		self.assertTrue(log.error)

	@patch("ntfynext.providers.ntfy.requests.post")
	def test_headers_redacted_in_log(self, mpost, _log):
		frappe.db.set_single_value("NTFY Settings", {"auth_type": "Bearer"})
		# store an encrypted token on the single
		settings = frappe.get_single("NTFY Settings")
		settings.token = "tk_secret_value"
		settings.flags.ignore_permissions = True
		settings.save()
		with patch("ntfynext.dispatch.frappe.enqueue"):
			log = enqueue_publish(PushMessage(topic="t", message="m"))
		self.assertNotIn("tk_secret_value", log.headers or "")
		self.assertIn("REDACTED", log.headers or "")
