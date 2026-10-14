// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("hrms");

frappe.pages["variable-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Variable Dashboard"),
		single_column: true,
	});
	new hrms.VariableDashboard(page).show();
};

hrms.VariableDashboard = class VariableDashboard {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.company = frappe.defaults.get_user_default("Company");
		this.payroll_month = frappe.datetime.month_start();
	}

	show() {
		this.wrapper.html(`
			<style>
				.variable-dashboard { padding: 4px 0 24px; }
				.variable-dashboard .vd-toolbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 12px; }
				.variable-dashboard .vd-scroll { overflow-x: auto; }
				.variable-dashboard table { width: max-content; min-width: 100%; border-collapse: collapse; }
				.variable-dashboard th, .variable-dashboard td { border-bottom: 1px solid var(--border-color); padding: 8px; text-align: left; white-space: nowrap; }
				.variable-dashboard th { font-size: 12px; color: var(--text-muted); }
				.variable-dashboard tbody tr { cursor: pointer; }
				.variable-dashboard tbody tr:hover { background: var(--fg-hover-color, #f4f5f6); }
				.variable-dashboard .num { text-align: right; }
				.variable-dashboard .vd-actions { text-align: right; }
				.vd-detail { display: grid; grid-template-columns: 220px 1fr; gap: 6px 12px; }
				.vd-detail span { color: var(--text-muted); }
			</style>
			<div class="variable-dashboard">
				<div class="vd-toolbar">
					<div class="filter-company"></div>
					<div class="filter-month"></div>
					<div class="filter-type"></div>
					<button class="btn btn-primary btn-sm btn-upload">${__("Upload Excel")}</button>
					<button class="btn btn-default btn-sm btn-export">${__("Export Excel")}</button>
					<button class="btn btn-default btn-sm btn-refresh">${__("Refresh")}</button>
					<button class="btn btn-danger btn-sm btn-delete">${__("Delete")}</button>
				</div>
				<div class="vd-host"></div>
			</div>
		`);
		this.host = this.wrapper.find(".vd-host");
		this.wrapper.find(".btn-refresh").on("click", () => this.load());
		this.wrapper.find(".btn-upload").on("click", () => this.upload());
		this.wrapper.find(".btn-export").on("click", () => this.export_excel());
		this.wrapper.find(".btn-delete").on("click", () => this.delete_filtered());
		this.make_filters().then(() => this.load());
	}

	make_filters() {
		return frappe
			.call({
				method: "hrms.payroll.page.staff_payroll_dashboard.staff_payroll_dashboard.get_payroll_dashboard_companies",
			})
			.then((r) => {
				const companies = r.message || [];
				const company =
					this.company && companies.includes(this.company) ? this.company : companies[0];
				this.company_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-company")[0],
					df: {
						fieldtype: companies.length > 1 ? "Select" : "Data",
						options: companies.join("\n"),
						label: __("Company"),
						fieldname: "company",
						default: company,
						read_only: companies.length <= 1 ? 1 : 0,
					},
					render_input: true,
				});
				this.month_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-month")[0],
					df: {
						fieldtype: "Date",
						label: __("Payroll Month"),
						fieldname: "payroll_month",
						default: this.payroll_month,
					},
					render_input: true,
				});
				this.type_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-type")[0],
					df: {
						fieldtype: "Select",
						label: __("Bonus or Incentive"),
						fieldname: "variable_type",
						options: "\n",
					},
					render_input: true,
				});
			});
	}

	load() {
		frappe.call({
			method: "hrms.payroll.page.variable_dashboard.variable_dashboard.get_variable_dashboard",
			args: {
				variable_type: this.type_field?.get_value() || "",
				payroll_month: this.month_field?.get_value() || "",
				company: this.company_field?.get_value() || "",
			},
			callback: (r) => this.render(r.message || {}),
		});
	}

	render(data) {
		const types = data.types || [];
		const current = this.type_field.get_value();
		this.type_field.df.options = ["", ...types].join("\n");
		this.type_field.refresh();
		if (types.includes(current)) {
			this.type_field.set_value(current);
		}
		const rows = data.rows || [];
		this.rows = rows;
		if (!rows.length) {
			this.host.html(`<p class="text-muted">${__("No variable pay uploaded for this filter.")}</p>`);
			return;
		}
		const money = (value) => format_currency(value || 0);
		const body = rows
			.map(
				(row, index) => `<tr data-idx="${index}">
					<td>${index + 1}</td>
					<td>${frappe.utils.escape_html(row.employee_number || "")}</td>
					<td>${frappe.utils.escape_html(row.employee_name || "")}</td>
					<td>${frappe.datetime.str_to_user(row.date_of_joining) || ""}</td>
					<td>${frappe.utils.escape_html(row.department || "")}</td>
					<td>${frappe.utils.escape_html(row.position || "")}</td>
					<td class="num">${money(row.basic_salary)}</td>
					<td class="num">${money(row.gross_salary)}</td>
					<td class="num">${money(row.paye)}</td>
					<td class="num">${money(row.pension_employee)}</td>
					<td class="num">${money(row.pension_employer)}</td>
					<td class="num">${money(row.oh_employer)}</td>
					<td class="num">${money(row.maternity_employee)}</td>
					<td class="num">${money(row.maternity_employer)}</td>
					<td class="num">${money(row.net_before_cbhi)}</td>
					<td class="num">${money(row.cbhi)}</td>
					<td class="num">${money(row.net_take_home)}</td>
					<td>${frappe.utils.escape_html(row.account_number || "")}</td>
					<td>${frappe.utils.escape_html(row.bank || "")}</td>
					<td class="vd-actions"><button type="button" class="btn btn-danger btn-xs btn-delete-row" data-name="${frappe.utils.escape_html(row.name || "")}">${__("Delete")}</button></td>
				</tr>`
			)
			.join("");
		this.host.html(`
			<div class="vd-scroll">
			<table>
				<thead>
					<tr>
						<th>${__("S/N")}</th>
						<th>${__("ID NUMBER")}</th>
						<th>${__("NAMES")}</th>
						<th>${__("Date of Joining")}</th>
						<th>${__("DEPARTMENT")}</th>
						<th>${__("POSITION")}</th>
						<th class="num">${__("Basic salary")}</th>
						<th class="num">${__("Gross Salary")}</th>
						<th class="num">${__("PAYE")}</th>
						<th class="num">${__("Pension Employee 6%")}</th>
						<th class="num">${__("Pension Employer 6%")}</th>
						<th class="num">${__("OH Employer 2%")}</th>
						<th class="num">${__("Maternity Employee 0.3%")}</th>
						<th class="num">${__("Maternity Employer 0.3%")}</th>
						<th class="num">${__("Net before CBHI")}</th>
						<th class="num">${__("RSSB CBHI")}</th>
						<th class="num">${__("Net Take-home Salary")}</th>
						<th>${__("Account Number")}</th>
						<th>${__("Beneficiary Bank")}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
			</div>
		`);
		this.host.find("tbody tr").on("click", (event) => {
			if ($(event.target).closest(".btn-delete-row").length) {
				return;
			}
			const row = this.rows[Number(event.currentTarget.dataset.idx)];
			if (row) {
				this.show_staff(row);
			}
		});
		this.host.find(".btn-delete-row").on("click", (event) => {
			event.preventDefault();
			event.stopPropagation();
			const name = event.currentTarget.dataset.name;
			const row = this.rows.find((item) => item.name === name);
			this.delete_row(name, row);
		});
	}

	delete_row(name, row) {
		if (!name) {
			return;
		}
		const who = row?.employee_name || row?.employee_number || name;
		frappe.confirm(__("Delete variable pay for {0}?", [who]), () => {
			frappe.call({
				method: "hrms.payroll.page.variable_dashboard.variable_dashboard.delete_variable_record",
				args: { name },
				freeze: true,
				callback: (r) => {
					frappe.show_alert({
						message: r.message?.message || __("Variable pay row deleted."),
						indicator: "green",
					});
					this.load();
				},
			});
		});
	}

	export_excel() {
		const month = this.month_field?.get_value();
		if (!month) {
			frappe.msgprint(__("Choose the payroll month first."));
			return;
		}
		const params = new URLSearchParams({ payroll_month: month });
		const company = this.company_field?.get_value();
		const variable_type = this.type_field?.get_value();
		if (company) {
			params.set("company", company);
		}
		if (variable_type) {
			params.set("variable_type", variable_type);
		}
		window.open(
			`/api/method/hrms.payroll.page.variable_dashboard.variable_dashboard.download_variable_excel?${params}`,
			"_blank"
		);
	}

	delete_filtered() {
		const month = this.month_field?.get_value();
		if (!month) {
			frappe.msgprint(__("Choose the payroll month first."));
			return;
		}
		const variable_type = this.type_field?.get_value() || "";
		const company = this.company_field?.get_value() || "";
		const scope = variable_type || __("all bonus and incentive types");
		frappe.confirm(
			__("Delete variable pay for {0}, {1}? This cannot be undone.", [company || __("this company"), scope]),
			() => {
				frappe.call({
					method: "hrms.payroll.page.variable_dashboard.variable_dashboard.delete_variable_for_filters",
					args: { payroll_month: month, company, variable_type },
					freeze: true,
					callback: (r) => {
						frappe.show_alert({
							message: r.message?.message || __("Variable pay deleted."),
							indicator: "green",
						});
						this.load();
					},
				});
			}
		);
	}

	show_staff(row) {
		const money = (value) => format_currency(value || 0);
		const lines = [
			[__("Type"), row.variable_type],
			[__("ID NUMBER"), row.employee_number],
			[__("NAMES"), row.employee_name],
			[__("Date of Joining"), frappe.datetime.str_to_user(row.date_of_joining) || ""],
			[__("DEPARTMENT"), row.department],
			[__("POSITION"), row.position],
			[__("Basic salary"), money(row.basic_salary)],
			[__("Gross Salary"), money(row.gross_salary)],
			[__("PAYE"), money(row.paye)],
			[__("Pension Employee 6%"), money(row.pension_employee)],
			[__("Pension Employer 6%"), money(row.pension_employer)],
			[__("OH Employer 2%"), money(row.oh_employer)],
			[__("Maternity Employee 0.3%"), money(row.maternity_employee)],
			[__("Maternity Employer 0.3%"), money(row.maternity_employer)],
			[__("Net before CBHI"), money(row.net_before_cbhi)],
			[__("RSSB CBHI"), money(row.cbhi)],
			[__("Net Take-home Salary"), money(row.net_take_home)],
			[__("Account Number"), row.account_number],
			[__("Beneficiary Bank"), row.bank],
		];
		const html = `<div class="vd-detail">${lines
			.map(
				([label, value]) =>
					`<span>${frappe.utils.escape_html(label)}</span><div>${frappe.utils.escape_html(value || "-")}</div>`
			)
			.join("")}</div>`;
		frappe.msgprint({
			title: row.employee_name || row.employee_number,
			message: html,
			wide: true,
		});
	}

	upload() {
		const month = this.month_field?.get_value();
		const company = this.company_field?.get_value();
		if (!month) {
			frappe.msgprint(__("Choose the payroll month first."));
			return;
		}
		new frappe.ui.FileUploader({
			allow_multiple: false,
			restrictions: { allowed_file_types: [".xlsx", ".xls"] },
			on_success: (file) => {
				frappe.call({
					method: "hrms.payroll.page.variable_dashboard.variable_dashboard.upload_variable_excel",
					args: { file_url: file.file_url, payroll_month: month, company },
					freeze: true,
					freeze_message: __("Importing variable pay..."),
					callback: (r) => {
						const message = r.message || {};
						frappe.show_alert({
							message: __("Imported {0} rows", [message.imported || 0]),
							indicator: "green",
						});
						if (message.variable_type && this.type_field) {
							this.type_field.set_value(message.variable_type);
						}
						this.load();
					},
				});
			},
		});
	}
};
