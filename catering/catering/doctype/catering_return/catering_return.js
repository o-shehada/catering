// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Catering Return", {
	reference_movement(frm) {
		if (!frm.doc.reference_movement) {
			return;
		}
		frm.call({
			doc: frm.doc,
			method: "get_loaded_items",
			args: { movement: frm.doc.reference_movement },
			freeze: true,
			freeze_message: __("Loading shipped items..."),
		}).then((r) => {
			if (!r.message) {
				return;
			}
			frm.clear_table("return_items");
			(r.message || []).forEach((row) => {
				const child = frm.add_child("return_items");
				Object.assign(child, row);
			});
			frm.refresh_field("return_items");
			recalc_totals(frm);
		});
	},
});

frappe.ui.form.on("Catering Return Item", {
	returned_qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const returned = row.returned_qty || 0;
		if (returned > (row.qty || 0)) {
			frappe.msgprint(__("Returned Qty cannot exceed Loaded Qty for {0}.", [row.item]));
			frappe.model.set_value(cdt, cdn, "returned_qty", row.qty || 0);
			return;
		}
		const consumed = (row.qty || 0) - returned;
		frappe.model.set_value(cdt, cdn, "consumed_qty", consumed);
		frappe.model.set_value(cdt, cdn, "amount", consumed * (row.rate || 0));
		recalc_totals(frm);
	},

	rate(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", (row.consumed_qty || 0) * (row.rate || 0));
		recalc_totals(frm);
	},

	return_items_remove(frm) {
		recalc_totals(frm);
	},
});

function recalc_totals(frm) {
	let total_consumed = 0;
	let total_amount = 0;
	(frm.doc.return_items || []).forEach((row) => {
		const consumed = (row.qty || 0) - (row.returned_qty || 0);
		total_consumed += consumed;
		total_amount += consumed * (row.rate || 0);
	});
	frm.set_value("total_consumed_qty", total_consumed);
	frm.set_value("total_amount", total_amount);
}
