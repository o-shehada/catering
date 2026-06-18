# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class ConsolidatedCateringInvoice(Document):
	def validate(self):
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From Date cannot be after To Date."))
		self.calculate_totals()
		if self.docstatus == 0:
			self.status = "Draft"

	def calculate_totals(self):
		total_qty = 0
		total_amount = 0
		for row in self.invoice_items:
			# Consumed-only document: qty column carries the consumed quantity.
			row.consumed_qty = row.qty
			row.amount = (row.qty or 0) * (row.rate or 0)
			total_qty += row.qty or 0
			total_amount += row.amount
		self.total_qty = total_qty
		self.total_amount = total_amount

	def on_submit(self):
		self.db_set("status", "Submitted")
		# Mark the source returns (and their movements) as Invoiced so they are not billed twice.
		return_names = json.loads(self.referenced_returns or "[]")
		for name in return_names:
			movement = frappe.db.get_value("Catering Return", name, "reference_movement")
			frappe.db.set_value(
				"Catering Return", name, {"status": "Invoiced", "invoiced_in": self.name}
			)
			if movement:
				frappe.db.set_value("Flight Catering Movement", movement, "status", "Invoiced")
		# Generate the downstream Purchase Invoice (left as a draft for review).
		self.create_purchase_invoice()

	def on_cancel(self):
		self.db_set("status", "Draft")
		self.remove_purchase_invoice()
		return_names = json.loads(self.referenced_returns or "[]")
		for name in return_names:
			movement = frappe.db.get_value("Catering Return", name, "reference_movement")
			frappe.db.set_value(
				"Catering Return", name, {"status": "Submitted", "invoiced_in": None}
			)
			if movement:
				frappe.db.set_value("Flight Catering Movement", movement, "status", "Returned")

	def create_purchase_invoice(self):
		"""Create a draft Purchase Invoice billing the supplier for the consumed items."""
		# Idempotency: never create a second invoice for the same document.
		if self.purchase_invoice and frappe.db.exists("Purchase Invoice", self.purchase_invoice):
			return
		if not self.invoice_items:
			return

		company = (
			self.company
			or frappe.defaults.get_user_default("Company")
			or frappe.db.get_single_value("Global Defaults", "default_company")
		)
		if not company:
			frappe.throw(_("Please set a Company to create the Purchase Invoice."))

		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier = self.supplier
		pi.company = company
		pi.set_posting_time = 1
		pi.posting_date = nowdate()
		pi.ignore_pricing_rule = 1
		pi.consolidated_catering_invoice = self.name
		pi.remarks = _("Auto-created from Consolidated Catering Invoice {0} ({1} to {2}).").format(
			self.name, self.from_date, self.to_date
		)

		for row in self.invoice_items:
			pi.append(
				"items",
				{
					"item_code": row.item,
					"qty": row.qty,
					"rate": row.rate,
					"price_list_rate": row.rate,
				},
			)

		pi.flags.ignore_permissions = True
		pi.insert(ignore_permissions=True)

		self.db_set("purchase_invoice", pi.name)
		frappe.msgprint(
			_("Purchase Invoice {0} created as a draft.").format(
				frappe.utils.get_link_to_form("Purchase Invoice", pi.name)
			),
			indicator="green",
			alert=True,
		)

	def remove_purchase_invoice(self):
		"""On cancel, delete the linked draft Purchase Invoice (or block if already submitted)."""
		if not self.purchase_invoice or not frappe.db.exists("Purchase Invoice", self.purchase_invoice):
			self.db_set("purchase_invoice", None)
			return

		docstatus = frappe.db.get_value("Purchase Invoice", self.purchase_invoice, "docstatus")
		if docstatus == 1:
			frappe.throw(
				_("Cannot cancel: the linked Purchase Invoice {0} is submitted. Cancel it first.").format(
					self.purchase_invoice
				)
			)
		frappe.delete_doc(
			"Purchase Invoice", self.purchase_invoice, force=1, ignore_permissions=True
		)
		self.db_set("purchase_invoice", None)

	@frappe.whitelist()
	def get_consumed_items(self):
		"""Aggregate consumed quantities from submitted, not-yet-invoiced Catering Returns whose
		flight falls within the period and whose movement is from this supplier, priced from the
		selected Price List. Also returns a per-return summary for the Catering Returns tab."""
		if not self.from_date or not self.to_date:
			frappe.throw(_("Please set From Date and To Date first."))
		if not self.supplier:
			frappe.throw(_("Please set the Supplier first."))

		# Movements within the period AND for the selected supplier.
		movements = frappe.get_all(
			"Flight Catering Movement",
			filters={
				"docstatus": 1,
				"supplier": self.supplier,
				"flight_datetime": ["between", [self.from_date, self.to_date]],
			},
			pluck="name",
		)
		if not movements:
			return {"items": [], "returns": [], "return_details": []}

		return_docs = frappe.get_all(
			"Catering Return",
			filters={
				"docstatus": 1,
				"status": "Submitted",
				"reference_movement": ["in", movements],
			},
			fields=[
				"name",
				"reference_movement",
				"airplane",
				"flight_number",
				"total_consumed_qty",
				"total_amount",
			],
		)
		if not return_docs:
			return {"items": [], "returns": [], "return_details": []}

		returns = [r.name for r in return_docs]

		# Aggregate consumed qty per item across all matching returns.
		aggregated = {}
		rows = frappe.get_all(
			"Catering Return Item",
			filters={"parenttype": "Catering Return", "parent": ["in", returns]},
			fields=["item", "item_name", "consumed_qty"],
		)
		for row in rows:
			if not row.item:
				continue
			entry = aggregated.setdefault(
				row.item,
				{"item": row.item, "item_name": row.item_name, "qty": 0},
			)
			entry["qty"] += row.consumed_qty or 0

		# Price each item from the chosen price list.
		items = []
		for item, entry in aggregated.items():
			rate = self.get_item_rate(item)
			entry["rate"] = rate
			entry["consumed_qty"] = entry["qty"]
			entry["amount"] = entry["qty"] * rate
			items.append(entry)
		items.sort(key=lambda d: d["item"])

		# Per-return summary rows for the Catering Returns tab.
		return_details = [
			{
				"catering_return": r.name,
				"reference_movement": r.reference_movement,
				"airplane": r.airplane,
				"flight_number": r.flight_number,
				"total_consumed_qty": r.total_consumed_qty,
				"total_amount": r.total_amount,
			}
			for r in return_docs
		]

		return {"items": items, "returns": returns, "return_details": return_details}

	def get_item_rate(self, item):
		filters = {"item_code": item}
		if self.price_list:
			filters["price_list"] = self.price_list
		rate = frappe.db.get_value("Item Price", filters, "price_list_rate")
		return rate or 0
