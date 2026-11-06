frappe.provide("hrms.payroll");

function hrms_is_payroll_excel_upload(opts = {}) {
	const doctype = opts.doctype || opts.frm?.doctype;
	return doctype === "Payroll Excel Upload" && opts.fieldname === "payroll_file";
}

function hrms_apply_payroll_excel_upload_restrictions(opts = {}) {
	if (!hrms_is_payroll_excel_upload(opts)) {
		return;
	}
	opts.restrictions = opts.restrictions || {};
	// Empty list: Frappe FileUploader skips client type validation.
	opts.restrictions.allowed_file_types = [];
}

hrms.payroll.patch_payroll_excel_file_uploader = function () {
	const Original = frappe.ui.FileUploader;
	if (!Original || Original.__hrms_payroll_excel_patched) {
		return;
	}

	function PatchedFileUploader(opts = {}) {
		hrms_apply_payroll_excel_upload_restrictions(opts);
		return new Original(opts);
	}

	PatchedFileUploader.UploadOptions = Original.UploadOptions;
	PatchedFileUploader.__hrms_payroll_excel_patched = true;
	frappe.ui.FileUploader = PatchedFileUploader;
};

hrms.payroll.patch_payroll_excel_file_uploader();
$(document).on("app_ready", () => hrms.payroll.patch_payroll_excel_file_uploader());
