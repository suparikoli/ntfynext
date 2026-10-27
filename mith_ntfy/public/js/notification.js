// Copyright (c) 2026, MithTech Innovative Solutions and contributors
// For license information, please see license.txt
//
// Adds a small hint to the standard Notification form when NTFY is enabled.
// Field visibility itself is handled by the custom fields' depends_on.

frappe.ui.form.on("Notification", {
	refresh(frm) {
		frm.trigger("send_via_ntfy");
	},

	send_via_ntfy(frm) {
		frm.set_intro("");
		if (frm.doc.send_via_ntfy) {
			frm.set_intro(
				__(
					"Send via NTFY is on — opted-in recipients also receive an ntfy push. " +
						"Set a Direct Topic to additionally notify a shared topic."
				),
				"blue"
			);
		}
	},
});
