from . import __version__ as app_version

app_name = "sales_application_plugin"
app_title = "Sales Application Plugin"
app_publisher = "Akhilam INC"
app_description = "Sales Application backend"
app_email = "raaj@akhilaminc.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/sales_application_plugin/css/sales_application_plugin.css"
# app_include_js = "/assets/sales_application_plugin/js/sales_application_plugin.js"

# include js, css files in header of web template
# web_include_css = "/assets/sales_application_plugin/css/sales_application_plugin.css"
# web_include_js = "/assets/sales_application_plugin/js/sales_application_plugin.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "sales_application_plugin/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "sales_application_plugin.utils.jinja_methods",
#	"filters": "sales_application_plugin.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "sales_application_plugin.install.before_install"
# after_install = "sales_application_plugin.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "sales_application_plugin.uninstall.before_uninstall"
# after_uninstall = "sales_application_plugin.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "sales_application_plugin.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Item Group": {
		"on_trash": "sales_application_plugin.sales_application_plugin.override.doc_event.handle_doc_trash"
	},
    "Item": {
		"on_trash": "sales_application_plugin.sales_application_plugin.override.doc_event.handle_doc_trash"
	},
    "Customer Group": {
		"on_trash": "sales_application_plugin.sales_application_plugin.override.doc_event.handle_doc_trash"
	},
    "Customer": {
		"on_trash": "sales_application_plugin.sales_application_plugin.override.doc_event.handle_doc_trash"
	},
    "Sales Invoice" : {
        "on_trash" : "sales_application_plugin.sales_application_plugin.override.doc_event.handle_doc_trash"
    },"Sales Order" : {
        "on_trash" : "sales_application_plugin.sales_application_plugin.override.doc_event.handle_doc_trash"
    },
    "Payment Entry" : {
        "on_trash" : "sales_application_plugin.sales_application_plugin.override.doc_event.handle_doc_trash"
    },
    "Journal Entry" : {
        "on_trash" : "sales_application_plugin.sales_application_plugin.override.doc_event.handle_doc_trash"
    },
    "User" : {
        "on_update" : "sales_application_plugin.sales_application_plugin.override.doc_event.on_user_update"
    }
}

# Scheduled Tasks
# ---------------
fixtures=[{"dt":"Custom Field","filters":[["name","in",["Address-geolocation_details"]]]}]
# scheduler_events = {
#	"all": [
#		"sales_application_plugin.tasks.all"
#	],
#	"daily": [
#		"sales_application_plugin.tasks.daily"
#	],
#	"hourly": [
#		"sales_application_plugin.tasks.hourly"
#	],
#	"weekly": [
#		"sales_application_plugin.tasks.weekly"
#	],
#	"monthly": [
#		"sales_application_plugin.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "sales_application_plugin.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "sales_application_plugin.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "sales_application_plugin.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["sales_application_plugin.utils.before_request"]
# after_request = ["sales_application_plugin.utils.after_request"]

# Job Events
# ----------
# before_job = ["sales_application_plugin.utils.before_job"]
# after_job = ["sales_application_plugin.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"sales_application_plugin.auth.validate"
# ]
