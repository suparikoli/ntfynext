# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Integration tests for the Notification override (precise path)."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.model.base_document import get_controller
from frappe.tests import IntegrationTestCase


class TestNotificationOverride(IntegrationTestCase):
	def setUp(self):
		frappe.db.set_single_value("NTFY Settings", {"enabled": 1, "server_url": "https://ntfy.example.com"})

	def test_controller_is_overridden(self):
		from frappe.email.doctype.notification.notification import Notification

		ctrl = get_controller("Notification")
		self.assertTrue(issubclass(ctrl, Notification))
		self.assertEqual(ctrl.__name__, "NTFYNotification")

	@patch("ntfynext.api.notify")
	def test_send_via_ntfy_delegates_rendered_content(self, mnotify):
		notif = frappe.new_doc("Notification")
		notif.subject = "ToDo {{ doc.name }}"
		notif.message = "<p>Body <b>{{ doc.description }}</b></p>"
		notif.send_via_ntfy = 1
		notif.channel = "Email"
		notif.document_type = "ToDo"
		notif.ntfy_topic = "team-topic"
		notif.ntfy_priority = "high"

		todo = frappe.get_doc({"doctype": "ToDo", "description": "Desc"}).insert(ignore_permissions=True)
		notif.send_ntfy_notification(todo, {"doc": todo, "alert": notif, "comments": None})

		mnotify.assert_called_once()
		kwargs = mnotify.call_args.kwargs
		self.assertEqual(kwargs["title"], f"ToDo {todo.name}")
		self.assertEqual(kwargs["message"], "Body Desc")  # HTML stripped, whitespace collapsed
		self.assertEqual(kwargs["topic"], "team-topic")
		self.assertEqual(kwargs["priority"], "high")
		self.assertEqual(kwargs["doctype"], "ToDo")
		self.assertEqual(kwargs["docname"], todo.name)

	@patch("ntfynext.api.notify")
	def test_no_ntfy_when_flag_off(self, mnotify):
		notif = frappe.new_doc("Notification")
		notif.subject = "x"
		notif.message = "y"
		notif.send_via_ntfy = 0
		notif.channel = "Email"
		notif.document_type = "ToDo"
		todo = frappe.get_doc({"doctype": "ToDo", "description": "d"}).insert(ignore_permissions=True)
		# send_notification_by_channel with the flag off must not push ntfy
		with patch.object(notif.__class__.__bases__[0], "send_notification_by_channel"):
			notif.send_notification_by_channel(todo, {"doc": todo, "alert": notif})
		mnotify.assert_not_called()
