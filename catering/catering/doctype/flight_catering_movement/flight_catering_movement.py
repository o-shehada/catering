# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FlightCateringMovement(Document):
	def validate(self):
		self.calculate_amounts()
		if not self.status or self.docstatus == 0:
			self.status = "Draft"

	def calculate_amounts(self):
		total_qty = 0
		total_amount = 0
		for row in self.loaded_items:
			# On loading there is nothing returned yet; consumption is settled in Catering Return.
			row.amount = (row.qty or 0) * (row.rate or 0)
			total_qty += row.qty or 0
			total_amount += row.amount
		self.total_qty = total_qty
		self.total_amount = total_amount

	def on_submit(self):
		self.db_set("status", "Submitted")

	def on_cancel(self):
		self.db_set("status", "Draft")

	@frappe.whitelist()
	def get_template_items(self, template):
		"""Return the item list of a Flight Catering Template (item only; qty/rate entered here)."""
		template_doc = frappe.get_doc("Flight Catering Template", template)
		return [{"item": row.item, "item_name": row.item_name} for row in template_doc.items]
