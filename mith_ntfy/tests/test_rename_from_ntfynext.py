# Copyright (c) 2026, MithTech Innovative Solutions and contributors
# For license information, please see license.txt

"""The ntfynext -> mith_ntfy rename patch: old-name state in, new-name state out, safe to run twice.

The old state is built inside the test transaction (the patch's commit is muted) and rolled back at the end.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from mith_ntfy.patches import rename_from_ntfynext as rename

OLD_MODULE = "NTFYnext"
NEW_MODULE = "Mith Ntfy"


class TestRenameFromNtfynext(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(self._restore)
		self._make_old_state()

	def _restore(self):
		frappe.db.rollback()
		frappe.clear_cache()

	def _make_old_state(self):
		installed = json.loads(frappe.db.get_global("installed_apps"))
		frappe.db.set_global(
			"installed_apps", json.dumps(["ntfynext" if a == "mith_ntfy" else a for a in installed])
		)
		frappe.db.sql("update `tabInstalled Application` set app_name='ntfynext' where app_name='mith_ntfy'")
		frappe.db.sql(
			"update `tabModule Def` set name=%s, module_name=%s, app_name='ntfynext' where name=%s",
			(OLD_MODULE, OLD_MODULE, NEW_MODULE),
		)
		frappe.db.sql("update `tabDocType` set module=%s where module=%s", (OLD_MODULE, NEW_MODULE))
		frappe.db.sql("update `tabCustom Field` set module=%s where module=%s", (OLD_MODULE, NEW_MODULE))
		frappe.db.sql(
			"update `tabPatch Log` set patch=concat('ntfynext.', substring(patch, 11)) where patch like 'mith_ntfy.%'"
		)
		frappe.db.delete("Patch Log", {"patch": "ntfynext.patches.rename_from_ntfynext"})
		frappe.db.sql(
			"update `tabScheduled Job Type` set method=concat('ntfynext.', substring(method, 11)) "
			"where method like 'mith_ntfy.%'"
		)

	def _run(self):
		with patch.object(frappe.db, "commit"):
			rename.execute()

	def test_rename_moves_everything(self):
		self.assertTrue(frappe.db.exists("Module Def", OLD_MODULE))
		self._run()

		installed = json.loads(frappe.db.get_global("installed_apps"))
		self.assertIn("mith_ntfy", installed)
		self.assertNotIn("ntfynext", installed)
		self.assertEqual(installed.count("mith_ntfy"), 1)
		self.assertFalse(frappe.db.exists("Installed Application", {"app_name": "ntfynext"}))
		self.assertTrue(frappe.db.exists("Installed Application", {"app_name": "mith_ntfy"}))

		self.assertFalse(frappe.db.exists("Module Def", OLD_MODULE))
		self.assertEqual(frappe.db.get_value("Module Def", NEW_MODULE, "app_name"), "mith_ntfy")
		self.assertEqual(frappe.db.get_value("DocType", "NTFY Settings", "module"), NEW_MODULE)
		self.assertFalse(frappe.db.exists("DocType", {"module": OLD_MODULE}))
		self.assertFalse(frappe.db.exists("Custom Field", {"module": OLD_MODULE}))

		self.assertFalse(frappe.db.exists("Patch Log", {"patch": ("like", "ntfynext.%")}))
		self.assertFalse(frappe.db.exists("Scheduled Job Type", {"method": ("like", "ntfynext.%")}))

	def test_rename_is_idempotent(self):
		self._run()
		before = (
			frappe.db.get_global("installed_apps"),
			frappe.db.count("Module Def"),
			frappe.db.count("Patch Log"),
			frappe.db.count("Installed Application"),
		)
		self._run()
		after = (
			frappe.db.get_global("installed_apps"),
			frappe.db.count("Module Def"),
			frappe.db.count("Patch Log"),
			frappe.db.count("Installed Application"),
		)
		self.assertEqual(before, after)
