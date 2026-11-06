// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Employee", {
	refresh(frm) {
		const field = frm.get_field("employee_number");
		if (!field) {
			return;
		}
		field.df.hidden = 0;
		field.df.read_only = 0;
		frm.set_df_property("employee_number", "hidden", 0);
		frm.set_df_property("employee_number", "read_only", 0);
		field.set_label(__("Employee Number"));
		field.set_description("");
		frm.refresh_field("employee_number");
	},
});
