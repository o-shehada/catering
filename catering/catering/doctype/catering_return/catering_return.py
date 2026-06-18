# Copyright (c) 2026, ARD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CateringReturn(Document):
	def validate(self):
		self.calculate_consumption()
		if self.docstatus == 0:
			self.status = "Draft"

	def calculate_consumption(self):
		total_consumed = 0
		total_amount = 0
		for row in self.return_items:
			returned = row.returned_qty or 0
			if returned > (row.qty or 0):
				frappe.throw(
					_("Row {0}: Returned Qty ({1}) cannot exceed Loaded Qty ({2}) for item {3}.").format(
						row.idx, returned, row.qty or 0, row.item
					)
				)
			row.consumed_qty = (row.qty or 0) - returned
			row.amount = row.consumed_qty * (row.rate or 0)
			total_consumed += row.consumed_qty
			total_amount += row.amount
		self.total_consumed_qty = total_consumed
		self.total_amount = total_amount

	def on_submit(self):
		self.status = "Submitted"
		self.db_set("status", "Submitted")
		frappe.db.set_value("Flight Catering Movement", self.reference_movement, "status", "Returned")

	def on_cancel(self):
		self.db_set("status", "Draft")
		# Revert the movement back to Submitted only if no other active return exists for it.
		other = frappe.db.exists(
			"Catering Return",
			{
				"reference_movement": self.reference_movement,
				"docstatus": 1,
				"name": ["!=", self.name],
			},
		)
		if not other:
			frappe.db.set_value(
				"Flight Catering Movement", self.reference_movement, "status", "Submitted"
			)

	@frappe.whitelist()
	def get_loaded_items(self, movement):
		"""Return the loaded item rows of a Flight Catering Movement as the basis for the return."""
		movement_doc = frappe.get_doc("Flight Catering Movement", movement)
		rows = []
		for row in movement_doc.loaded_items:
			rows.append(
				{
					"item": row.item,
					"item_name": row.item_name,
					"qty": row.qty,
					"returned_qty": 0,
					"consumed_qty": row.qty,
					"rate": row.rate,
					"amount": (row.qty or 0) * (row.rate or 0),
				}
			)
		return rows
