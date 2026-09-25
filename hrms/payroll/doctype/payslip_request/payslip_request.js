// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

function payslip_is_hr_approver() {
	return frappe.user.has_role("HR Manager") || frappe.user.has_role("HR User");
}

function payslip_hr_picks_employee() {
	return payslip_is_hr_approver();
}

frappe.ui.form.on("Payslip Request", {
	setup(frm) {
		if (!payslip_hr_picks_employee()) {
			frm.set_query("employee", () => ({
				filters: { user_id: frappe.session.user },
			}));
		}
	},

	onload(frm) {
		if (frm.is_new() && !payslip_hr_picks_employee()) {
			frappe.call({
				method:
					"hrms.payroll.doctype.payslip_request.payslip_request.get_self_employee_for_payslip_request",
				callback(r) {
					if (r.message && r.message.name) {
						frm.set_value("employee", r.message.name);
					} else {
						frappe.msgprint(
							__(
								"Your login is not linked to an Employee record. Ask HR to set User ID on your Employee profile."
							)
						);
					}
				},
			});
		}
	},

	refresh(frm) {
		frm.clear_custom_buttons();
		const is_hr = payslip_is_hr_approver();

		if (!payslip_hr_picks_employee()) {
			frm.set_df_property("employee", "read_only", 1);
		}

		if (frm.doc.status === "Draft" && !frm.is_new()) {
			frm.add_custom_button(__("Submit for Approval"), () => {
				frappe.call({
					method: "hrms.payroll.doctype.payslip_request.payslip_request.submit_payslip_request",
					args: { docname: frm.doc.name },
					freeze: true,
					callback() {
						frm.reload_doc();
						frappe.show_alert({ message: __("Submitted to HR"), indicator: "green" });
					},
				});
			}).addClass("btn-primary");
		}

		if (is_hr && frm.doc.status === "Pending") {
			frm.add_custom_button(__("Approve"), () => {
				frappe.call({
					method: "hrms.payroll.doctype.payslip_request.payslip_request.approve_payslip_request",
					args: { docname: frm.doc.name },
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			}).addClass("btn-primary");

			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					[
						{
							fieldname: "rejection_reason",
							fieldtype: "Small Text",
							label: __("Reason"),
							reqd: 1,
						},
					],
					(values) => {
						frappe.call({
							method: "hrms.payroll.doctype.payslip_request.payslip_request.reject_payslip_request",
							args: {
								docname: frm.doc.name,
								rejection_reason: values.rejection_reason,
							},
							freeze: true,
							callback() {
								frm.reload_doc();
							},
						});
					},
					__("Reject Payslip Request")
				);
			});
		}

		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("Download Payslip"), () => {
				const qs = new URLSearchParams({ docname: frm.doc.name });
				window.location.href = frappe.urllib.get_full_url(
					`/api/method/hrms.payroll.doctype.payslip_request.payslip_request.download_payslip_for_request?${qs}`
				);
			}).addClass("btn-primary");
		}

		if (!is_hr && frm.doc.status !== "Draft") {
			frm.set_df_property("period_type", "read_only", 1);
			frm.set_df_property("months", "read_only", 1);
			frm.set_df_property("payroll_month", "read_only", 1);
			frm.set_df_property("from_month", "read_only", 1);
			frm.set_df_property("to_month", "read_only", 1);
			frm.set_df_property("remarks", "read_only", 1);
		}
	},
});
