# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Extend the standard ``Notification`` doctype with ntfy delivery.

Wired via the ``override_doctype_class`` hook (not a monkeypatch): the loader
enforces that this class subclasses ``Notification``. We override the single
channel-dispatch method, call ``super()`` so email/Slack/SMS/system behaviour is
untouched, then additionally push to ntfy when "Send via NTFY" is ticked —
reusing the inherited :meth:`get_list_of_recipients` so every recipient
mechanism (document field, role, assignees, cc/bcc) is honoured.
"""

from __future__ import annotations

import frappe
from frappe.email.doctype.notification.notification import (
	Notification,
	get_reference_doctype,
	get_reference_name,
)

# ntfy renders a plain-text body; cap it like Frappe's own push relay does.
_MAX_BODY = 1000


class NTFYNotification(Notification):
	def send_notification_by_channel(self, doc, context):
		"""Run the standard channel dispatch, then add ntfy if enabled."""
		send_ntfy = bool(self.get("send_via_ntfy"))
		if send_ntfy:
			# Signal the Email Queue mirror (if enabled) to skip the emails this
			# notification is about to queue — this precise path already covers
			# ntfy for the same recipients, so we must not double-send.
			frappe.flags.ntfynext_inline = True
		try:
			super().send_notification_by_channel(doc, context)
			if send_ntfy:
				self.send_ntfy_notification(doc, context)
		finally:
			if send_ntfy:
				frappe.flags.ntfynext_inline = False

	def send_ntfy_notification(self, doc, context) -> None:
		"""Push this notification to opted-in recipients (and any direct topic)."""
		try:
			recipients, cc, bcc = self.get_list_of_recipients(doc, context)
			users = list({*recipients, *cc, *bcc})
			topic = (self.get("ntfy_topic") or "").strip() or None
			if not users and not topic:
				return

			# Local import avoids any import-time coupling with the notification module.
			from ntfynext.api import notify

			notify(
				users=users or None,
				topic=topic,
				title=self._ntfy_title(context),
				message=self._ntfy_body(context),
				url=self._ntfy_click(doc),
				priority=self.get("ntfy_priority") or None,
				tags=self.get("ntfy_tags") or None,
				doctype=get_reference_doctype(doc),
				docname=get_reference_name(doc),
			)
		except Exception:
			# Never let ntfy break the underlying notification.
			self.log_error("NTFYnext: failed to send ntfy notification")

	# -- rendering helpers --

	def _ntfy_title(self, context) -> str:
		subject = self.subject or ""
		if "{" in subject:
			subject = frappe.render_template(self.subject, context)
		return frappe.utils.strip_html_tags(subject).strip() or self.name

	def _ntfy_body(self, context) -> str:
		body = frappe.render_template(self.message or "", context)
		body = frappe.utils.strip_html_tags(body)
		return " ".join(body.split())[:_MAX_BODY]

	def _ntfy_click(self, doc) -> str | None:
		ref_dt = get_reference_doctype(doc)
		ref_dn = get_reference_name(doc)
		if ref_dt and ref_dn:
			return frappe.utils.get_url_to_form(ref_dt, ref_dn)
		return None
