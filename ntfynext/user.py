# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""User-related hooks for NTFYnext.

Auto-provisions an unguessable ntfy topic the first time a user opts in, so
notifications are private-by-default even on public ntfy servers. Users may
overwrite the generated topic with their own.
"""

from __future__ import annotations

import re

import frappe

_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]")


def ensure_topic(doc, method=None) -> None:
	"""``User.validate`` hook: generate a topic when NTFY is enabled and none is set."""
	# ``doc.get`` tolerates the custom fields not existing yet (pre-migrate).
	if doc.get("enable_ntfy") and not doc.get("ntfy_topic"):
		doc.ntfy_topic = generate_topic(doc.name)


def generate_topic(user: str) -> str:
	"""Build a hard-to-guess, ntfy-safe topic seeded from the user id.

	Format: ``ntfy-<slug>-<random>`` using only ``[A-Za-z0-9_-]`` (ntfy's
	allowed topic characters).
	"""
	local_part = (user or "user").split("@")[0]
	slug = _SLUG_RE.sub("", local_part)[:20] or "user"
	return f"ntfy-{slug}-{frappe.generate_hash(length=16)}"
