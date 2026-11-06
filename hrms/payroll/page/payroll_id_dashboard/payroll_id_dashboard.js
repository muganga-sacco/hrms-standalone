// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("hrms");

frappe.pages["payroll-id-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Payroll ID Numbers"),
		single_column: true,
	});
	new hrms.PayrollIdDashboard(page).show();
};

hrms.PayrollIdDashboard = class PayrollIdDashboard {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.rows = [];
		this.include_inactive = false;
	}

	show() {
		this.wrapper.html(`
			<style>
				.payroll-id-dashboard { padding: 4px 0 24px; }
				.payroll-id-dashboard .pid-note {
					margin-bottom: 12px;
					color: var(--text-muted);
					max-width: 820px;
				}
				.payroll-id-dashboard .pid-toolbar {
					display: flex;
					flex-wrap: wrap;
					gap: 8px;
					align-items: center;
					margin-bottom: 12px;
				}
				.payroll-id-dashboard .pid-toolbar input[type="search"] {
					min-width: 240px;
				}
				.payroll-id-dashboard .pid-table-wrap {
					overflow: auto;
					border: 1px solid var(--border-color);
					background: var(--card-bg);
				}
				.payroll-id-dashboard table { margin: 0; }
				.payroll-id-dashboard th, .payroll-id-dashboard td {
					vertical-align: middle;
					white-space: nowrap;
				}
				.payroll-id-dashboard .pid-input { min-width: 140px; }
				.payroll-id-dashboard tr.pid-dirty { background: var(--yellow-50, #fff8e1); }
				.payroll-id-dashboard .pid-missing { color: var(--red-600, #c0392b); }
			</style>
			<div class="payroll-id-dashboard">
				<p class="pid-note">
				
				<div class="pid-toolbar">
					<input type="search" class="form-control input-sm pid-search" placeholder="${__("Search name, Frappe ID, or payroll ID")}">
					<label class="checkbox pid-inactive">
						<input type="checkbox" class="pid-include-inactive"> ${__("Include inactive")}
					</label>
					<button class="btn btn-default btn-sm pid-refresh">${__("Refresh")}</button>
					<button class="btn btn-primary btn-sm pid-save">${__("Save changes")}</button>
				</div>
				<div class="pid-table-wrap"></div>
			</div>
		`);
		this.host = this.wrapper.find(".pid-table-wrap");
		this.wrapper.find(".pid-refresh").on("click", () => this.load());
		this.wrapper.find(".pid-save").on("click", () => this.save());
		this.wrapper.find(".pid-search").on("input", () => this.render());
		this.wrapper.find(".pid-include-inactive").on("change", (event) => {
			this.include_inactive = event.target.checked;
			this.load();
		});
		this.load();
	}

	load() {
		this.host.html(`<div class="text-muted" style="padding:12px">${__("Loading...")}</div>`);
		frappe.call({
			method: "hrms.payroll.page.payroll_id_dashboard.payroll_id_dashboard.get_payroll_id_rows",
			args: { include_inactive: this.include_inactive ? 1 : 0 },
			callback: (r) => {
				this.rows = (r.message || []).map((row) => ({
					...row,
					draft_id: row.payroll_id || "",
				}));
				this.render();
			},
		});
	}

	filtered_rows() {
		const query = (this.wrapper.find(".pid-search").val() || "").trim().toLowerCase();
		if (!query) {
			return this.rows;
		}
		return this.rows.filter((row) => {
			const haystack = [row.employee, row.employee_name, row.department, row.draft_id, row.user_id]
				.join(" ")
				.toLowerCase();
			return haystack.includes(query);
		});
	}

	render() {
		const rows = this.filtered_rows();
		if (!rows.length) {
			this.host.html(`<div class="text-muted" style="padding:12px">${__("No employees found.")}</div>`);
			return;
		}
		const body = rows
			.map((row) => {
				const dirty = (row.draft_id || "") !== (row.payroll_id || "");
				const login = row.user_id
					? frappe.utils.escape_html(row.user_id)
					: `<span class="pid-missing">${__("No login")}</span>`;
				const payslips =
					!row.staff_count && !row.lumpsum_count
						? __("None uploaded")
						: __("Staff {0} · Lumpsum {1}", [row.staff_count || 0, row.lumpsum_count || 0]);
				return `
					<tr class="${dirty ? "pid-dirty" : ""}" data-employee="${frappe.utils.escape_html(row.employee)}">
						<td><a href="/app/employee/${encodeURIComponent(row.employee)}">${frappe.utils.escape_html(row.employee)}</a></td>
						<td>${frappe.utils.escape_html(row.employee_name || "")}</td>
						<td>${frappe.utils.escape_html(row.department || "")}</td>
						<td>${login}</td>
						<td><input class="form-control input-sm pid-input" value="${frappe.utils.escape_html(row.draft_id || "")}"></td>
						<td>${payslips}</td>
					</tr>`;
			})
			.join("");
		this.host.html(`
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>${__("HR ID")}</th>
						<th>${__("Employee")}</th>
						<th>${__("Department")}</th>
						<th>${__("Login")}</th>
						<th>${__("Employee ID Number")}</th>
						<th>${__("Uploaded payslips")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`);
		this.host.find(".pid-input").on("input", (event) => {
			const employee = $(event.target).closest("tr").attr("data-employee");
			const row = this.rows.find((item) => item.employee === employee);
			if (!row) {
				return;
			}
			row.draft_id = event.target.value;
			$(event.target)
				.closest("tr")
				.toggleClass("pid-dirty", (row.draft_id || "").trim() !== (row.payroll_id || ""));
		});
	}

	save() {
		const changed = this.rows
			.filter((row) => (row.draft_id || "").trim() !== (row.payroll_id || ""))
			.map((row) => ({ employee: row.employee, payroll_id: (row.draft_id || "").trim() }));
		if (!changed.length) {
			frappe.show_alert({ message: __("No changes to save"), indicator: "orange" });
			return;
		}
		frappe.call({
			method: "hrms.payroll.page.payroll_id_dashboard.payroll_id_dashboard.save_payroll_ids",
			args: { rows: changed },
			freeze: true,
			freeze_message: __("Saving payroll IDs..."),
			callback: (r) => {
				const saved = r.message || {};
				frappe.show_alert({
					message: __("Saved {0} employees. Linked {1} payroll rows.", [
						saved.saved || 0,
						saved.linked_records || 0,
					]),
					indicator: "green",
				});
				this.load();
			},
		});
	}
};
