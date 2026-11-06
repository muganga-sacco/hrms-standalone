// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Imported Payroll Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "payroll_month",
			label: __("Payroll Month"),
			fieldtype: "Date",
		},
		{
			fieldname: "from_month",
			label: __("From Month"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_month",
			label: __("To Month"),
			fieldtype: "Date",
		},
	],
};
