// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("hrms.payroll");

hrms.payroll.can_add_cachet = function () {
	return Boolean(frappe.boot.hrms_can_add_cachet);
};

hrms.payroll.add_cachet = function () {
	if (!hrms.payroll.can_add_cachet()) {
		frappe.msgprint(__("Only HR can add the payslip cachet."));
		return;
	}
	const input = document.createElement("input");
	input.type = "file";
	input.accept = "image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp";
	input.onchange = async () => {
		const file = input.files && input.files[0];
		if (!file) {
			return;
		}
		frappe.dom.freeze(__("Saving cachet..."));
		try {
			const form = new FormData();
			form.append("file", file, file.name);
			form.append("is_private", "1");
			form.append("folder", "Home");
			const response = await fetch("/api/method/upload_file", {
				method: "POST",
				headers: {
					"X-Frappe-CSRF-Token": frappe.csrf_token,
					Accept: "application/json",
				},
				body: form,
			});
			const data = await response.json();
			if (!response.ok || data.exc || !data.message) {
				frappe.msgprint({
					title: __("Upload failed"),
					message: data.exc || data._server_messages || __("Could not upload the cachet"),
					indicator: "red",
				});
				return;
			}
			await frappe.call({
				method: "hrms.payroll.payroll_import.payroll_signoff.save_payroll_cachet",
				args: { file_url: data.message.file_url },
			});
			frappe.show_alert({
				message: __("Cachet saved. It will appear on approved and downloaded payslips."),
				indicator: "green",
			});
		} finally {
			frappe.dom.unfreeze();
		}
	};
	input.click();
};

hrms.payroll.open_settings = function () {
	frappe.set_route("Form", "Payroll Settings", "Payroll Settings");
};

$(document).on("app_ready", () => {
	if (!(frappe.search && frappe.search.utils && frappe.search.utils.make_function_searchable)) {
		return;
	}
	if (hrms.payroll.can_add_cachet()) {
		frappe.search.utils.make_function_searchable(hrms.payroll.add_cachet, __("Add Cachet"));
	}
	if (frappe.model && frappe.model.can_read && frappe.model.can_read("Payroll Settings")) {
		frappe.search.utils.make_function_searchable(hrms.payroll.open_settings, __("Payroll Settings"));
	}
});
