// Copyright (c) 2026, MithTech Innovative Solutions and contributors
// For license information, please see license.txt
//
// Global desk script: adds a "Send NTFY Notification" item to the document menu
// on every form, for users who may send (System Manager / NTFY Manager).

frappe.provide("mith_ntfy");

$(document).on("app_ready", function () {
	const can_send =
		frappe.user_roles.includes("System Manager") || frappe.user_roles.includes("NTFY Manager");
	if (!can_send) return;

	const hooked = new Set();
	frappe.router.on("change", () => {
		const route = frappe.get_route();
		if (!route || route[0] !== "Form" || !route[1] || hooked.has(route[1])) return;
		hooked.add(route[1]);
		frappe.ui.form.on(route[1], {
			refresh(frm) {
				if (frm.is_new() || frm.__ntfy_menu) return;
				frm.__ntfy_menu = true;
				frm.page.add_menu_item(__("Send NTFY Notification"), () => mith_ntfy.send_dialog(frm));
			},
		});
	});
});

mith_ntfy.send_dialog = function (frm) {
	let assignees = [];
	try {
		assignees = JSON.parse(frm.doc._assign || "[]");
	} catch (e) {
		assignees = [];
	}
	const default_users = Array.from(new Set([frm.doc.owner, ...assignees]))
		.filter(Boolean)
		.join(", ");

	const d = new frappe.ui.Dialog({
		title: __("Send NTFY Notification"),
		fields: [
			{
				fieldname: "title",
				fieldtype: "Data",
				label: __("Title"),
				reqd: 1,
				default: `${__(frm.doctype)} ${frm.docname}`,
			},
			{ fieldname: "message", fieldtype: "Small Text", label: __("Message"), reqd: 1 },
			{ fieldtype: "Section Break", label: __("Recipients") },
			{
				fieldname: "users",
				fieldtype: "Small Text",
				label: __("Users"),
				default: default_users,
				description: __("Comma-separated User IDs. Only opted-in users receive a push."),
			},
			{
				fieldname: "topic",
				fieldtype: "Data",
				label: __("Topic"),
				description: __("Optional: also publish to a fixed topic."),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "priority",
				fieldtype: "Select",
				label: __("Priority"),
				options: ["", "min", "low", "default", "high", "max"].join("\n"),
			},
			{ fieldname: "tags", fieldtype: "Data", label: __("Tags") },
		],
		primary_action_label: __("Send"),
		primary_action(v) {
			if (!v.users && !v.topic) {
				frappe.msgprint(__("Provide at least one User or a Topic."));
				return;
			}
			const users = (v.users || "")
				.split(",")
				.map((s) => s.trim())
				.filter(Boolean);
			frappe.call({
				method: "mith_ntfy.api.send_manual",
				args: {
					doctype: frm.doctype,
					docname: frm.docname,
					title: v.title,
					message: v.message,
					users: JSON.stringify(users),
					topic: v.topic,
					priority: v.priority,
					tags: v.tags,
				},
				freeze: true,
				freeze_message: __("Queueing notification..."),
				callback: (r) => {
					const res = r.message || {};
					frappe.show_alert({
						message: __("Queued {0} notification(s)", [res.queued || 0]),
						indicator: res.queued ? "green" : "orange",
					});
					d.hide();
				},
			});
		},
	});
	d.show();
};
