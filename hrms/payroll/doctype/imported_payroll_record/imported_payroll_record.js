// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Imported Payroll Record", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || !frm.doc.employee_id_number) {
			return;
		}
		frm.add_custom_button(__("Download Payslip"), () => {
			hrms.imported_payroll_record.download_payslip_dialog({
				employee_id_number: frm.doc.employee_id_number,
			});
		});
	},
});
