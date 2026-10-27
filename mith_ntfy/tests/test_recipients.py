# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Integration tests for recipient → topic resolution."""

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from mith_ntfy.recipients import resolve_user_targets


class TestRecipients(IntegrationTestCase):
	def _user(self, email, **prefs):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": "T", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		# set_value bypasses the auto-topic validate hook, so tests fully control prefs
		frappe.db.set_value("User", email, prefs)
		return email

	def test_opted_in_resolves(self):
		e = self._user("ntfy_in@example.com", enable_ntfy=1, ntfy_topic="topic-in", ntfy_silent_mode=0)
		targets = resolve_user_targets([e])
		self.assertEqual(len(targets), 1)
		self.assertEqual(targets[0].user, e)
		self.assertEqual(targets[0].topic, "topic-in")

	def test_opted_out_skipped(self):
		e = self._user("ntfy_out@example.com", enable_ntfy=0, ntfy_topic="x")
		self.assertEqual(resolve_user_targets([e]), [])

	def test_silent_skipped(self):
		e = self._user("ntfy_silent@example.com", enable_ntfy=1, ntfy_topic="x", ntfy_silent_mode=1)
		self.assertEqual(resolve_user_targets([e]), [])

	def test_no_topic_skipped(self):
		e = self._user("ntfy_notopic@example.com", enable_ntfy=1, ntfy_topic="", ntfy_silent_mode=0)
		self.assertEqual(resolve_user_targets([e]), [])

	def test_dedupe_and_unknown(self):
		e = self._user("ntfy_dup@example.com", enable_ntfy=1, ntfy_topic="t", ntfy_silent_mode=0)
		targets = resolve_user_targets([e, e, "does-not-exist@example.com", ""])
		self.assertEqual(len(targets), 1)
