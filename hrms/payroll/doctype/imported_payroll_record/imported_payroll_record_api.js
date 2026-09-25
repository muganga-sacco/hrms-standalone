// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("hrms.imported_payroll_record");

hrms.imported_payroll_record.open_payslip_download = function (params) {
	const qs = new URLSearchParams(params);
	const url = frappe.urllib.get_full_url(
		`/api/method/hrms.payroll.doctype.imported_payroll_record.imported_payroll_record.download_payslip_docx?${qs}`
	);
	window.location.href = url;
};

hrms.imported_payroll_record.download_payslip_dialog = function (defaults = {}) {
	frappe.prompt(
		[
			{
				fieldname: "employee_id_number",
				fieldtype: "Data",
				label: __("Employee ID Number"),
				reqd: 1,
				default: defaults.employee_id_number,
			},
			{
				fieldname: "mode",
				fieldtype: "Select",
				label: __("Period"),
				options: [
					"Last N months",
					"Single payroll month",
					"From month – To month",
				].join("\n"),
				default: "Last N months",
				reqd: 1,
			},
			{
				fieldname: "months",
				fieldtype: "Int",
				label: __("Number of months"),
				default: 3,
				depends_on: 'eval:doc.mode=="Last N months"',
			},
			{
				fieldname: "payroll_month",
				fieldtype: "Date",
				label: __("Payroll month"),
				depends_on: 'eval:doc.mode=="Single payroll month"',
			},
			{
				fieldname: "from_month",
				fieldtype: "Date",
				label: __("From month"),
				depends_on: 'eval:doc.mode=="From month – To month"',
			},
			{
				fieldname: "to_month",
				fieldtype: "Date",
				label: __("To month"),
				depends_on: 'eval:doc.mode=="From month – To month"',
			},
		],
		(values) => {
			const params = new URLSearchParams({
				employee_id_number: values.employee_id_number,
			});
			if (values.mode === "Last N months") {
				params.set("months", values.months || 3);
			} else if (values.mode === "Single payroll month") {
				params.set("payroll_month", values.payroll_month);
			} else {
				params.set("from_month", values.from_month);
				params.set("to_month", values.to_month);
			}
			hrms.imported_payroll_record.open_payslip_download(Object.fromEntries(params));
		},
		__("Download Payslip"),
		__("Download")
	);
};

hrms.imported_payroll_record.download_month_excel_dialog = function () {
	frappe.prompt(
		[
			{
				fieldname: "payroll_month",
				fieldtype: "Date",
				label: __("Payroll Month"),
				reqd: 1,
			},
			{
				fieldname: "company",
				fieldtype: "Link",
				options: "Company",
				label: __("Company"),
				default: frappe.defaults.get_user_default("Company"),
			},
		],
		(values) => {
			const params = new URLSearchParams({
				payroll_month: values.payroll_month,
			});
			if (values.company) {
				params.set("company", values.company);
			}
			window.open(
				`/api/method/hrms.payroll.doctype.imported_payroll_record.imported_payroll_record.download_payroll_month_excel?${params}`,
				"_blank"
			);
		},
		__("Export Payroll Month"),
		__("Download Excel")
	);
};
