// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

function payslip_list_is_hr() {
	return frappe.user.has_role("HR Manager") || frappe.user.has_role("HR User");
}

frappe.listview_settings["Payslip Request"] = {
	onload(listview) {
		if (!payslip_list_is_hr()) {
			listview.page.hide_menu_item(__("Export"));
		}
	},
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			Pending: "orange",
			Approved: "green",
			Rejected: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
