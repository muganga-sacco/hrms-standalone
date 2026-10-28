// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

function payslip_is_hr_approver() {
	return (
		frappe.session.user === "Administrator" ||
		frappe.user.has_role("HR Manager") ||
		frappe.user.has_role("HR User")
	);
}

function payslip_is_daf() {
	return frappe.session.user === "Administrator" || frappe.user.has_role("DAF");
}

function payslip_hr_picks_employee() {
	return payslip_is_hr_approver();
}

const PAYSLIP_MONTHS = [
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
];

function payslip_period_from_date(value) {
	if (value) {
		const parts = String(value).split("-");
		const month_index = parseInt(parts[1] || "1", 10) - 1;
		if (parts[0] && month_index >= 0 && month_index <= 11) {
			return { year: parts[0], month_name: PAYSLIP_MONTHS[month_index] };
		}
	}
	const now = frappe.datetime.str_to_obj(frappe.datetime.nowdate());
	return { year: String(now.getFullYear()), month_name: PAYSLIP_MONTHS[now.getMonth()] };
}

function payslip_date_from_period(year, month_name) {
	const month_index = PAYSLIP_MONTHS.indexOf(month_name);
	if (!year || month_index < 0) {
		return "";
	}
	return `${year}-${String(month_index + 1).padStart(2, "0")}-01`;
}

function payslip_show_select(frm, fieldname, value) {
	const field = frm.fields_dict[fieldname];
	// set_input before the <select> exists records the option list and then
	// refuses to fill the real dropdown, so the field stays blank.
	if (field && field.$input && field.$input[0] && !field.$input[0].options.length) {
		field.last_options = null;
		field.set_options();
	}
	if (!value || frm.doc[fieldname] === value) {
		if (value && field && field.$input) {
			field.set_input(value);
		}
		return;
	}
	if (!field || !field.$input) {
		frm.doc[fieldname] = value;
		return;
	}
	frm.doc[fieldname] = value;
	field.set_input(value);
}

function payslip_sync_single(frm) {
	const value = payslip_date_from_period(frm.doc.payroll_year, frm.doc.payroll_month_name);
	if (!value) {
		return;
	}
	if (frm.doc.period_type === "From month – To month") {
		if (frm.doc.from_month !== value) {
			frm.set_value("from_month", value);
		}
		return;
	}
	if (frm.doc.payroll_month !== value) {
		frm.set_value("payroll_month", value);
	}
}

function payslip_sync_range(frm) {
	const to_month = payslip_date_from_period(frm.doc.to_year, frm.doc.to_month_name);
	if (to_month && frm.doc.to_month !== to_month) {
		frm.set_value("to_month", to_month);
	}
	payslip_sync_single(frm);
}

function payslip_fill_period(frm) {
	if ((frm.is_new() || frm.doc.status === "Draft") && frm.doc.period_type !== "From month – To month") {
		frm.set_value("period_type", "From month – To month");
	}
	const is_range = frm.doc.period_type === "From month – To month";
	const start = payslip_period_from_date(
		is_range ? frm.doc.from_month || frm.doc.payroll_month : frm.doc.payroll_month
	);
	const to_period = payslip_period_from_date(frm.doc.to_month || frm.doc.payroll_month);
	payslip_show_select(frm, "payroll_year", start.year);
	payslip_show_select(frm, "payroll_month_name", start.month_name);
	payslip_show_select(frm, "to_year", to_period.year);
	payslip_show_select(frm, "to_month_name", to_period.month_name);
	if (frm.is_new() || frm.doc.status === "Draft") {
		payslip_sync_single(frm);
		payslip_sync_range(frm);
	}
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
		payslip_fill_period(frm);
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
		const is_daf = payslip_is_daf();
		payslip_fill_period(frm);

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

		if (is_hr && (frm.doc.status === "Pending HR" || frm.doc.status === "Pending")) {
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
		}

		if (is_daf && frm.doc.status === "Pending DAF") {
			frm.add_custom_button(__("Approve"), () => {
				frappe.call({
					method: "hrms.payroll.doctype.payslip_request.payslip_request.daf_approve_payslip_request",
					args: { docname: frm.doc.name },
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			}).addClass("btn-primary");
		}

		if (
			(is_hr || is_daf) &&
			["Pending HR", "Pending DAF", "Pending"].includes(frm.doc.status)
		) {
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
			[
				"period_type",
				"months",
				"payroll_year",
				"payroll_month_name",
				"to_year",
				"to_month_name",
				"remarks",
			].forEach((fieldname) => frm.set_df_property(fieldname, "read_only", 1));
		}
	},

	payroll_year: payslip_sync_single,
	payroll_month_name: payslip_sync_single,
	period_type: payslip_sync_range,
	to_year: payslip_sync_range,
	to_month_name: payslip_sync_range,
});
