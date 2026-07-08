"""Post-install setup for Hardware Cockpit.

No new DocType — we only backfill the *existing* ERPNext settings the cockpit reads, so a
fresh site is usable immediately. Everything here is idempotent (only fills blanks).
"""

import frappe


WORKSPACE = "Item Cockpit"


def after_install():
	try:
		_seed_defaults()
		_create_workspace()
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Hardware Cockpit install error", message=frappe.get_traceback())
		# Don't hard-fail the install over optional defaults.


def before_uninstall():
	if frappe.db.exists("Workspace", WORKSPACE):
		frappe.delete_doc("Workspace", WORKSPACE, ignore_permissions=True, force=True)


def _create_workspace():
	"""A public desk Workspace with a shortcut that opens the /item-cockpit SPA."""
	if frappe.db.exists("Workspace", WORKSPACE):
		return
	doc = {
		"doctype": "Workspace",
		"label": WORKSPACE,
		"title": WORKSPACE,
		"public": 1,
		"icon": "retail",
		"content": "[]",
		"shortcuts": [
			{"type": "URL", "label": "Open Item Cockpit", "url": "/item-cockpit", "color": "Green"}
		],
	}
	# `module` is a Link to Module Def — only set it if ours has been synced already.
	if frappe.db.exists("Module Def", "Hardware Cockpit"):
		doc["module"] = "Hardware Cockpit"
	frappe.get_doc(doc).insert(ignore_permissions=True)


def _seed_defaults():
	company = (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)

	# Default warehouse (Stock Settings) — pick a sensible leaf warehouse if unset.
	if not frappe.db.get_single_value("Stock Settings", "default_warehouse"):
		warehouse = frappe.db.get_value(
			"Warehouse",
			{"company": company, "is_group": 0, "disabled": 0} if company else {"is_group": 0, "disabled": 0},
			"name",
		)
		if warehouse:
			frappe.db.set_single_value("Stock Settings", "default_warehouse", warehouse)

	# Selling / Buying price lists.
	if not frappe.db.get_single_value("Selling Settings", "selling_price_list"):
		pl = frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name") or frappe.db.get_value(
			"Price List", "Standard Selling", "name"
		)
		if pl:
			frappe.db.set_single_value("Selling Settings", "selling_price_list", pl)

	if not frappe.db.get_single_value("Buying Settings", "buying_price_list"):
		pl = frappe.db.get_value("Price List", {"buying": 1, "enabled": 1}, "name") or frappe.db.get_value(
			"Price List", "Standard Buying", "name"
		)
		if pl:
			frappe.db.set_single_value("Buying Settings", "buying_price_list", pl)
