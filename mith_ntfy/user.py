# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""User-related hooks for Mith ntfy.

Auto-provisions an unguessable ntfy topic the first time a user opts in, so
notifications are private-by-default even on public ntfy servers. Users may
overwrite the generated topic with their own.

When ``NTFY Settings.backntfy_enabled`` is set, opting in also enqueues a
background job that creates an ntfy account on the linked backntfy instance
and grants the user read-only access to their topic.
"""

from __future__ import annotations

import re

import frappe

from mith_ntfy.utils import get_logger

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


def sync_backntfy(doc, method=None) -> None:
	"""``User.on_update`` hook: enqueue backntfy provisioning when needed.

	Only fires when NTFY Settings has ``backntfy_enabled`` on and the user is
	opted into ntfy with a topic. Idempotent — a user with ``ntfy_provisioned``
	already true and an unchanged topic is skipped.

	The actual HTTP call is deferred to a background job so a slow or dead
	backntfy never blocks a User save. Failures land in the mith_ntfy logger,
	not in front of the person editing the User.
	"""
	if not doc.get("enable_ntfy") or not doc.get("ntfy_topic"):
		return

	settings = frappe.get_cached_doc("NTFY Settings")
	if not settings.get("backntfy_enabled") or not settings.get("backntfy_url"):
		return

	needs_provision = not doc.get("ntfy_provisioned") or _topic_changed(doc)
	if not needs_provision:
		return

	frappe.enqueue(
		"mith_ntfy.user._provision_via_backntfy",
		queue="short",
		enqueue_after_commit=True,
		user_name=doc.name,
		topic=doc.ntfy_topic,
	)


def _topic_changed(doc) -> bool:
	"""True when this save changed ``ntfy_topic``. ``get_doc_before_save`` is
	the standard Frappe way to compare against the pre-save snapshot."""
	before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	if not before:
		return False
	return (before.get("ntfy_topic") or "") != (doc.get("ntfy_topic") or "")


def _provision_via_backntfy(user_name: str, topic: str) -> None:
	"""Background job body — kept module-level so ``frappe.enqueue`` can import
	it by dotted name. Fetches the current settings, calls backntfy, and
	persists the outcome back to the User via ``db_set`` (no full save, no
	revalidation, no cascade)."""
	from mith_ntfy.backntfy import BackntfyConfig, provision_user

	settings = frappe.get_cached_doc("NTFY Settings")
	if not settings.get("backntfy_enabled") or not settings.get("backntfy_url"):
		return

	api_token = settings.get_password("backntfy_api_token", raise_exception=False) or ""
	if not api_token:
		get_logger().warning(
			f"backntfy provisioning skipped for {user_name}: no backntfy_api_token in NTFY Settings"
		)
		return

	config = BackntfyConfig(
		url=settings.backntfy_url,
		api_token=api_token,
		timeout=settings.request_timeout or 10,
		verify_ssl=bool(settings.verify_ssl),
	)
	result = provision_user(config, user_name, topic)

	logger = get_logger()
	if not result.ok:
		logger.warning(
			f"backntfy provisioning FAILED for {user_name} topic={topic}: {result.error}"
		)
		return

	# ``db_set`` writes without triggering doc events, so this doesn't
	# re-enter sync_backntfy from the same worker.
	frappe.db.set_value("User", user_name, "ntfy_provisioned", 1, update_modified=False)
	if result.generated_password:
		user_doc = frappe.get_doc("User", user_name)
		user_doc.db_set(
			"ntfy_client_password", result.generated_password, update_modified=False
		)
	frappe.db.commit()
	logger.info(f"backntfy provisioning ok for {user_name} topic={topic}")
