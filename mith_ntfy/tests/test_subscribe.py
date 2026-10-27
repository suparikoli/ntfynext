# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Integration tests for the subscribe link + QR helper."""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from mith_ntfy.api import get_subscribe_info


class TestSubscribeInfo(IntegrationTestCase):
	def setUp(self):
		frappe.db.set_single_value("NTFY Settings", {"enabled": 1, "server_url": "https://ntfy.example.com"})
		self.user = "ntfy_sub@example.com"
		if not frappe.db.exists("User", self.user):
			frappe.get_doc(
				{"doctype": "User", "email": self.user, "first_name": "S", "send_welcome_email": 0}
			).insert(ignore_permissions=True)

	def test_returns_url_and_qr(self):
		frappe.db.set_value("User", self.user, {"enable_ntfy": 1, "ntfy_topic": "sub-topic-x"})
		info = get_subscribe_info(self.user)
		self.assertEqual(info["url"], "https://ntfy.example.com/sub-topic-x")
		self.assertEqual(info["topic"], "sub-topic-x")
		self.assertEqual(info["server"], "https://ntfy.example.com")
		self.assertTrue(info["qr_svg"].strip().startswith("<svg"))

	def test_user_override_server_is_used(self):
		frappe.db.set_value(
			"User",
			self.user,
			{"enable_ntfy": 1, "ntfy_topic": "t2", "ntfy_override_server_url": "https://my.ntfy.io/"},
		)
		self.assertEqual(get_subscribe_info(self.user)["url"], "https://my.ntfy.io/t2")

	def test_empty_without_topic(self):
		frappe.db.set_value("User", self.user, {"ntfy_topic": ""})
		self.assertEqual(get_subscribe_info(self.user), {})
