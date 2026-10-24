# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""backntfy client — talks to a backntfy admin-panel instance over its REST API.

backntfy (https://github.com/mithtech/backntfy) is a companion web UI that wraps
the ntfy CLI. When enabled in NTFY Settings, mith_ntfy calls it on User opt-in
to auto-provision an ntfy account and grant the user read-only access to their
generated topic — removing the manual "create user + grant ACL" step against a
locked-down (``NTFY_AUTH_DEFAULT_ACCESS=deny-all``) ntfy server.

All calls are single HTTP attempts and never raise; failures return a
:class:`BackntfyResult` with ``ok=False``. Retries are the caller's problem.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

import requests

from mith_ntfy.utils import get_logger

_MAX_BODY_LOG = 2_000
_DEFAULT_TIMEOUT = 10
# ntfy CLI generated passwords need >=6 chars; we use 32 hex = 128 bits entropy.
_GENERATED_PASSWORD_LENGTH = 32


@dataclass
class BackntfyResult:
	"""Uniform result shape for every backntfy call."""

	ok: bool
	status_code: int | None = None
	body: str = ""
	error: str | None = None
	duration: float = 0.0
	# Populated on successful user provisioning so the caller can persist it.
	generated_password: str | None = None


@dataclass
class BackntfyConfig:
	"""Subset of NTFY Settings that the client needs. Passed in explicitly so the
	client stays pure and testable (no ``frappe.get_single`` inside)."""

	url: str
	api_token: str
	timeout: int = _DEFAULT_TIMEOUT
	verify_ssl: bool = True


def _headers(config: BackntfyConfig) -> dict:
	return {
		"Authorization": f"Bearer {config.api_token}",
		"Content-Type": "application/json",
	}


def _base_url(config: BackntfyConfig) -> str:
	return config.url.rstrip("/")


def _request(config: BackntfyConfig, method: str, path: str, json_body: dict | None = None) -> BackntfyResult:
	"""Single HTTP attempt against backntfy. Never raises."""
	url = _base_url(config) + path
	logger = get_logger()
	started = time.monotonic()
	try:
		response = requests.request(
			method,
			url,
			json=json_body,
			headers=_headers(config),
			timeout=config.timeout or _DEFAULT_TIMEOUT,
			verify=config.verify_ssl,
		)
	except requests.exceptions.RequestException as exc:
		duration = time.monotonic() - started
		logger.warning(f"backntfy {method} {path} failed: {exc}")
		return BackntfyResult(ok=False, error=str(exc), duration=duration)

	duration = time.monotonic() - started
	body = (response.text or "")[:_MAX_BODY_LOG]
	ok = 200 <= response.status_code < 300
	error = None if ok else f"HTTP {response.status_code}: {body[:500]}"
	if ok:
		logger.info(f"backntfy {method} {path} ok ({response.status_code}, {duration * 1000:.0f}ms)")
	else:
		logger.warning(f"backntfy {method} {path} returned {error}")
	return BackntfyResult(
		ok=ok,
		status_code=response.status_code,
		body=body,
		error=error,
		duration=duration,
	)


def _generate_password() -> str:
	return secrets.token_hex(_GENERATED_PASSWORD_LENGTH // 2)


def test_connection(config: BackntfyConfig) -> BackntfyResult:
	"""GET /api/users — a cheap authenticated call. If it returns 200 the URL is
	reachable and the API token is accepted."""
	return _request(config, "GET", "/api/users")


def provision_user(config: BackntfyConfig, username: str, topic: str) -> BackntfyResult:
	"""Create the ntfy account and grant read-only ACL on ``topic``. Idempotent
	on the ACL side (backntfy overwrites) and tolerant of an already-existing
	user (any 4xx on the create call is treated as "already exists" and we
	proceed to the ACL grant).

	Returns a :class:`BackntfyResult` whose ``generated_password`` is populated
	when the create call succeeded (i.e. this is the first-time provisioning).
	On subsequent runs the password field is None and the caller keeps the
	previously stored value.
	"""
	password = _generate_password()
	create = _request(
		config,
		"POST",
		"/api/users",
		json_body={"username": username, "password": password, "role": "user"},
	)
	# 200 = created (fresh password to hand back); any 4xx = already exists.
	if not create.ok and (create.status_code is None or create.status_code < 400 or create.status_code >= 500):
		# 5xx / network / other unexpected failure — abort.
		return create

	grant = _request(
		config,
		"POST",
		"/api/access",
		json_body={"username": username, "topic": topic, "permission": "read-only"},
	)
	if not grant.ok:
		return grant

	# Only surface the generated password when the create call actually created
	# the user (200). On "already exists" the stored password is still valid.
	grant.generated_password = password if create.ok else None
	return grant


def deprovision_user(config: BackntfyConfig, username: str) -> BackntfyResult:
	"""Delete the ntfy account (and all its tokens + ACLs). Used when a user
	turns opt-in back off."""
	from urllib.parse import quote

	return _request(config, "DELETE", f"/api/users/{quote(username, safe='')}")
