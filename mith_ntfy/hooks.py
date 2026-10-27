"""Frappe hooks for Mith ntfy.

Mith ntfy adds `ntfy <https://ntfy.sh>`_ push delivery as an *additional*
notification channel alongside email (it never replaces email). The wiring is
grouped by feature below.
"""

app_name = "mith_ntfy"
app_title = "Mith ntfy"
app_publisher = "MithTech Innovative Solutions"
app_description = "ntfy push notifications as an additional channel for Frappe (deliver notification emails via ntfy)"
app_email = "manoj@mith.tech"
app_license = "mit"

# ---------------------------------------------------------------------------
# Apps screen
# ---------------------------------------------------------------------------
add_to_apps_screen = [
	{
		"name": "mith_ntfy",
		"logo": "/assets/mith_ntfy/images/ntfynext-logo.svg",
		"title": "Mith ntfy",
		"route": "/app/ntfy-settings",
		"has_permission": "mith_ntfy.api.has_app_permission",
	}
]

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
# Global desk script: injects the "Send NTFY Notification" document-menu action.
app_include_js = "/assets/mith_ntfy/js/mith_ntfy.js"

# Per-doctype client scripts (served from /assets/mith_ntfy/js via the app symlink).
doctype_js = {
	"NTFY Settings": "public/js/ntfy_settings.js",
	"Notification": "public/js/notification.js",
	"User": "public/js/user.js",
}

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------
after_install = "mith_ntfy.install.after_install"
after_migrate = "mith_ntfy.install.after_migrate"

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
					"User-ntfy_subscribe_section",
					"User-ntfy_subscribe_html",
					"User-ntfy_provisioned",
					"User-ntfy_client_password",
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
	"User": {
		"validate": "mith_ntfy.user.ensure_topic",
		# No-op unless NTFY Settings > backntfy Auto-Provisioning is on.
		"on_update": "mith_ntfy.user.sync_backntfy",
	},
	# Global mirror: no-op unless NTFY Settings > Mirror All Notification Emails is on.
	"Email Queue": {"after_insert": "mith_ntfy.dispatch.on_email_queued"},
}

# ---------------------------------------------------------------------------
# Controller overrides — add ntfy delivery to the standard Notification
# without monkeypatching (subclass + super()).
# ---------------------------------------------------------------------------
override_doctype_class = {
	"Notification": ["mith_ntfy.overrides.notification.NTFYNotification"],
}

# ---------------------------------------------------------------------------
# Scheduled tasks — retry sweeper for failed pushes (runs each minute so the
# 1-minute first-retry backoff is honoured closely).
# ---------------------------------------------------------------------------
scheduler_events = {
	"cron": {"* * * * *": ["mith_ntfy.tasks.retry_failed_notifications"]},
}

# ---------------------------------------------------------------------------
# Log retention — auto-clear old delivery logs
# ---------------------------------------------------------------------------
default_log_clearing_doctypes = {
	"NTFY Notification Log": 90,  # days to retain
}
