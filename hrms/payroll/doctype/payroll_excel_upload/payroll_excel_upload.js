// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

const PAYROLL_EXCEL_ALLOWED_TYPES = [
	".xlsx",
	".xls",
	".csv",
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	"application/vnd.ms-excel",
	"text/csv",
];

frappe.ui.form.on("Payroll Excel Upload", {
	setup(frm) {
		const attach = frm.fields_dict.payroll_file;
		if (!attach || attach._payroll_excel_upload_types_patched) {
			return;
		}
		attach._payroll_excel_upload_types_patched = true;
		attach.on_attach_click = function () {
			this.set_upload_options();
			this.upload_options.restrictions = this.upload_options.restrictions || {};
			this.upload_options.restrictions.allowed_file_types = PAYROLL_EXCEL_ALLOWED_TYPES;
			this.file_uploader = new frappe.ui.FileUploader(this.upload_options);
		};
	},
	refresh(frm) {
		if (frm.doc.docstatus !== 0 && !frm.is_new()) {
			return;
		}
		if (!frm.doc.payroll_file) {
			return;
		}
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
