# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Publish pipeline: prepare → log → (enqueue | send now) → apply result.

Network calls always happen in a background worker (via :func:`enqueue_publish`),
so document saves and web requests are never blocked. :func:`publish_now` is the
synchronous variant used by the Test page/Test Connection where an immediate
response is wanted. Every attempt is recorded in ``NTFY Notification Log``.
"""

from __future__ import annotations

from email import message_from_string, policy

import frappe

from mith_ntfy.config import SETTINGS_DOCTYPE, get_ntfy_config
from mith_ntfy.mith_ntfy.doctype.ntfy_notification_log.ntfy_notification_log import (
	NTFYNotificationLog,
)
from mith_ntfy.providers.base import PushMessage
from mith_ntfy.providers.ntfy import NtfyProvider
from mith_ntfy.recipients import resolve_user_targets
from mith_ntfy.utils import get_logger, redact_headers, strip_to_text

_MIRROR_BODY = 1000


def enqueue_publish(
	message: PushMessage,
	*,
	user: str | None = None,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
):
	"""Log a Queued push and enqueue the background job. Returns the log (or None).

	Returns ``None`` (a no-op) when NTFY is globally disabled or unconfigured.
	The job is enqueued *after commit* so it only runs once the log row is
	durable and the surrounding transaction has succeeded.
	"""
	prepared = _prepare(message, user)
	if not prepared:
		return None
	config, provider, payload, headers = prepared

	log = NTFYNotificationLog.create_log(
		status="Queued",
		title=_title_for(message),
		user=user,
		topic=message.topic,
		server=config.server_url,
		provider=provider.name,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		payload=payload,
		headers=redact_headers(headers),
	)
	frappe.enqueue(
		"mith_ntfy.dispatch.publish_job",
		queue="short",
		enqueue_after_commit=True,
		job_id=f"ntfy-publish-{log.name}",
		deduplicate=True,
		log_name=log.name,
		user=user,
	)
	return log


def publish_job(log_name: str, user: str | None = None) -> None:
	"""Background job: send the payload stored on ``log_name`` and record the result."""
	log: NTFYNotificationLog = frappe.get_doc("NTFY Notification Log", log_name)
	if log.status not in ("Queued", "Retrying"):
		return

	config = get_ntfy_config(user or log.user)
	provider = NtfyProvider(config)
	payload = frappe.parse_json(log.payload) or {}

	result = provider.publish_payload(payload)
	max_retries = config.retry_count if config.retry_count is not None else 5
	log.apply_response(result, max_retries)
	log.save(ignore_permissions=True)
	if not frappe.flags.in_test:
		frappe.db.commit()


def publish_now(
	message: PushMessage,
	*,
	user: str | None = None,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
) -> dict:
	"""Synchronously publish ``message`` and record a log. Returns a result dict."""
	prepared = _prepare(message, user)
	if not prepared:
		return {"ok": False, "error": "NTFY is disabled or not configured.", "skipped": True}
	config, provider, payload, headers = prepared

	result = provider.publish_payload(payload)
	max_retries = config.retry_count if config.retry_count is not None else 5
	log = NTFYNotificationLog.create_log(
		status="Success" if result.ok else "Queued",
		title=_title_for(message),
		user=user,
		topic=message.topic,
		server=config.server_url,
		provider=provider.name,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		payload=payload,
		headers=redact_headers(headers),
	)
	log.apply_response(result, max_retries)
	log.save(ignore_permissions=True)
	return {
		"ok": result.ok,
		"status_code": result.status_code,
		"topic": message.topic,
		"server": config.server_url,
		"response": result.body,
		"error": result.error,
		"log": log.name,
	}


def _prepare(message: PushMessage, user: str | None):
	"""Resolve config, apply defaults to ``message``, and build payload/headers.

	Returns ``(config, provider, payload, headers)`` or ``None`` when NTFY is
	disabled or has no server configured.
	"""
	config = get_ntfy_config(user)
	if not config.enabled or not config.server_url:
		get_logger().debug(f"NTFY skip (enabled={config.enabled}, server={config.server_url!r})")
		return None

	# Layer global/user defaults under any per-message values.
	if not message.priority:
		message.priority = config.default_priority
	if not message.tags:
		message.tags = list(config.default_tags)
	if not message.icon:
		message.icon = config.default_icon_url
	if not message.click:
		message.click = config.default_click_url

	provider = NtfyProvider(config)
	return config, provider, provider.build_payload(message), provider.build_headers()


def _title_for(message: PushMessage) -> str:
	"""Short title for the log row."""
	return (message.title or message.message or "")[:140]


# ---------------------------------------------------------------------------
# Email Queue mirror — global "mirror all notification emails" (off by default)
# ---------------------------------------------------------------------------
def on_email_queued(doc, method=None) -> None:
	"""``Email Queue`` after_insert hook.

	A no-op unless the global mirror is enabled. Performs only cheap checks on the
	request/job path and hands the parsing + delivery to a background job so it
	never slows the code that queued the email.
	"""
	# The precise Notification path already handles this email's recipients.
	if frappe.flags.get("ntfynext_inline"):
		return
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_test:
		return
	if not _mirror_enabled():
		return

	frappe.enqueue(
		"mith_ntfy.dispatch.mirror_email",
		queue="short",
		enqueue_after_commit=True,
		job_id=f"ntfy-mirror-{doc.name}",
		deduplicate=True,
		email_queue=doc.name,
	)


def mirror_email(email_queue: str) -> None:
	"""Background job: mirror one queued email to opted-in recipients."""
	if not frappe.db.exists("Email Queue", email_queue):
		return
	doc = frappe.get_doc("Email Queue", email_queue)
	targets = resolve_user_targets([r.recipient for r in doc.recipients])
	if not targets:
		return

	subject, body = _parse_email(doc.message)
	ref_dt, ref_dn = doc.reference_doctype, doc.reference_name
	click = frappe.utils.get_url_to_form(ref_dt, ref_dn) if ref_dt and ref_dn else None

	for target in targets:
		enqueue_publish(
			PushMessage(topic=target.topic, title=subject or None, message=body, click=click),
			user=target.user,
			reference_doctype=ref_dt,
			reference_name=ref_dn,
		)


def _mirror_enabled() -> bool:
	"""True only when NTFY is enabled *and* the global email mirror is switched on."""
	return bool(frappe.get_cached_value(SETTINGS_DOCTYPE, SETTINGS_DOCTYPE, "enabled")) and bool(
		frappe.get_cached_value(SETTINGS_DOCTYPE, SETTINGS_DOCTYPE, "mirror_all_emails")
	)


def _parse_email(raw: str) -> tuple[str, str]:
	"""Best-effort ``(subject, plain-text body)`` extraction from a MIME string."""
	try:
		msg = message_from_string(raw or "", policy=policy.default)
		subject = msg["subject"] or ""
		if msg.is_multipart():
			plain = _first_part(msg, "text/plain")
			body = plain if plain else strip_to_text(_first_part(msg, "text/html") or "")
		else:
			content = msg.get_content()
			body = strip_to_text(content) if msg.get_content_type() == "text/html" else content
		return str(subject), strip_to_text(body, _MIRROR_BODY)
	except Exception:
		get_logger().warning("Mith ntfy: failed to parse email MIME for mirror")
		return "", ""


def _first_part(msg, content_type: str) -> str | None:
	"""Return the decoded content of the first MIME part of ``content_type``."""
	for part in msg.walk():
		if part.get_content_type() == content_type:
			try:
				return part.get_content()
			except Exception:
				return None
	return None
