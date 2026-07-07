// Copyright (c) 2026, MithTech Innovative Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on("NTFY Settings", {
	refresh(frm) {
		frm.trigger("auth_type");
	},

	// Field button "Test Connection".
	test_connection(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Please save your changes before testing."));
			return;
		}
		frappe.prompt(
			[
				{
					fieldname: "topic",
					fieldtype: "Data",
					label: __("Test Topic"),
					default: frm.doc.test_topic || "",
					description: __("Leave blank to auto-generate a one-off topic."),
				},
			],
			(values) => {
				frappe.call({
					method: "test_connection",
					doc: frm.doc,
					args: { topic: values.topic },
					freeze: true,
					freeze_message: __("Publishing test message..."),
					callback: (r) => {
						const res = r.message || {};
						if (res.ok) {
							frappe.msgprint({
								title: __("Success"),
								indicator: "green",
								message: __("Delivered to <b>{0}</b> on <b>{1}</b> (HTTP {2}).", [
									frappe.utils.escape_html(res.topic || ""),
									frappe.utils.escape_html(res.server || ""),
									res.status_code,
								]),
							});
						} else {
							frappe.msgprint({
								title: __("Connection Failed"),
								indicator: "red",
								message: `<code>${frappe.utils.escape_html(res.error || "Unknown error")}</code>`,
							});
						}
					},
				});
			},
			__("Test Connection"),
			__("Send")
		);
	},
});
