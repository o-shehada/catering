// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Flight Catering Movement", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== "Invoiced") {
			frm.add_custom_button(__("Catering Return"), () => {
				frappe.new_doc("Catering Return", {
					reference_movement: frm.doc.name,
				});
			}, __("Create"));
		}
	},

	select_template(frm) {
		if (!frm.doc.select_template) {
			return;
		}
		frm.call({
			doc: frm.doc,
			method: "get_template_items",
			args: { template: frm.doc.select_template },
			freeze: true,
			freeze_message: __("Loading template items..."),
		}).then((r) => {
			if (!r.message) {
				return;
			}
			frm.clear_table("loaded_items");
			(r.message || []).forEach((row) => {
				const child = frm.add_child("loaded_items");
				Object.assign(child, row);
			});
			frm.refresh_field("loaded_items");
			recalc_totals(frm);
		});
	},
});

frappe.ui.form.on("Flight Catering Movement Item", {
	item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item) {
			return;
		}
		// Pull the rate from the movement's Price List (fallback to any Item Price).
		const filters = { item_code: row.item };
		if (frm.doc.price_list) {
			filters.price_list = frm.doc.price_list;
		}
		frappe.db.get_value("Item Price", filters, "price_list_rate").then((res) => {
			if (res && res.message && res.message.price_list_rate) {
				frappe.model.set_value(cdt, cdn, "rate", res.message.price_list_rate);
			}
		});
	},

	qty(frm, cdt, cdn) {
		set_row_amount(frm, cdt, cdn);
	},

	rate(frm, cdt, cdn) {
		set_row_amount(frm, cdt, cdn);
	},

	loaded_items_remove(frm) {
		recalc_totals(frm);
	},
});

function set_row_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", (row.qty || 0) * (row.rate || 0));
	recalc_totals(frm);
}

function recalc_totals(frm) {
	let total_qty = 0;
	let total_amount = 0;
	(frm.doc.loaded_items || []).forEach((row) => {
		total_qty += row.qty || 0;
		total_amount += (row.qty || 0) * (row.rate || 0);
	});
	frm.set_value("total_qty", total_qty);
	frm.set_value("total_amount", total_amount);
}
