# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""Unit tests for the NTFYnext transport: pure helpers + the ntfy provider.

These avoid the database: the provider's HTTP call and logger are mocked, so
the suite exercises payload/header/priority mapping and error handling in
isolation.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from ntfynext.config import ResolvedConfig
from ntfynext.providers.ntfy import NtfyMessage, NtfyProvider
from ntfynext.utils import normalize_tags, priority_to_int, redact_headers, validate_server_url


def make_config(**overrides) -> ResolvedConfig:
	base = dict(
		enabled=True,
		server_url="https://ntfy.example.com",
		auth_type="None",
		username=None,
		password=None,
		token=None,
		default_priority="default",
		default_tags=[],
		request_timeout=10,
		verify_ssl=True,
		retry_count=5,
	)
	base.update(overrides)
	return ResolvedConfig(**base)


class TestPriorityMapping(unittest.TestCase):
	def test_names(self):
		self.assertEqual(priority_to_int("min"), 1)
		self.assertEqual(priority_to_int("low"), 2)
		self.assertEqual(priority_to_int("default"), 3)
		self.assertEqual(priority_to_int("high"), 4)
		self.assertEqual(priority_to_int("max"), 5)

	def test_case_insensitive_and_numeric_string(self):
		self.assertEqual(priority_to_int("HIGH"), 4)
		self.assertEqual(priority_to_int("5"), 5)

	def test_ints_and_bounds(self):
		self.assertEqual(priority_to_int(4), 4)
		self.assertEqual(priority_to_int(9), 3)  # out of range → default
		self.assertEqual(priority_to_int(0), 3)

	def test_missing_and_unknown(self):
		self.assertEqual(priority_to_int(None), 3)
		self.assertEqual(priority_to_int(""), 3)
		self.assertEqual(priority_to_int("urgent"), 3)


class TestTagNormalization(unittest.TestCase):
	def test_comma_string(self):
		self.assertEqual(normalize_tags("warning, skull ,,fire"), ["warning", "skull", "fire"])

	def test_list_and_empty(self):
		self.assertEqual(normalize_tags(["a", " b ", ""]), ["a", "b"])
		self.assertEqual(normalize_tags(None), [])
		self.assertEqual(normalize_tags(""), [])


class TestRedaction(unittest.TestCase):
	def test_masks_authorization(self):
		out = redact_headers({"Content-Type": "application/json", "Authorization": "Bearer secret"})
		self.assertEqual(out["Authorization"], "***REDACTED***")
		self.assertEqual(out["Content-Type"], "application/json")

	def test_empty(self):
		self.assertEqual(redact_headers(None), {})


class TestUrlValidation(unittest.TestCase):
	def test_valid_and_normalised(self):
		self.assertEqual(validate_server_url("https://ntfy.sh/"), "https://ntfy.sh")
		self.assertEqual(validate_server_url(" http://n.co "), "http://n.co")

	def test_rejects_bad_scheme(self):
		with self.assertRaises(Exception):
			validate_server_url("ftp://ntfy.sh")

	def test_rejects_missing_host(self):
		with self.assertRaises(Exception):
			validate_server_url("https://")

	def test_rejects_inline_credentials(self):
		with self.assertRaises(Exception):
			validate_server_url("https://user:pass@ntfy.sh")


class TestBuildPayload(unittest.TestCase):
	def setUp(self):
		self.provider = NtfyProvider(make_config())

	def test_minimal(self):
		payload = self.provider.build_payload(NtfyMessage(topic="t", message="hello"))
		self.assertEqual(payload["topic"], "t")
		self.assertEqual(payload["message"], "hello")
		self.assertEqual(payload["priority"], 3)
		self.assertNotIn("title", payload)
		self.assertNotIn("tags", payload)

	def test_full_mapping(self):
		msg = NtfyMessage(
			topic="alerts",
			message="body",
			title="Title",
			priority="high",
			tags="warning,skull",
			click="https://x/y",
			attach="https://x/f.pdf",
			filename="f.pdf",
			icon="https://x/i.png",
			actions=[{"action": "view", "label": "Open", "url": "https://x"}],
			markdown=True,
			delay="30min",
			email="a@b.co",
			call="+123",
		)
		p = self.provider.build_payload(msg)
		self.assertEqual(p["title"], "Title")
		self.assertEqual(p["priority"], 4)
		self.assertEqual(p["tags"], ["warning", "skull"])
		self.assertEqual(p["click"], "https://x/y")
		self.assertEqual(p["attach"], "https://x/f.pdf")
		self.assertEqual(p["filename"], "f.pdf")
		self.assertEqual(p["icon"], "https://x/i.png")
		self.assertEqual(p["delay"], "30min")
		self.assertEqual(p["email"], "a@b.co")
		self.assertEqual(p["call"], "+123")
		self.assertTrue(p["markdown"])
		self.assertEqual(len(p["actions"]), 1)

	def test_markdown_omitted_when_false(self):
		p = self.provider.build_payload(NtfyMessage(topic="t", markdown=False))
		self.assertNotIn("markdown", p)


class TestBuildHeaders(unittest.TestCase):
	def test_none(self):
		h = NtfyProvider(make_config(auth_type="None")).build_headers()
		self.assertNotIn("Authorization", h)
		self.assertEqual(h["Content-Type"], "application/json")

	def test_basic(self):
		h = NtfyProvider(make_config(auth_type="Basic", username="u", password="p")).build_headers()
		# base64("u:p") == "dTpw"
		self.assertEqual(h["Authorization"], "Basic dTpw")

	def test_bearer(self):
		h = NtfyProvider(make_config(auth_type="Bearer", token="tk_abc")).build_headers()
		self.assertEqual(h["Authorization"], "Bearer tk_abc")


@patch("ntfynext.providers.ntfy.get_logger", return_value=MagicMock())
class TestPublish(unittest.TestCase):
	def _run(self, mock_post_return=None, side_effect=None):
		provider = NtfyProvider(make_config())
		with patch("ntfynext.providers.ntfy.requests.post", side_effect=side_effect) as mp:
			if mock_post_return is not None and side_effect is None:
				mp.return_value = mock_post_return
			return provider.publish(NtfyMessage(topic="t", message="m")), mp

	def test_success(self, _logger):
		resp = MagicMock(status_code=200, text='{"id":"x"}')
		result, mp = self._run(mock_post_return=resp)
		self.assertTrue(result.ok)
		self.assertEqual(result.status_code, 200)
		self.assertIsNone(result.error)
		# posts to server root with trailing slash and JSON body
		args, kwargs = mp.call_args
		self.assertEqual(args[0], "https://ntfy.example.com/")
		self.assertEqual(kwargs["json"]["topic"], "t")
		self.assertEqual(kwargs["timeout"], 10)
		self.assertTrue(kwargs["verify"])

	def test_http_error(self, _logger):
		resp = MagicMock(status_code=403, text="forbidden")
		result, _mp = self._run(mock_post_return=resp)
		self.assertFalse(result.ok)
		self.assertEqual(result.status_code, 403)
		self.assertIn("403", result.error)

	def test_network_exception(self, _logger):
		result, _mp = self._run(side_effect=requests.exceptions.ConnectTimeout("boom"))
		self.assertFalse(result.ok)
		self.assertIsNone(result.status_code)
		self.assertIn("boom", result.error)


if __name__ == "__main__":
	unittest.main()
