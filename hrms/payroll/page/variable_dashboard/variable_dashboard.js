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
	static MONTHS = [
		"January",
		"February",
		"March",
		"April",
		"May",
		"June",
		"July",
		"August",
		"September",
		"October",
		"November",
		"December",
	];

	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.company = frappe.defaults.get_user_default("Company");
		this.payroll_month = frappe.datetime.month_start();
	}

	show() {
		if (!$("#staff-payroll-dashboard-css").length) {
			$(
				'<link id="staff-payroll-dashboard-css" rel="stylesheet" href="/assets/hrms/css/staff_payroll_dashboard.css?v=20261026c">'
			).appendTo("head");
		}
		this.wrapper.html(`
			<div class="staff-payroll-dashboard variable-dashboard">
				<div class="toolbar-row">
					<div class="filter-company"></div>
					<div class="filter-year"></div>
					<div class="filter-month"></div>
					<div class="filter-actions">
						<button class="btn btn-primary btn-sm btn-upload">${__("Upload Excel")}</button>
						<button class="btn btn-default btn-sm btn-export">${__("Export Excel")}</button>
						<button class="btn btn-default btn-sm btn-refresh">${__("Refresh")}</button>
						<button class="btn btn-danger btn-sm btn-delete">${__("Delete")}</button>
					</div>
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
				method:
					"hrms.payroll.page.staff_payroll_dashboard.staff_payroll_dashboard.get_payroll_dashboard_options",
			})
			.then((r) => {
				const options = r.message || {};
				const companies = options.companies || [];
				const company =
					this.company && companies.includes(this.company) ? this.company : companies[0];
				this.company_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-company")[0],
					df: {
						fieldtype: "Select",
						options: (companies.length ? companies : [company].filter(Boolean)).join("\n"),
						label: __("Company"),
						fieldname: "company",
						read_only: companies.length <= 1 ? 1 : 0,
					},
					render_input: true,
				});
				const period = this.initial_period(options);
				const years = period.years.length ? period.years : [String(period.year)];
				this.year_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-year")[0],
					df: {
						fieldtype: "Select",
						options: years.join("\n"),
						label: __("Year"),
						fieldname: "payroll_year",
					},
					render_input: true,
				});
				this.month_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-month")[0],
					df: {
						fieldtype: "Select",
						options: hrms.VariableDashboard.MONTHS.join("\n"),
						label: __("Month"),
						fieldname: "payroll_month_name",
					},
					render_input: true,
				});
				return Promise.all([
					company ? this.company_field.set_value(company) : null,
					this.year_field.set_value(String(period.year)),
					this.month_field.set_value(hrms.VariableDashboard.MONTHS[period.month_index]),
				]).then(() => {
					if (company) {
						this.company_field.value = company;
						this.company_field.set_disp_area?.(company);
					}
				});
			});
	}

	initial_period(options) {
		const now = frappe.datetime.str_to_obj(frappe.datetime.nowdate());
		const years = (options.years || []).map((year) => String(year));
		const current_year = String(now.getFullYear());
		if (!years.includes(current_year)) {
			years.unshift(current_year);
		}
		const parts = String(options.latest_payroll_month || this.payroll_month || "").split("-");
		let year = parts[0] || current_year;
		let month_index = Math.max(0, parseInt(parts[1] || "1", 10) - 1);
		if (!years.includes(year)) {
			years.unshift(year);
		}
		if (Number.isNaN(month_index) || month_index > 11) {
			month_index = now.getMonth();
			year = current_year;
		}
		return { years, year, month_index };
	}

	get_payroll_month_value() {
		const year = String(this.year_field?.get_value() || "").trim();
		const month_name = this.month_field?.get_value();
		const month_index = hrms.VariableDashboard.MONTHS.indexOf(month_name);
		if (!year || month_index < 0) {
			return null;
		}
		return `${year}-${String(month_index + 1).padStart(2, "0")}-01`;
	}

	load() {
		const month = this.get_payroll_month_value();
		if (!month) {
			this.host.html(`<p class="text-muted">${__("Choose a payroll month.")}</p>`);
			return;
		}
		frappe.call({
			method:
				"hrms.payroll.page.staff_payroll_dashboard.staff_payroll_dashboard.get_staff_payroll_dashboard",
			args: {
				payroll_month: month,
				company: this.company_field?.get_value() || "",
				payroll_sheet_type: "Variable",
			},
			callback: (r) => this.render_sheet(r.message || {}),
		});
	}

	render_sheet(data) {
		const sheets = data.sheets?.length ? data.sheets : data.rows?.length ? [data] : [];
		if (!sheets.length) {
			const applied = data.filters_applied || {};
			this.host.html(
				`<div class="empty-state">${__(
					"No submitted variable pay for {0}. Import Excel from Payroll Excel Upload, sheet type Variable.",
					[applied.payroll_month || ""]
				)}</div>`
			);
			return;
		}
		const applied = data.filters_applied || {};
		const hint =
			sheets.length > 1
				? `<div class="sheet-filter-hint">${__(
						"{0} variable pays in {1}. Each one is shown as its own sheet.",
						[sheets.length, applied.payroll_month || ""]
				  )}</div>`
				: "";
		this.host.html(`
			${hint}
			<div class="variable-sheet-stack">${sheets.map((sheet) => this.variable_sheet_block(sheet)).join("")}</div>
		`);
	}

	variable_sheet_block(data) {
		const rows_html = data.rows.map((row) => this.variable_data_row(row)).join("");
		const footer = data.footer || {};
		const logo_html = data.logo_url
			? `<div class="sheet-logo-wrap"><img class="sheet-logo" src="${frappe.utils.escape_html(data.logo_url)}" alt="Company logo" /></div>`
			: `<div class="sheet-logo-placeholder">${frappe.utils.escape_html(data.company_name || "")}</div>`;
		const signatures_html = (footer.signatures || [])
			.filter((sig) => sig && (sig.name || sig.title || sig.heading))
			.map(
				(sig) => `<div class="signature-block">
				<div class="sig-heading">${this.esc(sig.heading)}</div>
				<div class="sig-name">${this.esc(sig.name)}</div>
				<div class="sig-title">${this.esc(sig.title)}</div>
			</div>`
			)
			.join("");
		return `
			<div class="sheet-wrap">
					<div class="sheet-brand-row">
						${logo_html}
						<div class="sheet-title">${frappe.utils.escape_html(data.title || "")}</div>
					</div>
					<table class="payroll-sheet">
						<thead>
							<tr>
								<th rowspan="3">S/N</th>
								<th rowspan="3">ID NUMBER</th>
								<th rowspan="3">NAMES</th>
								<th rowspan="3">Date of Joining</th>
								<th rowspan="3">DEPARTMENT</th>
								<th rowspan="3">POSITION</th>
								<th rowspan="3">Basic salary</th>
								<th rowspan="3">Gross Salary</th>
								<th rowspan="3">PAYE(PAY AS YOU EARN)</th>
								<th colspan="5" class="hdr-rssb">RSSB CONTRIBUTIONS</th>
								<th rowspan="3">Net before CBHI</th>
								<th rowspan="3">RSSB CBHI Scheme 0.5%</th>
								<th rowspan="3" class="col-yellow">Net Take-home Salary</th>
								<th rowspan="3">Account Number</th>
								<th rowspan="3" class="col-green">Beneficiary Bank</th>
							</tr>
							<tr>
								<th colspan="3" class="hdr-rssb-sub">PENSION SCHEME + OH</th>
								<th colspan="2" class="hdr-rssb-sub">MATERNITY LEAVE BENEFITS</th>
							</tr>
							<tr>
								<th class="hdr-rssb">Pension Employee 6%</th>
								<th class="hdr-rssb">Pension Employer 6%</th>
								<th class="hdr-rssb-sub">OH Employer 2%</th>
								<th class="hdr-rssb-sub">Employee 0,3%</th>
								<th class="hdr-rssb-sub">Employer 0,3%</th>
							</tr>
						</thead>
						<tbody>${rows_html}</tbody>
						<tfoot>${this.variable_total_row(data.totals, data.grand_total_label)}</tfoot>
					</table>
					<div class="sheet-footer">
						<div class="sheet-date-line">${this.esc(footer.date_line || "")}</div>
						<div class="sheet-signatures">${signatures_html}</div>
					</div>
			</div>
		`;
	}

	variable_data_row(row) {
		const take_home = parseFloat(row.take_home) || parseFloat(row.net_salary) || 0;
		return `<tr>
			<td>${row.sn}</td>
			<td>${this.esc(row.employee_id_number)}</td>
			<td>${this.esc(row.employee_name)}</td>
			<td>${this.esc(row.date_of_joining)}</td>
			<td>${this.esc(row.department)}</td>
			<td>${this.esc(row.position)}</td>
			<td class="num">${this.fmt(row.basic_salary)}</td>
			<td class="num">${this.fmt(row.gross_salary)}</td>
			<td class="num">${this.fmt(row.paye)}</td>
			<td class="num">${this.fmt(row.pension_employee)}</td>
			<td class="num">${this.fmt(row.pension_employer)}</td>
			<td class="num">${this.fmt(row.oh_employer)}</td>
			<td class="num">${this.fmt(row.maternity_employee)}</td>
			<td class="num">${this.fmt(row.maternity_employer)}</td>
			<td class="num">${this.fmt(row.net_before_cbhi)}</td>
			<td class="num">${this.fmt(row.cbhi)}</td>
			<td class="num col-yellow">${this.fmt(take_home)}</td>
			<td>${this.esc(row.account_number)}</td>
			<td class="col-green">${this.esc(row.bank)}</td>
		</tr>`;
	}

	variable_total_row(totals, label) {
		totals = totals || {};
		const take_home = parseFloat(totals.take_home) || parseFloat(totals.net_salary) || 0;
		return `<tr class="grand-total">
			<td colspan="6">${this.esc(label || __("GRAND TOTAL"))}</td>
			<td class="num">${this.fmt(totals.basic_salary)}</td>
			<td class="num">${this.fmt(totals.gross_salary)}</td>
			<td class="num">${this.fmt(totals.paye)}</td>
			<td class="num">${this.fmt(totals.pension_employee)}</td>
			<td class="num">${this.fmt(totals.pension_employer)}</td>
			<td class="num">${this.fmt(totals.oh_employer)}</td>
			<td class="num">${this.fmt(totals.maternity_employee)}</td>
			<td class="num">${this.fmt(totals.maternity_employer)}</td>
			<td class="num">${this.fmt(totals.net_before_cbhi)}</td>
			<td class="num">${this.fmt(totals.cbhi)}</td>
			<td class="num col-yellow">${this.fmt(take_home)}</td>
			<td colspan="2"></td>
		</tr>`;
	}

	fmt(val) {
		const n = parseFloat(val) || 0;
		if (!n) {
			return "-";
		}
		return frappe.format(n, { fieldtype: "Float", precision: 0 });
	}

	esc(val) {
		return frappe.utils.escape_html(val == null ? "" : String(val));
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
		const month = this.get_payroll_month_value();
		if (!month) {
			frappe.msgprint(__("Choose the payroll month first."));
			return;
		}
		const params = new URLSearchParams({ payroll_month: month });
		const company = this.company_field?.get_value();
		if (company) {
			params.set("company", company);
		}
		window.open(
			`/api/method/hrms.payroll.page.variable_dashboard.variable_dashboard.download_variable_excel?${params}`,
			"_blank"
		);
	}

	delete_filtered() {
		const month = this.get_payroll_month_value();
		if (!month) {
			frappe.msgprint(__("Choose the payroll month first."));
			return;
		}
		const company = this.company_field?.get_value() || "";
		frappe.confirm(
			__("Delete variable pay for {0}, {1}? This cannot be undone.", [
				company || __("this company"),
				month,
			]),
			() => {
				frappe.call({
					method: "hrms.payroll.page.variable_dashboard.variable_dashboard.delete_variable_for_filters",
					args: { payroll_month: month, company },
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
		const month = this.get_payroll_month_value();
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
