# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Public API surface for Mith ntfy.

Developer helpers::

    from mith_ntfy import notify

    notify(users=["Administrator"], title="Lead Assigned",
           message="A new lead has been assigned.", url="/app/lead/LEAD-0001")

    notify(topic="sales-team", title="New Opportunity", message="...")

Plus the whitelisted desk endpoints used by the Test page and the document menu.
"""

from __future__ import annotations

import frappe
from frappe import _

from mith_ntfy.dispatch import enqueue_publish, publish_now
from mith_ntfy.providers.base import PushMessage
from mith_ntfy.recipients import get_user_prefs, resolve_user_targets
from mith_ntfy.utils import normalize_tags

_SEND_ROLES = ("System Manager", "NTFY Manager")


# ---------------------------------------------------------------------------
# Developer API
# ---------------------------------------------------------------------------
def notify(
	users=None,
	topic: str | None = None,
	title: str | None = None,
	message: str | None = None,
	url: str | None = None,
	priority=None,
	tags=None,
	doctype: str | None = None,
	docname: str | None = None,
	**kwargs,
) -> list[str]:
	"""Queue ntfy push notifications. Returns the created log names.

	Args:
		users: User ids / emails to notify (only opted-in, non-silent users with
			a topic receive a push).
		topic: Publish directly to a fixed topic (e.g. a shared team topic), in
			addition to any ``users``.
		title, message: Notification title and body.
		url: Click-through URL (maps to ntfy ``click``).
		priority: ntfy priority name/int; falls back to the configured default.
		tags: Comma string or list of ntfy tags.
		doctype, docname: Originating document, linked on each log.
		**kwargs: Extra ntfy fields — ``icon``, ``attach``, ``filename``,
			``actions``, ``markdown``, ``delay``, ``email``, ``call``.
	"""
	logs = []
	if topic:
		logs.append(
			enqueue_publish(
				_build(topic, title, message, url, priority, tags, kwargs),
				reference_doctype=doctype,
				reference_name=docname,
			)
		)
	for target in resolve_user_targets(_as_list(users)):
		logs.append(
			enqueue_publish(
				_build(target.topic, title, message, url, priority, tags, kwargs),
				user=target.user,
				reference_doctype=doctype,
				reference_name=docname,
			)
		)
	return [log.name for log in logs if log]


def send_notification(
	user: str,
	title: str | None = None,
	message: str | None = None,
	url: str | None = None,
	priority=None,
	tags=None,
) -> list[str]:
	"""Convenience wrapper: notify a single user."""
	return notify(users=[user], title=title, message=message, url=url, priority=priority, tags=tags)


def publish(
	topic: str,
	message: str | None = None,
	title: str | None = None,
	url: str | None = None,
	priority=None,
	tags=None,
	**kwargs,
) -> list[str]:
	"""Convenience wrapper: publish directly to a topic."""
	return notify(
		topic=topic, title=title, message=message, url=url, priority=priority, tags=tags, **kwargs
	)


# ---------------------------------------------------------------------------
# Whitelisted desk endpoints
# ---------------------------------------------------------------------------
@frappe.whitelist()
def send_test(
	user: str | None = None,
	topic: str | None = None,
	title: str | None = None,
	message: str | None = None,
	priority=None,
	tags=None,
	url: str | None = None,
) -> dict:
	"""Send a one-off test push synchronously and return the server response.

	Used by the NTFY Test page. Resolves ``user``'s topic when ``topic`` is
	omitted.
	"""
	frappe.only_for(_SEND_ROLES)
	if not topic and user:
		topic = get_user_prefs(user).get("ntfy_topic")
	if not topic:
		frappe.throw(_("Provide a topic, or a user who has an NTFY topic configured."))

	message_obj = PushMessage(
		topic=topic,
		title=title or _("NTFY Test"),
		message=message or _("Test notification from Mith ntfy."),
		click=url,
		priority=priority,
		tags=normalize_tags(tags),
	)
	return publish_now(message_obj, user=user)


@frappe.whitelist()
def send_manual(
	doctype: str | None = None,
	docname: str | None = None,
	title: str | None = None,
	message: str | None = None,
	users=None,
	topic: str | None = None,
	priority=None,
	tags=None,
	url: str | None = None,
) -> dict:
	"""Manually send a notification (used by the "Send NTFY Notification" menu).

	Requires a send role and read access to the referenced document.
	"""
	frappe.only_for(_SEND_ROLES)
	if doctype and docname:
		frappe.get_doc(doctype, docname).check_permission("read")
		if not url:
			url = frappe.utils.get_url_to_form(doctype, docname)

	names = notify(
		users=_as_list(frappe.parse_json(users) if isinstance(users, str) else users),
		topic=topic,
		title=title,
		message=message,
		url=url,
		priority=priority,
		tags=normalize_tags(tags),
		doctype=doctype,
		docname=docname,
	)
	return {"queued": len(names), "logs": names}


def has_app_permission() -> bool:
	"""Return whether the Mith ntfy tile should appear on the ``/apps`` screen.

	Shown to Administrators and anyone holding the ``System Manager`` or
	``NTFY Manager`` role. Kept independent of the NTFY doctypes so it is safe
	to evaluate before/without them.
	"""
	if frappe.session.user == "Administrator":
		return True
	return bool(set(frappe.get_roles()) & {"System Manager", "NTFY Manager"})


@frappe.whitelist()
def get_subscribe_info(user: str | None = None) -> dict:
	"""Return the ntfy subscribe URL + an inline QR SVG for a user's topic.

	Powers the one-tap "Subscribe" card on the User → NTFY tab. Users may fetch
	their own; System Managers may fetch anyone's. Returns an empty dict when the
	user has no topic yet.
	"""
	user = user or frappe.session.user
	if user != frappe.session.user:
		frappe.only_for("System Manager")

	topic = (frappe.db.get_value("User", user, "ntfy_topic") or "").strip()
	if not topic:
		return {}

	server = (
		frappe.db.get_value("User", user, "ntfy_override_server_url")
		or frappe.get_cached_value("NTFY Settings", "NTFY Settings", "server_url")
		or "https://ntfy.sh"
	).rstrip("/")
	url = f"{server}/{topic}"
	return {"url": url, "topic": topic, "server": server, "qr_svg": _qr_svg(url)}


def _qr_svg(data: str) -> str:
	"""Render ``data`` as an inline SVG QR code (no external requests, CSP-safe)."""
	import io

	import pyqrcode

	buf = io.BytesIO()
	pyqrcode.create(data).svg(
		buf,
		scale=4,
		xmldecl=False,
		svgns=True,
		background="#ffffff",
		module_color="#111111",
		quiet_zone=2,
	)
	return buf.getvalue().decode("utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build(topic, title, message, url, priority, tags, extra: dict) -> PushMessage:
	"""Assemble a :class:`PushMessage` from call arguments."""
	return PushMessage(
		topic=topic,
		title=title,
		message=message or "",
		click=url,
		priority=priority,
		tags=tags or [],
		icon=extra.get("icon"),
		attach=extra.get("attach"),
		filename=extra.get("filename"),
		actions=extra.get("actions"),
		markdown=bool(extra.get("markdown", False)),
		delay=extra.get("delay"),
		email=extra.get("email"),
		call=extra.get("call"),
	)


def _as_list(value) -> list:
	"""Coerce ``None``/scalar/list into a list."""
	if value is None:
		return []
	if isinstance(value, (list, tuple)):
		return list(value)
	return [value]
