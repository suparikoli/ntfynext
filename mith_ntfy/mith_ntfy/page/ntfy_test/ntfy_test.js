// Copyright (c) 2026, MithTech Innovative Solutions and contributors
// For license information, please see license.txt

frappe.pages["ntfy-test"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("NTFY Test"),
		single_column: true,
	});

	const body = $('<div class="ntfy-test-page" style="padding: 0 15px;"></div>').appendTo(page.body);
	const form_area = $("<div></div>").appendTo(body);
	const result_area = $('<div style="margin-top: 20px;"></div>').appendTo(body);

	const fg = new frappe.ui.FieldGroup({
		parent: form_area,
		fields: [
			{
				fieldname: "user",
				fieldtype: "Link",
				label: __("User"),
				options: "User",
				description: __("Send to this user's topic (must be opted in)."),
			},
			{
				fieldname: "topic",
				fieldtype: "Data",
				label: __("Topic"),
				description: __("Or publish directly to a topic (overrides User)."),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "priority",
				fieldtype: "Select",
				label: __("Priority"),
				options: ["", "min", "low", "default", "high", "max"].join("\n"),
			},
			{ fieldname: "tags", fieldtype: "Data", label: __("Tags"), description: __("Comma-separated") },
			{ fieldtype: "Section Break" },
			{ fieldname: "title", fieldtype: "Data", label: __("Title"), default: "NTFY Test" },
			{
				fieldname: "message",
				fieldtype: "Small Text",
				label: __("Message"),
				default: "Test notification from Mith ntfy.",
			},
			{ fieldname: "click_url", fieldtype: "Data", label: __("Click URL") },
		],
	});
	fg.make();

	page.set_primary_action(
		__("Send Test"),
		() => {
			const v = fg.get_values();
			if (!v) return;
			if (!v.user && !v.topic) {
				frappe.msgprint(__("Provide a User or a Topic."));
				return;
			}
			result_area.empty();
			page.btn_primary.prop("disabled", true);
			frappe.call({
				method: "mith_ntfy.api.send_test",
				args: {
					user: v.user,
					topic: v.topic,
					title: v.title,
					message: v.message,
					priority: v.priority,
					tags: v.tags,
					url: v.click_url,
				},
				callback: (r) => render_result(result_area, r.message),
				always: () => page.btn_primary.prop("disabled", false),
			});
		},
		"octicon octicon-rocket"
	);

	function render_result(area, res) {
		if (!res) return;
		const ok = res.ok;
		const color = ok ? "green" : "red";
		const heading = ok ? __("Delivered") : __("Failed");
		const rows = [
			[__("Status"), `<span class="indicator ${color}">${heading}</span>`],
			[__("HTTP Code"), frappe.utils.escape_html(String(res.status_code || "-"))],
			[__("Topic"), frappe.utils.escape_html(res.topic || "-")],
			[__("Server"), frappe.utils.escape_html(res.server || "-")],
		];
		if (res.error) rows.push([__("Error"), `<code>${frappe.utils.escape_html(res.error)}</code>`]);
		if (res.log) {
			const href = `/app/ntfy-notification-log/${encodeURIComponent(res.log)}`;
			rows.push([__("Log"), `<a href="${href}">${frappe.utils.escape_html(res.log)}</a>`]);
		}
		if (res.response) {
			rows.push([
				__("Response"),
				`<pre style="white-space:pre-wrap;margin:0">${frappe.utils.escape_html(res.response)}</pre>`,
			]);
		}
		const html = rows
			.map(
				([k, val]) =>
					`<tr><td class="text-muted" style="width:130px;padding:4px 8px;vertical-align:top">${k}</td>` +
					`<td style="padding:4px 8px">${val}</td></tr>`
			)
			.join("");
		$(
			`<div class="frappe-card" style="padding:12px"><table class="table table-borderless" style="margin:0">${html}</table></div>`
		).appendTo(area);
	}
};
