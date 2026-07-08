"""Item Cockpit — whitelisted API for the Manage screen.

Every write goes through `frappe.get_doc(...).insert()/.save()/.submit()` so all ERPNext
validation, permissions, ledgers and accounting fire. No raw SQL writes, no Bin writes.

Defaults (price lists, warehouse, company, currency) are read from existing ERPNext
settings — this app deliberately does not add its own Settings DocType.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

# Reasonable ceiling on how many items we scan/enrich for one grid load. Hardware-store
# catalogues are modest; if a site ever exceeds this, the grid is capped (and logged) rather
# than doing something unbounded. Filtering/search narrows this well before the cap.
MAX_SCAN = 5000


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _reject_guest():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to use the Item Cockpit."), frappe.AuthenticationError)


def _require(doctype, ptype="read"):
	if not frappe.has_permission(doctype, ptype):
		frappe.throw(
			_("You do not have permission to {0} {1}.").format(ptype, _(doctype)),
			frappe.PermissionError,
		)


def _settings():
	"""Resolve the store defaults from existing ERPNext settings, with safe fallbacks."""
	company = (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.defaults.get_defaults().get("company")
		or frappe.db.get_value("Company", {}, "name")
	)
	currency = (
		(company and frappe.db.get_value("Company", company, "default_currency"))
		or frappe.db.get_single_value("Global Defaults", "default_currency")
		or "USD"
	)
	selling_pl = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
	buying_pl = frappe.db.get_single_value("Buying Settings", "buying_price_list") or "Standard Buying"
	warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if not warehouse and company:
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 0, "disabled": 0}, "name"
		)
	return frappe._dict(
		company=company,
		currency=currency,
		selling_price_list=selling_pl,
		buying_price_list=buying_pl,
		default_warehouse=warehouse,
	)


def _price_list(price_type, settings):
	if price_type not in ("selling", "buying"):
		frappe.throw(_("Unknown price type: {0}").format(price_type))
	return settings.selling_price_list if price_type == "selling" else settings.buying_price_list


def _upsert_price(item_code, price_type, rate, settings=None):
	"""Create or update the single Item Price for (item, price list). Returns the saved rate."""
	settings = settings or _settings()
	price_list = _price_list(price_type, settings)
	uom = frappe.db.get_value("Item", item_code, "stock_uom")
	currency = frappe.db.get_value("Price List", price_list, "currency") or settings.currency

	existing = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list, "uom": uom},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Item Price", existing)
		doc.price_list_rate = flt(rate)
		doc.save()
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": item_code,
				"price_list": price_list,
				"uom": uom,
				"currency": currency,
				"price_list_rate": flt(rate),
			}
		).insert()
	return flt(doc.price_list_rate)


def _stock_qty(item_code, warehouse):
	if not warehouse:
		return 0.0
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


def _make_stock_reconciliation(item_code, warehouse, qty, valuation_rate, company):
	"""Build + submit a Stock Reconciliation that sets `item_code` in `warehouse` to `qty`."""
	sr = frappe.new_doc("Stock Reconciliation")
	sr.purpose = "Stock Reconciliation"
	sr.set_posting_time = 1
	sr.company = company
	sr.expense_account = (
		frappe.get_cached_value("Company", company, "stock_adjustment_account")
		or frappe.get_cached_value("Account", {"account_type": "Stock Adjustment", "company": company}, "name")
		or frappe.get_cached_value("Account", {"account_type": "Temporary", "company": company}, "name")
	)
	sr.cost_center = frappe.get_cached_value("Company", company, "cost_center") or frappe.get_cached_value(
		"Cost Center", {"is_group": 0, "company": company}, "name"
	)
	sr.append(
		"items",
		{
			"item_code": item_code,
			"warehouse": warehouse,
			"qty": flt(qty),
			"valuation_rate": flt(valuation_rate),
		},
	)
	sr.insert()
	sr.submit()
	return sr


def _valuation_rate(item_code, warehouse, fallback_cost=None, settings=None):
	"""Current valuation rate, else the item's cost/buying price, else 0."""
	from erpnext.stock.utils import get_stock_balance

	rate = 0.0
	if warehouse:
		try:
			_qty, rate = get_stock_balance(item_code, warehouse, with_valuation_rate=True)
		except Exception:
			rate = 0.0
	if flt(rate) <= 0:
		if fallback_cost is not None:
			rate = flt(fallback_cost)
		else:
			settings = settings or _settings()
			rate = flt(
				frappe.db.get_value(
					"Item Price",
					{"item_code": item_code, "price_list": settings.buying_price_list},
					"price_list_rate",
				)
			)
	return flt(rate)


def _set_reorder_row(item_doc, warehouse, reorder_level, reorder_qty=None):
	reorder_level = flt(reorder_level)
	row = next((r for r in item_doc.reorder_levels if r.warehouse == warehouse), None)
	if row:
		row.warehouse_reorder_level = reorder_level
		if reorder_qty is not None:
			row.warehouse_reorder_qty = flt(reorder_qty)
	else:
		item_doc.append(
			"reorder_levels",
			{
				"warehouse": warehouse,
				"warehouse_reorder_level": reorder_level,
				"warehouse_reorder_qty": flt(reorder_qty) if reorder_qty is not None else reorder_level,
				"material_request_type": "Purchase",
			},
		)


def _generate_item_code(item_group):
	"""Group-prefixed code like FAS-001, respecting existing sequences. Best-effort + unique."""
	prefix = "".join(ch for ch in (item_group or "ITM") if ch.isalnum())[:3].upper() or "ITM"
	existing = frappe.get_all(
		"Item", filters={"item_code": ["like", f"{prefix}-%"]}, pluck="item_code"
	)
	seq = 0
	for code in existing:
		tail = code.rsplit("-", 1)[-1]
		if tail.isdigit():
			seq = max(seq, int(tail))
	seq += 1
	code = f"{prefix}-{seq:03d}"
	while frappe.db.exists("Item", code):
		seq += 1
		code = f"{prefix}-{seq:03d}"
	return code


def _status(qty, reorder):
	if flt(qty) <= 0:
		return "out"
	if flt(reorder) > 0 and flt(qty) < flt(reorder):
		return "low"
	return "ok"


# ---------------------------------------------------------------------------
# whitelisted API
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_form_meta():
	"""Lists the client needs to render filters and the wizard. One call on page load."""
	_reject_guest()
	_require("Item", "read")
	settings = _settings()
	currency_symbol = frappe.db.get_value("Currency", settings.currency, "symbol") or settings.currency
	uoms = frappe.get_all("UOM", filters={"enabled": 1}, pluck="name", order_by="name asc")
	default_uom = "Unit" if "Unit" in uoms else (uoms[0] if uoms else None)
	return {
		"item_groups": frappe.get_all(
			"Item Group", filters={"is_group": 0}, pluck="name", order_by="name asc"
		),
		"uoms": uoms,
		"default_uom": default_uom,
		"warehouses": frappe.get_all(
			"Warehouse", filters={"is_group": 0, "disabled": 0}, fields=["name", "company"], order_by="name asc"
		),
		"default_warehouse": settings.default_warehouse,
		"company": settings.company,
		"currency": settings.currency,
		"currency_symbol": currency_symbol,
	}


@frappe.whitelist()
def get_items(search=None, item_group=None, stock_status=None, warehouse=None, limit=100, start=0):
	"""Grid payload: enriched item rows + live stock-status counts.

	Rows join Item + latest selling/buying Item Price + Bin qty + reorder level, with
	`stock_status` (ok/low/out) derived server-side so the client's chip counts are correct.
	"""
	_reject_guest()
	_require("Item", "read")
	settings = _settings()
	warehouse = warehouse or settings.default_warehouse
	limit, start = cint(limit) or 100, cint(start)

	filters = {"disabled": 0, "has_variants": 0}
	if item_group and item_group not in ("all", "All"):
		filters["item_group"] = item_group
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = [{"item_code": ["like", like]}, {"item_name": ["like", like]}]
		# Also match items by barcode (Item Barcode child table) so a scan finds the item.
		barcode_matches = frappe.get_all("Item Barcode", filters={"barcode": ["like", like]}, pluck="parent")
		if barcode_matches:
			or_filters.append({"name": ["in", barcode_matches]})

	matched = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["name as item_code", "item_name", "item_group", "stock_uom", "image"],
		order_by="item_name asc",
		limit_page_length=MAX_SCAN,
	)
	if len(matched) >= MAX_SCAN:
		frappe.log_error(
			title="Item Cockpit: grid scan hit MAX_SCAN cap",
			message=f"get_items returned the {MAX_SCAN}-row cap for filters={filters}, search={search!r}.",
		)

	codes = [d.item_code for d in matched]
	sell_map, buy_map, qty_map, reorder_map = {}, {}, {}, {}
	if codes:
		for p in frappe.get_all(
			"Item Price",
			filters={"item_code": ["in", codes], "price_list": settings.selling_price_list},
			fields=["item_code", "price_list_rate"],
			order_by="modified desc",
		):
			sell_map.setdefault(p.item_code, p.price_list_rate)
		for p in frappe.get_all(
			"Item Price",
			filters={"item_code": ["in", codes], "price_list": settings.buying_price_list},
			fields=["item_code", "price_list_rate"],
			order_by="modified desc",
		):
			buy_map.setdefault(p.item_code, p.price_list_rate)
		if warehouse:
			for b in frappe.get_all(
				"Bin",
				filters={"item_code": ["in", codes], "warehouse": warehouse},
				fields=["item_code", "actual_qty"],
			):
				qty_map[b.item_code] = flt(qty_map.get(b.item_code)) + flt(b.actual_qty)
			for r in frappe.get_all(
				"Item Reorder",
				filters={"parent": ["in", codes], "warehouse": warehouse},
				fields=["parent", "warehouse_reorder_level"],
			):
				reorder_map[r.parent] = flt(r.warehouse_reorder_level)

	rows, low_count, out_count = [], 0, 0
	for d in matched:
		qty = flt(qty_map.get(d.item_code))
		reorder = flt(reorder_map.get(d.item_code))
		status = _status(qty, reorder)
		if status == "low":
			low_count += 1
		elif status == "out":
			out_count += 1
		rows.append(
			{
				"item_code": d.item_code,
				"item_name": d.item_name,
				"item_group": d.item_group,
				"stock_uom": d.stock_uom,
				"image": d.image,
				"qty": qty,
				"reorder_level": reorder,
				"stock_status": status,
				"selling_rate": flt(sell_map.get(d.item_code)),
				"cost_rate": flt(buy_map.get(d.item_code)),
			}
		)

	if stock_status in ("low", "out", "ok"):
		rows = [r for r in rows if r["stock_status"] == stock_status]

	total_count = len(rows)
	page = rows[start : start + limit]
	return {
		"items": page,
		"total_count": total_count,
		"all_count": len(matched),
		"low_count": low_count,
		"out_count": out_count,
		"warehouse": warehouse,
		"currency_symbol": frappe.db.get_value("Currency", settings.currency, "symbol") or settings.currency,
	}


@frappe.whitelist()
def update_price(item_code, price_type, rate):
	"""Upsert the selling or buying Item Price for an item."""
	_reject_guest()
	_require("Item Price", "write")
	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} not found.").format(item_code))
	saved = _upsert_price(item_code, price_type, rate)
	return {"item_code": item_code, "price_type": price_type, "rate": saved}


@frappe.whitelist()
def set_stock(item_code, warehouse=None, qty=0, valuation_rate=None):
	"""Set absolute stock on hand for an item via a Stock Reconciliation. Returns new qty."""
	_reject_guest()
	_require("Stock Reconciliation", "create")
	settings = _settings()
	warehouse = warehouse or settings.default_warehouse
	if not warehouse:
		frappe.throw(_("No warehouse is configured. Set a default warehouse in Stock Settings."))
	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} not found.").format(item_code))

	company = frappe.db.get_value("Warehouse", warehouse, "company") or settings.company
	rate = _valuation_rate(item_code, warehouse, fallback_cost=valuation_rate, settings=settings)
	try:
		_make_stock_reconciliation(item_code, warehouse, flt(qty), rate, company)
	except frappe.ValidationError as e:
		frappe.throw(_("Could not set stock: {0}").format(str(e)))
	return {"item_code": item_code, "warehouse": warehouse, "qty": _stock_qty(item_code, warehouse)}


@frappe.whitelist()
def set_reorder(item_code, warehouse=None, reorder_level=0, reorder_qty=None):
	"""Upsert the item's reorder rule for the warehouse."""
	_reject_guest()
	_require("Item", "write")
	settings = _settings()
	warehouse = warehouse or settings.default_warehouse
	if not warehouse:
		frappe.throw(_("No warehouse is configured. Set a default warehouse in Stock Settings."))
	doc = frappe.get_doc("Item", item_code)
	_set_reorder_row(doc, warehouse, reorder_level, reorder_qty)
	doc.save()
	return {"item_code": item_code, "warehouse": warehouse, "reorder_level": flt(reorder_level)}


@frappe.whitelist()
def update_uom(item_code, stock_uom):
	"""Change the item's stock unit. Surfaces a clean error when ERPNext blocks the change."""
	_reject_guest()
	_require("Item", "write")
	doc = frappe.get_doc("Item", item_code)
	doc.stock_uom = stock_uom
	try:
		doc.save()
	except frappe.ValidationError:
		frappe.throw(
			_(
				"This item already has stock activity, so its unit can't be changed. "
				"Create a new item if you need a different unit."
			)
		)
	return {"item_code": item_code, "stock_uom": stock_uom}


@frappe.whitelist()
def create_item(payload):
	"""Create an item + prices + opening stock + reorder rule in one call.

	payload keys: name, item_group, item_code?, barcode?, stock_uom, cost, price,
	opening_qty, reorder_level, warehouse?. Rolls back cleanly on any failure.
	"""
	_reject_guest()
	_require("Item", "create")
	if isinstance(payload, str):
		payload = json.loads(payload)
	payload = frappe._dict(payload)

	settings = _settings()
	warehouse = payload.warehouse or settings.default_warehouse
	if not payload.name:
		frappe.throw(_("Please enter an item name."))
	if not payload.item_group:
		frappe.throw(_("Please choose a group."))
	if not payload.stock_uom:
		frappe.throw(_("Please choose a unit."))

	provided_code = (payload.get("item_code") or "").strip()
	if provided_code:
		if frappe.db.exists("Item", provided_code):
			frappe.throw(_("An item with code {0} already exists.").format(provided_code))
		# On sites that auto-number items, ERPNext would override the code and hand back a
		# different one — reject clearly instead of silently ignoring the caller's code.
		if frappe.db.get_default("item_naming_by") == "Naming Series":
			frappe.throw(_("This site numbers items automatically, so a custom code can't be set here. Leave the code blank."))

	savepoint = "hc_create_item"
	frappe.db.savepoint(savepoint)
	try:
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_name": payload.name,
				"item_group": payload.item_group,
				"stock_uom": payload.stock_uom,
				"is_stock_item": 1,
			}
		)
		# Honour a user-supplied code; otherwise auto-name (group prefix unless the site
		# names items by Naming Series, which would override an explicit code anyway).
		if provided_code:
			item.item_code = provided_code
		elif frappe.db.get_default("item_naming_by") != "Naming Series":
			item.item_code = _generate_item_code(payload.item_group)
		if payload.barcode:
			item.append("barcodes", {"barcode": str(payload.barcode).strip()})
		item.insert()

		if payload.get("price") is not None and payload.price != "":
			_upsert_price(item.name, "selling", payload.price, settings)
		if payload.get("cost") is not None and payload.cost != "":
			_upsert_price(item.name, "buying", payload.cost, settings)

		if flt(payload.opening_qty) > 0 and warehouse:
			company = frappe.db.get_value("Warehouse", warehouse, "company") or settings.company
			rate = _valuation_rate(item.name, warehouse, fallback_cost=payload.cost, settings=settings)
			_make_stock_reconciliation(item.name, warehouse, flt(payload.opening_qty), rate, company)

		if flt(payload.reorder_level) > 0 and warehouse:
			item.reload()
			_set_reorder_row(item, warehouse, payload.reorder_level, payload.get("reorder_qty"))
			item.save()
	except frappe.ValidationError as e:
		frappe.db.rollback(save_point=savepoint)
		frappe.throw(_("Could not create the item: {0}").format(str(e)))
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise

	return {"item_code": item.name, "item_name": item.item_name}


@frappe.whitelist()
def create_group(group_name, parent=None):
	"""Create an Item Group (leaf) from the cockpit. Returns the group name."""
	_reject_guest()
	_require("Item Group", "create")
	group_name = (group_name or "").strip()
	if not group_name:
		frappe.throw(_("Please enter a group name."))
	if frappe.db.exists("Item Group", group_name):
		return {"item_group": group_name, "existed": True}
	parent = parent or "All Item Groups"
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": group_name,
				"parent_item_group": parent,
				"is_group": 0,
			}
		).insert()
	except frappe.ValidationError as e:
		frappe.throw(_("Could not create the group: {0}").format(str(e)))
	return {"item_group": doc.name, "existed": False}


def has_app_permission():
	"""Gate for the Apps-screen tile (hooks add_to_apps_screen): anyone who can read Items."""
	return bool(frappe.session.user != "Guest" and frappe.has_permission("Item", "read"))


@frappe.whitelist(allow_guest=False)
def get_csrf_token():
	"""Fresh CSRF token for the SPA (used by the client's write-retry path)."""
	_reject_guest()
	return {"csrf_token": frappe.sessions.get_csrf_token()}
