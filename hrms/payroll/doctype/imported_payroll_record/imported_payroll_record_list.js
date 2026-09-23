// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.listview_settings["Imported Payroll Record"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Download Payslip"), () => {
			hrms.imported_payroll_record.download_payslip_dialog();
		});
		listview.page.add_inner_button(__("Export Payroll Month (Excel)"), () => {
			hrms.imported_payroll_record.download_month_excel_dialog();
		});
		listview.page.add_inner_button(__("Payroll Register Report"), () => {
			frappe.set_route("query-report", "Imported Payroll Register");
		});
	},
};
