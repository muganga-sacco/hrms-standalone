// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.listview_settings["Payslip Request"] = {
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			"Pending HR": "orange",
			"Pending DAF": "blue",
			"Pending MD": "purple",
			Pending: "orange",
			Approved: "green",
			Rejected: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},

	onload(listview) {
		const prev = frappe.get_prev_route ? frappe.get_prev_route() : [];
		const from_my_payslips =
			prev && prev[0] === "Workspaces" && (prev[1] || "") === "My Payslips";
		const is_approver =
			frappe.session.user === "Administrator" ||
			frappe.user.has_role("HR Manager") ||
			frappe.user.has_role("HR User") ||
			frappe.user.has_role("DAF") ||
			frappe.user.has_role("MD");

		const self_employee = (callback) => {
			frappe.call({
				method:
					"hrms.payroll.doctype.payslip_request.payslip_request.get_self_employee_for_payslip_request",
				callback(r) {
					callback((r.message && r.message.name) || null);
				},
			});
		};

		const apply_mine = () => {
			self_employee((employee) => {
				listview.filter_area.clear();
				if (employee) {
					listview.filter_area.add([[listview.doctype, "employee", "=", employee]]);
				} else {
					listview.filter_area.add([
						[listview.doctype, "owner", "=", frappe.session.user],
					]);
				}
			});
		};

		listview.page.add_inner_button(__("My Requests"), apply_mine);

		if (from_my_payslips && !listview.filter_area.get().length) {
			apply_mine();
		}

		if (is_approver) {
			listview.page.add_inner_button(__("To Approve"), () => {
				self_employee((employee) => {
					listview.filter_area.clear();
					listview.filter_area.add([
						[
							listview.doctype,
							"status",
							"in",
							["Pending HR", "Pending DAF", "Pending MD", "Pending"],
						],
					]);
					if (employee) {
						listview.filter_area.add([
							[listview.doctype, "employee", "!=", employee],
						]);
					}
				});
			});
		}
	},
};
