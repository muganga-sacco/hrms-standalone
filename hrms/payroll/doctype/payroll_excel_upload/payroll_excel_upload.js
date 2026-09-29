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

function patch_payroll_file_attach_control() {
	const Cls = frappe.ui.form.ControlAttach;
	if (!Cls || Cls.prototype._payroll_excel_upload_patched) {
		return;
	}
	Cls.prototype._payroll_excel_upload_patched = true;
	const orig_on_attach_click = Cls.prototype.on_attach_click;
	Cls.prototype.on_attach_click = function () {
		if (
			this.frm?.doctype === "Payroll Excel Upload" &&
			this.df?.fieldname === "payroll_file"
		) {
			this.set_upload_options();
			this.upload_options.restrictions = this.upload_options.restrictions || {};
			this.upload_options.restrictions.allowed_file_types = PAYROLL_EXCEL_ALLOWED_TYPES;
			this.file_uploader = new frappe.ui.FileUploader(this.upload_options);
			return;
		}
		return orig_on_attach_click.apply(this, arguments);
	};
}

patch_payroll_file_attach_control();

function open_payroll_excel_uploader(frm) {
	new frappe.ui.FileUploader({
		doctype: frm.doctype,
		docname: frm.docname,
		fieldname: "payroll_file",
		frm,
		restrictions: { allowed_file_types: PAYROLL_EXCEL_ALLOWED_TYPES },
		on_success(file) {
			frm.set_value("payroll_file", file.file_url);
		},
	});
}

frappe.ui.form.on("Payroll Excel Upload", {
	onload() {
		patch_payroll_file_attach_control();
	},
	refresh(frm) {
		patch_payroll_file_attach_control();

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
