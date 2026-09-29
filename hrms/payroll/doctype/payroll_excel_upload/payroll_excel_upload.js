// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

function upload_payroll_file_via_api(frm) {
	const pick_and_upload = () => {
		const input = document.createElement("input");
		input.type = "file";
		input.accept =
			".xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel";
		input.onchange = async () => {
			const file = input.files && input.files[0];
			if (!file) {
				return;
			}
			frappe.dom.freeze(__("Uploading {0}...", [file.name]));
			try {
				const form = new FormData();
				form.append("file", file, file.name);
				form.append("is_private", "1");
				form.append("folder", "Home");
				form.append("doctype", frm.doctype);
				form.append("docname", frm.docname);
				form.append("fieldname", "payroll_file");

				const response = await fetch("/api/method/upload_file", {
					method: "POST",
					headers: {
						"X-Frappe-CSRF-Token": frappe.csrf_token,
						Accept: "application/json",
					},
					body: form,
				});
				const data = await response.json();
				if (!response.ok || data.exc) {
					frappe.msgprint({
						title: __("Upload failed"),
						message: data.exc || data._server_messages || __("Could not upload file"),
						indicator: "red",
					});
					return;
				}
				const file_doc = data.message;
				const attach = frm.fields_dict.payroll_file;
				if (attach) {
					await attach.parse_validate_and_set_in_model(file_doc.file_url);
					attach.set_value(file_doc.file_url);
					attach.refresh();
				} else {
					await frm.set_value("payroll_file", file_doc.file_url);
				}
				if (frm.attachments) {
					frm.attachments.update_attachment(file_doc);
				}
				frm.refresh_field("payroll_file");
				frappe.show_alert({ message: __("File uploaded — you can save now"), indicator: "green" });
			} finally {
				frappe.dom.unfreeze();
			}
		};
		input.click();
	};

	// Do not save before upload on new docs: payroll_file is mandatory and save would fail first.
	if (!frm.is_new() && frm.is_dirty()) {
		frm.save().then(pick_and_upload);
	} else {
		pick_and_upload();
	}
}

function patch_payroll_file_attach_button(frm) {
	const attach = frm.fields_dict.payroll_file;
	if (!attach || attach._payroll_api_upload_patched) {
		return;
	}
	attach._payroll_api_upload_patched = true;
	attach.on_attach_click = () => upload_payroll_file_via_api(frm);
}

frappe.ui.form.on("Payroll Excel Upload", {
	onload(frm) {
		patch_payroll_file_attach_button(frm);
	},
	refresh(frm) {
		patch_payroll_file_attach_button(frm);

		if (frm.doc.docstatus !== 0 && !frm.is_new()) {
			return;
		}

		const upload_action = () => upload_payroll_file_via_api(frm);

		if (!frm.doc.payroll_file) {
			frm.add_custom_button(__("Upload Excel File"), upload_action);
			return;
		}

		frm.add_custom_button(__("Replace Excel File"), upload_action);

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
