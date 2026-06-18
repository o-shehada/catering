// Copyright (c) 2026, ARD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Consolidated Catering Invoice", {
	refresh(frm) {
		if (frm.doc.purchase_invoice) {
			frm.add_custom_button(__("Purchase Invoice"), () => {
				frappe.set_route("Form", "Purchase Invoice", frm.doc.purchase_invoice);
			}, __("View"));
		}
	},

	get_items(frm) {
		// Manual trigger: show messages (missing fields / no results).
		fetch_consumed_items(frm, true);
	},

	supplier(frm) {
		auto_fetch(frm);
	},

	from_date(frm) {
		auto_fetch(frm);
	},

	to_date(frm) {
		auto_fetch(frm);
	},

	price_list(frm) {
		auto_fetch(frm);
	},
});

frappe.ui.form.on("Catering Item Table", {
	qty(frm, cdt, cdn) {
		set_row_amount(frm, cdt, cdn);
	},

	rate(frm, cdt, cdn) {
		set_row_amount(frm, cdt, cdn);
	},

	invoice_items_remove(frm) {
		recalc_totals(frm);
	},
});

// Auto-refetch silently once supplier + both dates are present and the doc is still editable.
function auto_fetch(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}
	if (frm.doc.supplier && frm.doc.from_date && frm.doc.to_date) {
		fetch_consumed_items(frm, false);
	}
}

function fetch_consumed_items(frm, show_messages) {
	if (!frm.doc.supplier || !frm.doc.from_date || !frm.doc.to_date) {
		if (show_messages) {
			frappe.msgprint(__("Please set Supplier, From Date and To Date first."));
		}
		return;
	}
	frm.call({
		doc: frm.doc,
		method: "get_consumed_items",
		freeze: true,
		freeze_message: __("Collecting consumed items for the period..."),
	}).then((r) => {
		if (!r.message) {
			return;
		}
		const data = r.message;

		frm.clear_table("invoice_items");
		(data.items || []).forEach((row) => {
			const child = frm.add_child("invoice_items");
			Object.assign(child, row);
		});

		frm.clear_table("return_details");
		(data.return_details || []).forEach((row) => {
			const child = frm.add_child("return_details");
			Object.assign(child, row);
		});

		frm.set_value("referenced_returns", JSON.stringify(data.returns || []));
		frm.refresh_field("invoice_items");
		frm.refresh_field("return_details");
		recalc_totals(frm);

		if (show_messages && !(data.items || []).length) {
			frappe.msgprint(__("No consumed (returned, un-invoiced) items found in this period."));
		}
	});
}

function set_row_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "consumed_qty", row.qty || 0);
	frappe.model.set_value(cdt, cdn, "amount", (row.qty || 0) * (row.rate || 0));
	recalc_totals(frm);
}

function recalc_totals(frm) {
	let total_qty = 0;
	let total_amount = 0;
	(frm.doc.invoice_items || []).forEach((row) => {
		total_qty += row.qty || 0;
		total_amount += (row.qty || 0) * (row.rate || 0);
	});
	frm.set_value("total_qty", total_qty);
	frm.set_value("total_amount", total_amount);
}
