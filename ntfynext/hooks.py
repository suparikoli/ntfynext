"""Frappe hooks for NTFYnext.

NTFYnext adds `ntfy <https://ntfy.sh>`_ push delivery as an *additional*
notification channel alongside email (it never replaces email). The wiring is
grouped by feature below.
"""

app_name = "ntfynext"
app_title = "NTFYnext"
app_publisher = "MithTech Innovative Solutions"
app_description = "ntfy push notifications as an additional channel for Frappe (deliver notification emails via ntfy)"
app_email = "manoj@mith.tech"
app_license = "mit"

# ---------------------------------------------------------------------------
# Apps screen
# ---------------------------------------------------------------------------
add_to_apps_screen = [
	{
		"name": "ntfynext",
		"logo": "/assets/ntfynext/images/ntfynext-logo.svg",
		"title": "NTFYnext",
		"route": "/app/ntfy-settings",
		"has_permission": "ntfynext.api.has_app_permission",
	}
]

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
# Global desk script: injects the "Send NTFY Notification" document-menu action.
app_include_js = "/assets/ntfynext/js/ntfynext.js"

# Per-doctype client scripts (served from /assets/ntfynext/js via the app symlink).
doctype_js = {
	"NTFY Settings": "public/js/ntfy_settings.js",
	"Notification": "public/js/notification.js",
}

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------
after_install = "ntfynext.install.after_install"
after_migrate = "ntfynext.install.after_migrate"

# ---------------------------------------------------------------------------
# Fixtures — our custom fields + the NTFY Manager role
# ---------------------------------------------------------------------------
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					"User-ntfy_tab",
					"User-ntfy_prefs_section",
					"User-enable_ntfy",
					"User-ntfy_topic",
					"User-ntfy_override_server_url",
					"User-ntfy_col_break",
					"User-ntfy_priority",
					"User-ntfy_tags",
					"User-ntfy_silent_mode",
					"Notification-send_via_ntfy",
					"Notification-ntfy_section",
					"Notification-ntfy_topic",
					"Notification-ntfy_priority",
					"Notification-ntfy_tags",
				],
			]
		],
	},
	{"dt": "Role", "filters": [["role_name", "in", ["NTFY Manager"]]]},
]

# ---------------------------------------------------------------------------
# Document events
# ---------------------------------------------------------------------------
doc_events = {
	"User": {"validate": "ntfynext.user.ensure_topic"},
	# Global mirror: no-op unless NTFY Settings > Mirror All Notification Emails is on.
	"Email Queue": {"after_insert": "ntfynext.dispatch.on_email_queued"},
}

# ---------------------------------------------------------------------------
# Controller overrides — add ntfy delivery to the standard Notification
# without monkeypatching (subclass + super()).
# ---------------------------------------------------------------------------
override_doctype_class = {
	"Notification": ["ntfynext.overrides.notification.NTFYNotification"],
}

# ---------------------------------------------------------------------------
# Scheduled tasks — retry sweeper for failed pushes (runs each minute so the
# 1-minute first-retry backoff is honoured closely).
# ---------------------------------------------------------------------------
scheduler_events = {
	"cron": {"* * * * *": ["ntfynext.tasks.retry_failed_notifications"]},
}

# ---------------------------------------------------------------------------
# Log retention — auto-clear old delivery logs
# ---------------------------------------------------------------------------
default_log_clearing_doctypes = {
	"NTFY Notification Log": 90,  # days to retain
}
