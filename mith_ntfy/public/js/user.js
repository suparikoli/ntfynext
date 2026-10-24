// Copyright (c) 2026, MithTech Innovative Solutions and contributors
// For license information, please see license.txt
//
// Renders a one-tap "Subscribe" card (QR + button) on the User's NTFY tab so a
// user can point their phone at it and land in the ntfy app already subscribed
// to their private topic. The QR/URL come from mith_ntfy.api.get_subscribe_info.

frappe.ui.form.on("User", {
	refresh(frm) {
		frm.trigger("_ntfy_render_subscribe");
	},
	enable_ntfy(frm) {
		frm.trigger("_ntfy_render_subscribe");
	},
	ntfy_topic(frm) {
		frm.trigger("_ntfy_render_subscribe");
	},
	ntfy_override_server_url(frm) {
		frm.trigger("_ntfy_render_subscribe");
	},

	_ntfy_render_subscribe(frm) {
		const field = frm.get_field("ntfy_subscribe_html");
		if (!field) return;

		if (frm.is_new() || !frm.doc.enable_ntfy || !frm.doc.ntfy_topic) {
			field.html("");
			return;
		}

		frappe.call({
			method: "mith_ntfy.api.get_subscribe_info",
			args: { user: frm.doc.name },
			callback(r) {
				const d = r.message || {};
				if (!d.url) {
					field.html("");
					return;
				}
				const url = frappe.utils.escape_html(d.url);
				const topic = frappe.utils.escape_html(d.topic || "");
				const server = frappe.utils.escape_html(d.server || "");
				field.html(`
					<div style="display:flex;gap:24px;align-items:center;flex-wrap:wrap;padding:4px 0">
						<div style="width:156px;height:156px;flex:none;border:1px solid var(--border-color);border-radius:10px;padding:6px;background:#fff">
							${d.qr_svg || ""}
						</div>
						<div style="min-width:240px">
							<div style="font-weight:600;margin-bottom:6px">${__("Get push notifications on your phone")}</div>
							<div class="text-muted" style="margin-bottom:12px;max-width:420px">
								${__("Scan the QR with your phone's camera, or tap below — it opens the ntfy app subscribed to your private topic.")}
							</div>
							<a href="${url}" target="_blank" rel="noopener" class="btn btn-primary btn-sm">
								${__("Subscribe in ntfy")}
							</a>
							<a href="https://ntfy.sh/docs/subscribe/phone/" target="_blank" rel="noopener" class="btn btn-default btn-sm" style="margin-left:6px">
								${__("Get the app")}
							</a>
							<div class="text-muted small" style="margin-top:12px">
								${__("Topic")}: <code>${topic}</code><br>${__("Server")}: ${server}
							</div>
						</div>
					</div>
				`);
			},
		});
	},
});
