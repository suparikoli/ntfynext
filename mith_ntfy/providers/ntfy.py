# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""ntfy provider — publishes a :class:`PushMessage` to any ntfy server.

Uses ntfy's JSON publishing API (``POST {server}/`` with a JSON body) rather
than the header-based API, so Unicode titles/messages and every mapped field
work without RFC-2047 header encoding. A single publish is one HTTP attempt;
retries are owned by the background-job layer.
"""

from __future__ import annotations

import base64
import time
from typing import TYPE_CHECKING

import requests

from mith_ntfy.providers.base import NotificationProvider, ProviderResponse, PushMessage
from mith_ntfy.utils import get_logger, normalize_tags, priority_to_int

if TYPE_CHECKING:
	from mith_ntfy.config import ResolvedConfig

# Readable alias — ntfy callers can spell it NtfyMessage.
NtfyMessage = PushMessage

_MAX_BODY_LOG = 10_000  # cap stored response bodies


class NtfyProvider(NotificationProvider):
	"""Publish notifications to an ntfy server."""

	name = "ntfy"

	def __init__(self, config: ResolvedConfig):
		self.config = config

	# -- public builders (also used by the job layer for redacted logging) --

	def build_payload(self, message: PushMessage) -> dict:
		"""Map a :class:`PushMessage` onto an ntfy JSON payload."""
		payload: dict = {
			"topic": message.topic,
			"message": message.message or "",
			"priority": priority_to_int(message.priority),
		}
		if message.title:
			payload["title"] = message.title

		tags = normalize_tags(message.tags)
		if tags:
			payload["tags"] = tags

		# Direct 1:1 optional fields.
		for attr in ("click", "attach", "filename", "icon", "delay", "email", "call"):
			value = getattr(message, attr, None)
			if value:
				payload[attr] = value

		if message.actions:
			payload["actions"] = message.actions
		if message.markdown:
			payload["markdown"] = True

		return payload

	def build_headers(self) -> dict:
		"""Build request headers including the Authorization header (if any)."""
		headers = {"Content-Type": "application/json"}
		auth_type = (self.config.auth_type or "None").strip()

		if auth_type == "Basic" and self.config.username is not None:
			raw = f"{self.config.username or ''}:{self.config.password or ''}".encode()
			headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
		elif auth_type == "Bearer" and self.config.token:
			headers["Authorization"] = f"Bearer {self.config.token}"

		return headers

	# -- transport --

	def publish(self, message: PushMessage) -> ProviderResponse:
		"""Publish ``message`` in a single HTTP attempt. Never raises."""
		return self.publish_payload(self.build_payload(message))

	def publish_payload(self, payload: dict) -> ProviderResponse:
		"""Publish a pre-built ntfy JSON payload (used by the retry job to resend
		the exact stored payload). Single attempt, never raises."""
		url = self.config.server_url.rstrip("/") + "/"
		headers = self.build_headers()
		logger = get_logger()
		topic = payload.get("topic", "?")

		started = time.monotonic()
		try:
			response = requests.post(
				url,
				json=payload,
				headers=headers,
				timeout=self.config.request_timeout or 10,
				verify=self.config.verify_ssl,
			)
		except requests.exceptions.RequestException as exc:
			duration = time.monotonic() - started
			logger.warning(f"ntfy publish to topic '{topic}' failed: {exc}")
			return ProviderResponse(ok=False, error=str(exc), duration=duration)

		duration = time.monotonic() - started
		body = (response.text or "")[:_MAX_BODY_LOG]
		ok = 200 <= response.status_code < 300
		error = None if ok else f"HTTP {response.status_code}: {body[:500]}"
		if ok:
			logger.info(
				f"ntfy publish to topic '{topic}' ok "
				f"({response.status_code}, {duration * 1000:.0f}ms)"
			)
		else:
			logger.warning(f"ntfy publish to topic '{topic}' returned {error}")
		return ProviderResponse(
			ok=ok,
			status_code=response.status_code,
			body=body,
			error=error,
			duration=duration,
		)
