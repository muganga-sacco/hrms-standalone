// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.listview_settings["Payroll Excel Upload"] = {
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			Imported: "orange",
			"Pending DAF": "blue",
			"Pending MD": "purple",
			Approved: "green",
			Rejected: "red",
			Failed: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},

	onload(listview) {
		const is_daf = frappe.session.user === "Administrator" || frappe.user.has_role("DAF");
		const is_md = frappe.session.user === "Administrator" || frappe.user.has_role("MD");
		const is_hr = frappe.user.has_role("HR Manager") || frappe.user.has_role("HR User");
		if (is_hr && !is_daf && !is_md) {
			return;
		}
		if (is_daf && !is_md) {
			listview.filter_area.add("Payroll Excel Upload", "status", "=", "Pending DAF");
		} else if (is_md && !is_daf) {
			listview.filter_area.add("Payroll Excel Upload", "status", "=", "Pending MD");
		} else if (is_daf || is_md) {
			listview.filter_area.add("Payroll Excel Upload", "status", "in", ["Pending DAF", "Pending MD"]);
		}
	},
};
