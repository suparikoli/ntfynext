# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Recipient → ntfy topic resolution.

Turns a list of recipients (Frappe User ids or bare email addresses) into the
subset that has opted in to ntfy, is not in silent mode, and has a topic set.
This is the single place that decides *who actually gets a push*.
"""

from __future__ import annotations

from dataclasses import dataclass

import frappe


@dataclass(frozen=True)
class UserTarget:
	"""A resolved, deliverable target."""

	user: str
	topic: str


def resolve_user_targets(recipients) -> list[UserTarget]:
	"""Return deliverable :class:`UserTarget` objects for ``recipients``.

	Each recipient may be a User id or an email address. Users that are unknown,
	opted out, silenced, or missing a topic are skipped. Duplicates collapse.
	"""
	targets: dict[str, UserTarget] = {}
	for recipient in _dedupe(recipients):
		user = _to_user(recipient)
		if not user or user in targets:
			continue
		prefs = get_user_prefs(user)
		if prefs.get("enable_ntfy") and prefs.get("ntfy_topic") and not prefs.get("ntfy_silent_mode"):
			targets[user] = UserTarget(user=user, topic=prefs["ntfy_topic"])
	return list(targets.values())


def get_user_prefs(user: str) -> dict:
	"""Return a user's NTFY preference fields (empty dict if the user is unknown)."""
	return (
		frappe.db.get_value(
			"User",
			user,
			["enable_ntfy", "ntfy_topic", "ntfy_silent_mode"],
			as_dict=True,
		)
		or {}
	)


def _to_user(recipient: str) -> str | None:
	"""Map a recipient string to a User id (User name == email in Frappe)."""
	if not recipient:
		return None
	recipient = recipient.strip()
	if frappe.db.exists("User", recipient):
		return recipient
	# Fall back to an email lookup for non-id recipients.
	return frappe.db.get_value("User", {"email": recipient}, "name")


def _dedupe(items) -> list[str]:
	seen: dict[str, None] = {}
	for item in items or []:
		if item and item not in seen:
			seen[item] = None
	return list(seen)
