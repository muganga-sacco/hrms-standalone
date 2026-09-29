// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt
// FileUploader patch lives in hrms/public/js/payroll_excel_file_uploader.js (hrms.bundle.js).

function open_payroll_excel_uploader(frm) {
	new frappe.ui.FileUploader({
		doctype: frm.doctype,
		docname: frm.docname,
		fieldname: "payroll_file",
		frm,
		on_success(file) {
			frm.set_value("payroll_file", file.file_url);
		},
	});
}

frappe.ui.form.on("Payroll Excel Upload", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 && !frm.is_new()) {
			return;
		}

		if (!frm.doc.payroll_file) {
			frm.add_custom_button(__("Upload Excel File"), () => open_payroll_excel_uploader(frm));
			return;
		}

		frm.add_custom_button(__("Replace Excel File"), () => open_payroll_excel_uploader(frm));

		frm.add_custom_button(__("Refresh Logo & Signatures"), () => {
			frappe.call({
				method:
					"hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload.refresh_sheet_layout_from_excel",
				args: { docname: frm.doc.name },
				freeze: true,
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Sheet layout updated from Excel"), indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		});

		frm.add_custom_button(__("Import from Excel"), () => {
			const run_import = () => {
				frappe.call({
					method: "hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload.import_payroll_excel",
					args: { docname: frm.doc.name },
					freeze: true,
					freeze_message: __("Importing payroll..."),
					callback(r) {
						if (!r.exc) {
							frappe.show_alert({
								message: __("Imported {0} record(s)", [r.message.imported]),
								indicator: "green",
							});
							frm.reload_doc();
						}
					},
				});
			};
			if (frm.is_dirty()) {
				frm.save().then(run_import);
			} else {
				run_import();
			}
		});
	},
});
