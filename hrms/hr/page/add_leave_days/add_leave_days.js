// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("hrms");

frappe.pages["add-leave-days"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Add Leave Days"),
		single_column: true,
	});
	new hrms.AddLeaveDays(page);
};

hrms.AddLeaveDays = class AddLeaveDays {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.summary = null;
		this.make();
	}

	make() {
		this.wrapper.html(`
			<style>
				.add-leave-days { max-width: 720px; padding: 8px 0 32px; }
				.add-leave-days .ald-row { display: flex; gap: 16px; margin-bottom: 12px; }
				.add-leave-days .ald-row > div { flex: 1; }
				.add-leave-days label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
				.add-leave-days input, .add-leave-days select { width: 100%; }
				.add-leave-days .ald-readonly { background: var(--control-bg); padding: 8px 10px; border-radius: 6px; min-height: 36px; }
				.add-leave-days .ald-help { color: var(--text-muted); margin: 8px 0 16px; }
				.add-leave-days .ald-actions { margin-top: 16px; }
			</style>
			<div class="add-leave-days">
				<p class="ald-help">${__(
					"New Leaves starts at 0. Type a positive number to add days, or a negative number to remove days. Total is existing allocated plus that number."
				)}</p>
				<div class="ald-row">
					<div>
						<label>${__("Employee")}</label>
						<div class="ald-employee"></div>
					</div>
					<div>
						<label>${__("Leave Type")}</label>
						<div class="ald-leave-type"></div>
					</div>
				</div>
				<div class="ald-row">
					<div>
						<label>${__("Allocation")}</label>
						<div class="ald-readonly ald-allocation">—</div>
					</div>
					<div>
						<label>${__("Period")}</label>
						<div class="ald-readonly ald-period">—</div>
					</div>
				</div>
				<div class="ald-row">
					<div>
						<label>${__("Existing allocated (ledger)")}</label>
						<div class="ald-readonly ald-existing">0</div>
					</div>
					<div>
						<label>${__("Unused / carry forward")}</label>
						<div class="ald-readonly ald-unused">0</div>
					</div>
				</div>
				<div class="ald-row">
					<div>
						<label>${__("New Leaves Allocated")}</label>
						<input type="number" class="form-control ald-extra" value="0" step="0.5">
					</div>
					<div>
						<label>${__("Total Leaves Allocated")}</label>
						<div class="ald-readonly ald-total">0</div>
					</div>
				</div>
				<div class="ald-actions">
					<button class="btn btn-primary btn-sm ald-save">${__("Apply days")}</button>
				</div>
			</div>
		`);

		this.employee_ctrl = frappe.ui.form.make_control({
			parent: this.wrapper.find(".ald-employee"),
			df: { fieldtype: "Link", options: "Employee", fieldname: "employee" },
			render_input: true,
		});
		this.leave_type_ctrl = frappe.ui.form.make_control({
			parent: this.wrapper.find(".ald-leave-type"),
			df: {
				fieldtype: "Link",
				options: "Leave Type",
				fieldname: "leave_type",
				default: "Annual leave",
			},
			render_input: true,
		});
		this.leave_type_ctrl.set_value("Annual leave");

		this.employee_ctrl.$input.on("change", () => this.load());
		this.leave_type_ctrl.$input.on("change", () => this.load());
		this.wrapper.find(".ald-extra").on("input", () => this.refresh_total());
		this.wrapper.find(".ald-save").on("click", () => this.save());
	}

	load() {
		const employee = this.employee_ctrl.get_value();
		const leave_type = this.leave_type_ctrl.get_value() || "Annual leave";
		this.wrapper.find(".ald-extra").val(0);
		if (!employee) {
			this.summary = null;
			this.paint(null);
			return;
		}
		frappe.call({
			method: "hrms.hr.add_leave_allocation_days.get_allocation_summary",
			args: { employee, leave_type, year: 2026 },
			callback: (r) => {
				this.summary = r.message && r.message.found ? r.message : null;
				this.paint(this.summary);
			},
		});
	}

	paint(s) {
		if (!s) {
			this.wrapper.find(".ald-allocation").text("—");
			this.wrapper.find(".ald-period").text("—");
			this.wrapper.find(".ald-existing").text("0");
			this.wrapper.find(".ald-unused").text("0");
			this.wrapper.find(".ald-total").text("0");
			return;
		}
		this.wrapper.find(".ald-allocation").text(s.allocation);
		this.wrapper.find(".ald-period").text(`${s.from_date} → ${s.to_date}`);
		this.wrapper.find(".ald-existing").text(s.existing_total);
		this.wrapper.find(".ald-unused").text(s.unused_leaves);
		this.refresh_total();
	}

	extra_days() {
		return flt(this.wrapper.find(".ald-extra").val() || 0);
	}

	refresh_total() {
		const existing = this.summary ? flt(this.summary.existing_total) : 0;
		this.wrapper.find(".ald-total").text(existing + this.extra_days());
	}

	save() {
		if (!this.summary) {
			frappe.msgprint(__("Select an employee with a submitted allocation first."));
			return;
		}
		const days = this.extra_days();
		if (days === 0) {
			frappe.msgprint(__("Type days in New Leaves Allocated (positive to add, negative to remove)."));
			return;
		}
		frappe.call({
			method: "hrms.hr.add_leave_allocation_days.apply_extra_days",
			args: {
				employee: this.summary.employee,
				leave_type: this.summary.leave_type,
				days,
				year: 2026,
			},
			freeze: true,
			freeze_message: days < 0 ? __("Removing days...") : __("Adding days..."),
			callback: (r) => {
				frappe.show_alert({
					message: days < 0
						? __("Removed {0} days. Total is now {1}.", [
							Math.abs(days),
							r.message.existing_total,
						])
						: __("Added {0} days. Total is now {1}.", [
							days,
							r.message.existing_total,
						]),
					indicator: "green",
				});
				this.summary = r.message;
				this.wrapper.find(".ald-extra").val(0);
				this.paint(this.summary);
			},
		});
	}
};
