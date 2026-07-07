# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Scheduled tasks for NTFYnext.

:func:`retry_failed_notifications` runs on a cron and re-enqueues pushes whose
backoff timer has elapsed. The backoff schedule and the Failed/Retrying state
machine live on the ``NTFY Notification Log`` controller; this sweep only decides
*when* to try again.
"""

from __future__ import annotations

import frappe
from frappe.utils import now_datetime

# Cap per tick so a large backlog can't overwhelm a single scheduler run.
_MAX_PER_RUN = 500


def retry_failed_notifications() -> int:
	"""Re-enqueue every log in ``Retrying`` whose ``next_retry_at`` has passed.

	Idempotent: each job uses the same ``job_id`` as the original publish with
	``deduplicate=True``, so overlapping scheduler ticks never double-send.
	Returns the number of logs re-enqueued (handy for tests/telemetry).
	"""
	due = frappe.get_all(
		"NTFY Notification Log",
		filters={"status": "Retrying", "next_retry_at": ["<=", now_datetime()]},
		fields=["name", "user"],
		order_by="next_retry_at asc",
		limit=_MAX_PER_RUN,
	)
	for log in due:
		frappe.enqueue(
			"ntfynext.dispatch.publish_job",
			queue="short",
			job_id=f"ntfy-publish-{log.name}",
			deduplicate=True,
			log_name=log.name,
			user=log.user,
		)
	return len(due)
