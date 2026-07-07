# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Provider abstraction for NTFYnext.

The dispatch/queue/log layers speak only to :class:`NotificationProvider` and
the provider-agnostic :class:`PushMessage`. Adding another channel later
(Telegram, Gotify, Discord, Matrix, …) means implementing one subclass and
registering it — no changes to dispatch, jobs, or the log doctype.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PushMessage:
	"""A single push notification, independent of the delivery provider.

	Field names follow ntfy's vocabulary because it is the richest superset, but
	every field is generic enough to map onto other providers (title/message/
	priority/tags/click are near-universal; a provider ignores what it can't use).
	"""

	topic: str
	message: str = ""
	title: str | None = None
	priority: str | int | None = None
	tags: list[str] = field(default_factory=list)
	click: str | None = None
	attach: str | None = None
	filename: str | None = None
	icon: str | None = None
	actions: list[dict] | None = None
	markdown: bool = False
	delay: str | None = None
	email: str | None = None
	call: str | None = None


@dataclass
class ProviderResponse:
	"""Outcome of a single publish attempt (never raises to the caller)."""

	ok: bool
	status_code: int | None = None
	body: str | None = None
	error: str | None = None
	duration: float = 0.0

	def as_log(self) -> dict:
		"""Return a dict of the response fields suitable for the log doctype."""
		return {
			"status": "Success" if self.ok else "Failed",
			"response_code": self.status_code,
			"response": self.body,
			"error": self.error,
			"duration": self.duration,
		}


class NotificationProvider(ABC):
	"""Interface every push provider implements."""

	#: Short machine name, e.g. ``"ntfy"``. Used in logs and settings.
	name: str = "base"

	@abstractmethod
	def publish(self, message: PushMessage) -> ProviderResponse:
		"""Send ``message`` in a single attempt and return a :class:`ProviderResponse`.

		Implementations MUST NOT raise for network/HTTP errors — they capture the
		failure in :class:`ProviderResponse` so the caller (background job) can
		decide whether to schedule a retry.
		"""
		raise NotImplementedError
