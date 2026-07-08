"""Website context for the Item Cockpit SPA at /item-cockpit.

Requires login, and exposes Frappe boot data (incl. a CSRF token) to the page as
`window.*` globals via the `{% for key in boot %}` loop the Vite build injects.
"""

import frappe
from frappe.website.utils import get_boot_data

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + (
			getattr(frappe.local, "request", None) and frappe.local.request.path or "/item-cockpit"
		)
		raise frappe.Redirect

	context.boot = get_boot_data()
	context.boot["csrf_token"] = frappe.sessions.get_csrf_token()
	context.boot["hardware_cockpit"] = 1
	return context
