# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Integration tests for config resolution (global + per-user overrides)."""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from mith_ntfy.config import get_ntfy_config


class TestConfig(IntegrationTestCase):
	def setUp(self):
		frappe.db.set_single_value(
			"NTFY Settings",
			{
				"enabled": 1,
				"server_url": "https://global.example.com",
				"default_priority": "low",
				"default_tags": "a,b",
				"auth_type": "None",
				"request_timeout": 7,
				"retry_count": 4,
			},
		)

	def test_global_config(self):
		c = get_ntfy_config()
		self.assertTrue(c.enabled)
		self.assertEqual(c.server_url, "https://global.example.com")
		self.assertEqual(c.default_priority, "low")
		self.assertEqual(c.default_tags, ["a", "b"])
		self.assertEqual(c.request_timeout, 7)
		self.assertEqual(c.retry_count, 4)

	def test_user_overrides_server_and_priority(self):
		user = "ntfy_cfg@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "C", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		frappe.db.set_value(
			"User",
			user,
			{"ntfy_override_server_url": "https://user.example.com", "ntfy_priority": "max", "ntfy_tags": "x"},
		)
		c = get_ntfy_config(user)
		self.assertEqual(c.server_url, "https://user.example.com")
		self.assertEqual(c.default_priority, "max")
		self.assertEqual(c.default_tags, ["x"])
