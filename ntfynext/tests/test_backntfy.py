# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Unit tests for the backntfy client (ntfynext.backntfy).

Pure unit tests: no Frappe DB, no real HTTP — ``requests.request`` is patched
and the logger is stubbed. Mirrors the style of test_ntfy_client.py.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from ntfynext.backntfy import (
	BackntfyConfig,
	BackntfyResult,
	deprovision_user,
	provision_user,
	test_connection,
)


def make_config(**overrides) -> BackntfyConfig:
	base = dict(
		url="https://backntfy.example.com",
		api_token="a" * 64,
		timeout=10,
		verify_ssl=True,
	)
	base.update(overrides)
	return BackntfyConfig(**base)


def _resp(status: int, text: str = "") -> MagicMock:
	return MagicMock(status_code=status, text=text)


@patch("ntfynext.backntfy.get_logger", return_value=MagicMock())
class TestTestConnection(unittest.TestCase):
	def test_success(self, _logger):
		with patch("ntfynext.backntfy.requests.request", return_value=_resp(200, '{"users":[]}')) as mp:
			result = test_connection(make_config())
		self.assertTrue(result.ok)
		self.assertEqual(result.status_code, 200)
		self.assertIsNone(result.error)
		# hits GET /api/users with Bearer token + JSON content type
		args, kwargs = mp.call_args
		self.assertEqual(args, ("GET", "https://backntfy.example.com/api/users"))
		self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + "a" * 64)
		self.assertTrue(kwargs["verify"])
		self.assertEqual(kwargs["timeout"], 10)

	def test_url_trailing_slash_stripped(self, _logger):
		cfg = make_config(url="https://backntfy.example.com/")
		with patch("ntfynext.backntfy.requests.request", return_value=_resp(200)) as mp:
			test_connection(cfg)
		self.assertEqual(mp.call_args[0][1], "https://backntfy.example.com/api/users")

	def test_wrong_token(self, _logger):
		with patch("ntfynext.backntfy.requests.request", return_value=_resp(401, '{"error":"not authenticated"}')):
			result = test_connection(make_config())
		self.assertFalse(result.ok)
		self.assertEqual(result.status_code, 401)
		self.assertIn("401", result.error)

	def test_network_failure(self, _logger):
		with patch("ntfynext.backntfy.requests.request", side_effect=requests.exceptions.ConnectTimeout("boom")):
			result = test_connection(make_config())
		self.assertFalse(result.ok)
		self.assertIsNone(result.status_code)
		self.assertIn("boom", result.error)


@patch("ntfynext.backntfy.get_logger", return_value=MagicMock())
class TestProvisionUser(unittest.TestCase):
	def test_success_creates_user_then_grants_acl(self, _logger):
		calls = []

		def fake_request(method, url, **kwargs):
			calls.append((method, url, kwargs["json"]))
			return _resp(200, '{"ok":true}')

		with patch("ntfynext.backntfy.requests.request", side_effect=fake_request):
			result = provision_user(make_config(), "alice@example.com", "ntfy-alice-abc123")

		self.assertTrue(result.ok)
		self.assertEqual(len(calls), 2)
		# first call: create user
		self.assertEqual(calls[0][0], "POST")
		self.assertEqual(calls[0][1], "https://backntfy.example.com/api/users")
		self.assertEqual(calls[0][2]["username"], "alice@example.com")
		self.assertEqual(calls[0][2]["role"], "user")
		self.assertEqual(len(calls[0][2]["password"]), 32)  # 32 hex chars
		# second call: grant access
		self.assertEqual(calls[1][0], "POST")
		self.assertEqual(calls[1][1], "https://backntfy.example.com/api/access")
		self.assertEqual(calls[1][2]["username"], "alice@example.com")
		self.assertEqual(calls[1][2]["topic"], "ntfy-alice-abc123")
		self.assertEqual(calls[1][2]["permission"], "read-only")
		# password is returned so the caller can persist it
		self.assertEqual(result.generated_password, calls[0][2]["password"])

	def test_user_already_exists_still_grants_acl(self, _logger):
		responses = [_resp(409, '{"error":"user already exists"}'), _resp(200)]
		with patch("ntfynext.backntfy.requests.request", side_effect=responses) as mp:
			result = provision_user(make_config(), "alice@example.com", "topic-x")
		self.assertTrue(result.ok)
		self.assertEqual(mp.call_count, 2)
		# no generated password surfaced when the create call didn't create anything
		self.assertIsNone(result.generated_password)

	def test_server_error_on_create_aborts(self, _logger):
		with patch("ntfynext.backntfy.requests.request", return_value=_resp(500, "boom")) as mp:
			result = provision_user(make_config(), "alice", "topic-x")
		self.assertFalse(result.ok)
		self.assertEqual(result.status_code, 500)
		# aborted before the ACL call
		self.assertEqual(mp.call_count, 1)

	def test_network_error_on_create_aborts(self, _logger):
		with patch("ntfynext.backntfy.requests.request", side_effect=requests.exceptions.ConnectionError("net")) as mp:
			result = provision_user(make_config(), "alice", "topic-x")
		self.assertFalse(result.ok)
		self.assertIsNone(result.status_code)
		self.assertEqual(mp.call_count, 1)

	def test_acl_failure_returned(self, _logger):
		responses = [_resp(200), _resp(400, '{"error":"invalid topic"}')]
		with patch("ntfynext.backntfy.requests.request", side_effect=responses):
			result = provision_user(make_config(), "alice", "bad topic")
		self.assertFalse(result.ok)
		self.assertEqual(result.status_code, 400)


@patch("ntfynext.backntfy.get_logger", return_value=MagicMock())
class TestDeprovisionUser(unittest.TestCase):
	def test_url_encodes_username(self, _logger):
		with patch("ntfynext.backntfy.requests.request", return_value=_resp(200)) as mp:
			result = deprovision_user(make_config(), "alice+test@example.com")
		self.assertTrue(result.ok)
		args, _kwargs = mp.call_args
		self.assertEqual(args[0], "DELETE")
		# @ + gets percent-encoded so it survives as a single path segment
		self.assertEqual(
			args[1],
			"https://backntfy.example.com/api/users/alice%2Btest%40example.com",
		)


class TestResultShape(unittest.TestCase):
	"""Guard the dataclass surface so tests + hook code both stay honest."""

	def test_defaults(self):
		r = BackntfyResult(ok=True)
		self.assertTrue(r.ok)
		self.assertIsNone(r.status_code)
		self.assertEqual(r.body, "")
		self.assertIsNone(r.error)
		self.assertEqual(r.duration, 0.0)
		self.assertIsNone(r.generated_password)


if __name__ == "__main__":
	unittest.main()
