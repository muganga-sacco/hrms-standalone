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

hrms.imported_payroll_record.MONTHS = [
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

hrms.imported_payroll_record.year_choices = function (selected_year) {
	const current = new Date().getFullYear();
	const years = [];
	for (let year = current - 2; year <= current + 1; year++) {
		years.push(String(year));
	}
	if (selected_year && !years.includes(String(selected_year))) {
		years.unshift(String(selected_year));
	}
	return years.join("\n");
};

hrms.imported_payroll_record.split_payroll_month = function (value) {
	const parts = String(value || "").split("-");
	let year = parts[0];
	let month_index = parseInt(parts[1] || "1", 10) - 1;
	if (!year || month_index < 0 || month_index > 11) {
		const now = frappe.datetime.str_to_obj(frappe.datetime.nowdate());
		year = String(now.getFullYear());
		month_index = now.getMonth();
	}
	return {
		year: String(year),
		month_name: hrms.imported_payroll_record.MONTHS[month_index],
	};
};

hrms.imported_payroll_record.compose_payroll_month = function (year, month_name) {
	const month_index = hrms.imported_payroll_record.MONTHS.indexOf(month_name);
	if (!year || month_index < 0) {
		return "";
	}
	return `${year}-${String(month_index + 1).padStart(2, "0")}-01`;
};

hrms.imported_payroll_record.download_payslip_dialog = function (defaults = {}) {
	const period = hrms.imported_payroll_record.split_payroll_month(defaults.payroll_month);
	const years = hrms.imported_payroll_record.year_choices(period.year);
	const months = hrms.imported_payroll_record.MONTHS.join("\n");
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
				fieldname: "payroll_year",
				fieldtype: "Select",
				label: __("Year"),
				options: years,
				default: period.year,
				reqd: 1,
			},
			{
				fieldname: "payroll_month_name",
				fieldtype: "Select",
				label: __("Month"),
				options: months,
				default: period.month_name,
				reqd: 1,
			},
			{
				fieldname: "to_year",
				fieldtype: "Select",
				label: __("To year"),
				options: years,
				default: period.year,
				reqd: 1,
			},
			{
				fieldname: "to_month_name",
				fieldtype: "Select",
				label: __("To month"),
				options: months,
				default: period.month_name,
				reqd: 1,
			},
		],
		(values) => {
			const from_month = hrms.imported_payroll_record.compose_payroll_month(
				values.payroll_year,
				values.payroll_month_name
			);
			const to_month = hrms.imported_payroll_record.compose_payroll_month(
				values.to_year,
				values.to_month_name
			);
			if (!from_month || !to_month) {
				frappe.msgprint(__("Year and Month are required."));
				return;
			}
			if (from_month > to_month) {
				frappe.msgprint(__("From month cannot be after To month."));
				return;
			}
			hrms.imported_payroll_record.open_payslip_download({
				employee_id_number: values.employee_id_number,
				from_month,
				to_month,
			});
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
