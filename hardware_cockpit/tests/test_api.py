"""End-to-end tests for the Item Cockpit API.

These exercise the three flows the spec calls out:
  * create_item creates Item + selling/buying Item Price + opening Stock Reconciliation + reorder row
  * update_price upserts (creates then updates, never duplicates) an Item Price
  * set_stock produces a submitted Stock Reconciliation with the correct absolute qty

They run against the site's data, reusing its default company/warehouse/price lists, and
skip cleanly if the site has none configured. FrappeTestCase rolls back after each test.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from hardware_cockpit import api


def _first(doctype, filters):
	return frappe.db.get_value(doctype, filters, "name")


class TestItemCockpitAPI(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.settings = api._settings()
		cls.item_group = _first("Item Group", {"is_group": 0})
		if not cls.item_group:
			cls.item_group = frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": "HC Test Group",
					"parent_item_group": "All Item Groups",
					"is_group": 0,
				}
			).insert().name
		cls.uom = _first("UOM", {"name": "Nos"}) or _first("UOM", {"enabled": 1})

	def setUp(self):
		if not (self.settings.company and self.settings.default_warehouse):
			self.skipTest("Site has no default company/warehouse configured.")
		if not (
			frappe.db.exists("Price List", self.settings.selling_price_list)
			and frappe.db.exists("Price List", self.settings.buying_price_list)
		):
			self.skipTest("Site is missing the configured selling/buying price lists.")

	def _new_item(self, **overrides):
		payload = {
			"name": "HC Test " + frappe.generate_hash(length=8),
			"item_group": self.item_group,
			"stock_uom": self.uom,
			"cost": 0,
			"price": 0,
			"opening_qty": 0,
			"reorder_level": 0,
			"warehouse": self.settings.default_warehouse,
		}
		payload.update(overrides)
		return api.create_item(payload)

	# ------------------------------------------------------------------
	def test_create_item_end_to_end(self):
		res = self._new_item(cost=40, price=65, opening_qty=12.5, reorder_level=10)
		code = res["item_code"]

		self.assertTrue(frappe.db.exists("Item", code))

		selling = frappe.db.get_value(
			"Item Price",
			{"item_code": code, "price_list": self.settings.selling_price_list},
			"price_list_rate",
		)
		buying = frappe.db.get_value(
			"Item Price",
			{"item_code": code, "price_list": self.settings.buying_price_list},
			"price_list_rate",
		)
		self.assertEqual(selling, 65)
		self.assertEqual(buying, 40)

		# opening stock → a submitted Stock Reconciliation row for this item
		sr_item = frappe.db.get_value(
			"Stock Reconciliation Item",
			{"item_code": code, "warehouse": self.settings.default_warehouse},
			["parent", "qty"],
			as_dict=True,
		)
		self.assertIsNotNone(sr_item)
		self.assertEqual(sr_item.qty, 12.5)
		self.assertEqual(frappe.db.get_value("Stock Reconciliation", sr_item.parent, "docstatus"), 1)

		# reorder row
		reorder = frappe.db.get_value(
			"Item Reorder",
			{"parent": code, "warehouse": self.settings.default_warehouse},
			"warehouse_reorder_level",
		)
		self.assertEqual(reorder, 10)

	def test_update_price_upserts(self):
		code = self._new_item()["item_code"]

		api.update_price(code, "selling", 100)
		rows = frappe.get_all(
			"Item Price",
			filters={"item_code": code, "price_list": self.settings.selling_price_list},
			fields=["name", "price_list_rate"],
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].price_list_rate, 100)

		api.update_price(code, "selling", 125)
		rows = frappe.get_all(
			"Item Price",
			filters={"item_code": code, "price_list": self.settings.selling_price_list},
			fields=["name", "price_list_rate"],
		)
		self.assertEqual(len(rows), 1, "update_price must update, not duplicate")
		self.assertEqual(rows[0].price_list_rate, 125)

	def test_create_item_honours_explicit_code(self):
		code = "HCCODE" + frappe.generate_hash(length=8)
		res = self._new_item(item_code=code)
		self.assertEqual(res["item_code"], code)
		self.assertTrue(frappe.db.exists("Item", code))

	def test_create_group_creates_leaf_group(self):
		name = "HC Group " + frappe.generate_hash(length=8)
		res = api.create_group(name)
		self.assertEqual(res["item_group"], name)
		self.assertFalse(res["existed"])
		self.assertEqual(frappe.db.get_value("Item Group", name, "is_group"), 0)
		# creating the same group again is idempotent, not an error
		again = api.create_group(name)
		self.assertTrue(again["existed"])

	def test_get_items_finds_by_barcode(self):
		barcode = "HC" + frappe.generate_hash(length=10)
		code = self._new_item(barcode=barcode)["item_code"]

		res = api.get_items(search=barcode)
		found = [r["item_code"] for r in res["items"]]
		self.assertIn(code, found, "get_items should find an item by its barcode")

		# a barcode that matches nothing returns no rows
		empty = api.get_items(search="HCNOSUCHBARCODE0000")
		self.assertNotIn(code, [r["item_code"] for r in empty["items"]])

	def test_set_stock_creates_reconciliation(self):
		code = self._new_item(cost=30)["item_code"]

		out = api.set_stock(code, self.settings.default_warehouse, 7.5)
		self.assertEqual(out["qty"], 7.5)

		sr_item = frappe.db.get_value(
			"Stock Reconciliation Item",
			{"item_code": code, "warehouse": self.settings.default_warehouse, "qty": 7.5},
			"parent",
		)
		self.assertIsNotNone(sr_item)
		self.assertEqual(frappe.db.get_value("Stock Reconciliation", sr_item, "docstatus"), 1)

		bin_qty = frappe.db.get_value(
			"Bin", {"item_code": code, "warehouse": self.settings.default_warehouse}, "actual_qty"
		)
		self.assertEqual(bin_qty, 7.5)
