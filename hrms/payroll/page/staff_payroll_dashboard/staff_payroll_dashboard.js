// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("hrms");

frappe.pages["staff-payroll-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Staff Payroll Dashboard"),
		single_column: true,
	});

	if (!$("#staff-payroll-dashboard-css").length) {
		$(
			'<link id="staff-payroll-dashboard-css" rel="stylesheet" href="/assets/hrms/css/staff_payroll_dashboard.css?v=20261026c">'
		).appendTo("head");
	}

	const dashboard = new hrms.StaffPayrollDashboard(page);
	dashboard.show();
};

hrms.StaffPayrollDashboard = class StaffPayrollDashboard {
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
		this.is_hr_payroll = frappe.user.has_role("HR Manager") || frappe.user.has_role("HR User");
		this.render_shell();
		this.make_filters().then(() => this.load_data({ silent: true }));
	}

	render_shell() {
		this.wrapper.html(`
			<div class="staff-payroll-dashboard">
				<div class="toolbar-row">
					<div class="filter-company"></div>
					<div class="filter-year"></div>
					<div class="filter-month"></div>
					<div class="filter-sheet-type"></div>
					<div class="filter-actions">
						<button class="btn btn-primary btn-sm btn-refresh">${__("Refresh")}</button>
						<button class="btn btn-default btn-sm btn-export">${__("Export Excel")}</button>
						<button class="btn btn-default btn-sm btn-payslip-search">${__("Download Payslip")}</button>
						<button class="btn btn-danger btn-sm btn-delete-payroll">${__("Delete Payroll")}</button>
					</div>
				</div>
				<div class="sheet-host"></div>
			</div>
		`);

		this.sheet_host = this.wrapper.find(".sheet-host");
		this.wrapper.find(".btn-refresh").on("click", () => {
			const month = this.get_payroll_month_value();
			if (month) {
				this._committed_payroll_month = month;
			}
			this.load_data();
		});
		if (this.is_hr_payroll) {
			this.wrapper.find(".btn-export").on("click", () => this.export_excel());
			this.wrapper.find(".btn-payslip-search").on("click", () => this.payslip_dialog());
			this.wrapper.find(".btn-delete-payroll").on("click", () => this.delete_payroll());
		} else {
			this.wrapper.find(".btn-export, .btn-payslip-search, .btn-delete-payroll").remove();
		}
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
				this.dashboard_companies = companies;
				const default_company =
					this.company && companies.includes(this.company)
						? this.company
						: companies[0] || this.company || "";
				const period = this.initial_period(options);
				const years = period.years.length ? period.years : [String(period.year)];
				this.company_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-company")[0],
					df: {
						fieldtype: "Select",
						options: (companies.length ? companies : [default_company].filter(Boolean)).join(
							"\n"
						),
						label: __("Company"),
						fieldname: "company",
						read_only: companies.length <= 1 ? 1 : 0,
					},
					render_input: true,
				});
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
						options: hrms.StaffPayrollDashboard.MONTHS.join("\n"),
						label: __("Month"),
						fieldname: "payroll_month_name",
					},
					render_input: true,
				});
				this.sheet_type_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-sheet-type")[0],
					df: {
						fieldtype: "Select",
						label: __("Sheet Type"),
						fieldname: "payroll_sheet_type",
						options: "Staff Payroll\nLumpsum\nVariable\nAll",
						default: "Staff Payroll",
					},
					render_input: true,
				});
				this._committed_payroll_month = period.payroll_month;
				return Promise.all([
					default_company ? this.company_field.set_value(default_company) : null,
					this.year_field.set_value(String(period.year)),
					this.month_field.set_value(hrms.StaffPayrollDashboard.MONTHS[period.month_index]),
					this.sheet_type_field.set_value("Staff Payroll"),
				]).then(() => {
					this.show_company_name(default_company);
					const reload = () => this.schedule_filter_reload();
					this.company_field.df.onchange = reload;
					this.year_field.df.onchange = reload;
					this.month_field.df.onchange = reload;
					this.sheet_type_field.df.onchange = reload;
				});
			});
	}

	show_company_name(company) {
		if (!company || !this.company_field) {
			return;
		}
		this.company_field.value = company;
		if (this.company_field.set_disp_area) {
			this.company_field.set_disp_area(company);
		}
		if (this.company_field.$input) {
			this.company_field.$input.val(company);
		}
	}

	initial_period(options) {
		const now = frappe.datetime.str_to_obj(frappe.datetime.nowdate());
		const years = (options.years || []).map((year) => String(year));
		const current_year = String(now.getFullYear());
		if (!years.includes(current_year)) {
			years.unshift(current_year);
		}
		let payroll_month = options.latest_payroll_month || this.payroll_month;
		const parts = String(payroll_month || "").split("-");
		let year = parts[0] || current_year;
		let month_index = Math.max(0, parseInt(parts[1] || "1", 10) - 1);
		if (!years.includes(year)) {
			years.unshift(year);
		}
		if (Number.isNaN(month_index) || month_index > 11) {
			month_index = now.getMonth();
			year = current_year;
		}
		payroll_month = `${year}-${String(month_index + 1).padStart(2, "0")}-01`;
		return { years, year, month_index, payroll_month };
	}

	schedule_filter_reload(options = {}) {
		clearTimeout(this._filter_reload_timer);
		this._filter_reload_timer = setTimeout(() => {
			const month = this.get_payroll_month_value();
			if (!month) {
				return;
			}
			if (!options.force) {
				if (
					month === this.last_requested_filters?.payroll_month &&
					(this.company_field?.get_value() || null) ===
						(this.last_requested_filters?.company || null) &&
					(this.sheet_type_field?.get_value() || "Staff Payroll") ===
						(this.last_requested_filters?.payroll_sheet_type || "Staff Payroll")
				) {
					return;
				}
			}
			this.load_data({ silent: true });
		}, 150);
	}

	get_payroll_month_value() {
		const year = String(this.year_field?.get_value() || "").trim();
		const month_name = this.month_field?.get_value();
		return this.compose_payroll_month(year, month_name) || this._committed_payroll_month || null;
	}

	year_choices(selected_year) {
		const current = new Date().getFullYear();
		const years = [];
		for (let year = current - 2; year <= current + 1; year++) {
			years.push(String(year));
		}
		if (selected_year && !years.includes(String(selected_year))) {
			years.unshift(String(selected_year));
		}
		return years.join("\n");
	}

	split_payroll_month(value) {
		const parts = String(value || "").split("-");
		let year = parts[0];
		let month_index = parseInt(parts[1] || "1", 10) - 1;
		if (!year || month_index < 0 || month_index > 11) {
			const now = frappe.datetime.str_to_obj(frappe.datetime.nowdate());
			year = String(now.getFullYear());
			month_index = now.getMonth();
		}
		return {
			year: String(year),
			month_name: hrms.StaffPayrollDashboard.MONTHS[month_index],
		};
	}

	compose_payroll_month(year, month_name) {
		const month_index = hrms.StaffPayrollDashboard.MONTHS.indexOf(month_name);
		if (!year || month_index < 0) {
			return "";
		}
		return `${year}-${String(month_index + 1).padStart(2, "0")}-01`;
	}

	get_filters() {
		const payroll_month = this.get_payroll_month_value();
		let company = (this.company_field.get_value() || "").trim();
		if (!company && this.dashboard_companies?.length === 1) {
			company = this.dashboard_companies[0];
		}
		return {
			company: company || null,
			payroll_month,
			payroll_sheet_type: this.sheet_type_field?.get_value() || "Staff Payroll",
		};
	}

	load_data(options = {}) {
		const filters = this.get_filters();
		if (!filters.payroll_month) {
			if (!options.silent) {
				frappe.msgprint(__("Please select Payroll Month."));
			}
			return;
		}
		this.last_requested_filters = { ...filters };
		this._committed_payroll_month = filters.payroll_month;
		this._load_seq = (this._load_seq || 0) + 1;
		const load_seq = this._load_seq;
		this.sheet_host.html(`<div class="empty-state">${__("Loading payroll…")}</div>`);
		frappe.call({
			method: "hrms.payroll.page.staff_payroll_dashboard.staff_payroll_dashboard.get_staff_payroll_dashboard",
			args: filters,
			freeze: !options.silent,
			callback: (r) => {
				if (load_seq !== this._load_seq) {
					return;
				}
				this.render_sheet(r.message || {});
			},
		});
	}

	delete_payroll() {
		const filters = this.get_filters();
		if (!filters.payroll_month) {
			frappe.msgprint(__("Please select Payroll Month (pick a day in the calendar, then try again)."));
			return;
		}
		const company = filters.company || __("all companies");
		const sheet = filters.payroll_sheet_type || "Staff Payroll";
		const month = filters.payroll_month;
		frappe.confirm(
			__(
				"Permanently delete submitted payroll for {0}, {1}, sheet type {2}? This cannot be undone.",
				[company, month, sheet]
			),
			() => {
				frappe.call({
					method:
						"hrms.payroll.page.staff_payroll_dashboard.staff_payroll_dashboard.delete_payroll_for_filters",
					args: filters,
					freeze: true,
					callback: (r) => {
						const msg = r.message?.message || __("Payroll deleted.");
						frappe.show_alert({ message: msg, indicator: "green" });
						this.load_data({ silent: true });
					},
				});
			}
		);
	}

	export_excel() {
		const filters = this.get_filters();
		if (!filters.payroll_month) {
			frappe.msgprint(__("Please select Payroll Month (pick a day in the calendar, then try again)."));
			return;
		}
		const params = new URLSearchParams({ payroll_month: filters.payroll_month });
		if (filters.company) {
			params.set("company", filters.company);
		}
		if (filters.payroll_sheet_type && filters.payroll_sheet_type !== "All") {
			params.set("payroll_sheet_type", filters.payroll_sheet_type);
		}
		window.open(
			`/api/method/hrms.payroll.doctype.imported_payroll_record.imported_payroll_record.download_payroll_month_excel?${params}`,
			"_blank"
		);
	}

	render_sheet(data) {
		if (data.layout === "variable" || data.payroll_sheet_type === "Variable") {
			this.render_variable_sheet(data);
			return;
		}
		if (!data.rows || !data.rows.length) {
			const applied = data.filters_applied || {};
			const month = applied.payroll_month || "";
			const sheet = applied.payroll_sheet_type || "";
			this.sheet_host.html(
				`<div class="empty-state">${__(
					"No submitted payroll for {0} ({1}). Import Excel or choose another month.",
					[month, sheet]
				)}</div>`
			);
			return;
		}

		if (data.layout === "lumpsum" || data.payroll_sheet_type === "Lumpsum") {
			this.render_lumpsum_sheet(data);
			return;
		}

		const rows_html = data.rows.map((row) => this.render_data_row(row)).join("");
		const subtotal_html =
			data.rows.length > 1 ? this.render_total_row(data.totals, "S/TOTAL1") : "";
		const grand_label =
			data.grand_total_label ||
			(data.month_label ? `GRAND TOTAL_${data.month_label}` : "GRAND TOTAL");
		const totals_html = this.render_total_row(data.totals, grand_label);
		const { logo_html, footer, signatures_html, filter_hint_html } = this.build_sheet_chrome(data);

		this.sheet_host.html(`
			<div class="sheet-wrap">
				${filter_hint_html}
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
							<th rowspan="3">Transport allowance CRO</th>
							<th rowspan="3">ITC allowance</th>
							<th rowspan="3">ICT allowance</th>
							<th rowspan="3">Gross Salary</th>
							<th rowspan="3">PAYE(PAY AS YOU EARN)</th>
							<th colspan="5" class="hdr-rssb">RSSB CONTRIBUTIONS</th>
							<th rowspan="3">Net before CBHI</th>
							<th rowspan="3">RSSB CBHI Scheme 0.5%</th>
							<th rowspan="3" class="col-yellow">Net Salary</th>
							<th rowspan="3" class="col-yellow">Net Salary</th>
							<th rowspan="3">MUGANGA SACCO SOCIAL FUND</th>
							<th rowspan="3">RPF</th>
							<th rowspan="3">BRD Scholar loan Repayment</th>
							<th rowspan="3">Sport Subscription reimbursement</th>
							<th colspan="2" class="hdr-insurance" rowspan="2">INSURANCE DEDUCTIONS</th>
							<th rowspan="3" class="col-yellow">Net paid</th>
							<th rowspan="3" class="col-yellow">Net paid</th>
							<th rowspan="3" class="col-green">Compulsory Saving</th>
							<th rowspan="3" class="col-green">Compulsory saving Account</th>
							<th rowspan="3" class="col-green">Take home</th>
							<th rowspan="3">Account Number</th>
							<th rowspan="3">Beneficiary Bank</th>
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
							<th class="hdr-insurance">Sanlam</th>
							<th class="hdr-insurance">Prime</th>
						</tr>
					</thead>
					<tbody>${rows_html}</tbody>
					<tfoot>${subtotal_html}${totals_html}</tfoot>
				</table>
				<div class="sheet-footer">
					<div class="sheet-date-line">${this.esc(footer.date_line || "")}</div>
					<div class="sheet-signatures">${signatures_html}</div>
				</div>
			</div>
		`);

	}

	build_sheet_chrome(data) {
		const logo_html = data.logo_url
			? `<div class="sheet-logo-wrap"><img class="sheet-logo" src="${frappe.utils.escape_html(
					data.logo_url
			  )}" alt="Company logo" /></div>`
			: `<div class="sheet-logo-placeholder">
					<div>${frappe.utils.escape_html(data.company_name || "")}</div>
					${
						data.logo_hint
							? `<div class="logo-hint">${frappe.utils.escape_html(data.logo_hint)}</div>`
							: ""
					}
			   </div>`;
		const footer = data.footer || {};
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
		const applied = data.filters_applied || {};
		const filter_hint_html =
			applied.payroll_month && applied.payroll_sheet_type
				? `<div class="sheet-filter-hint">${__(
						"Showing {0} · {1}",
						[applied.payroll_sheet_type, applied.payroll_month]
				  )}</div>`
				: "";
		return { logo_html, footer, signatures_html, filter_hint_html };
	}

	render_lumpsum_sheet(data) {
		const rows_html = data.rows.map((row) => this.render_lumpsum_data_row(row)).join("");
		const grand_label = data.grand_total_label || "GRAND TOTAL";
		let totals_html = this.render_lumpsum_total_row(data.totals, grand_label);
		const { logo_html, footer, signatures_html, filter_hint_html } = this.build_sheet_chrome(data);

		this.sheet_host.html(`
			<div class="sheet-wrap sheet-wrap-lumpsum">
				${filter_hint_html}
				<div class="sheet-brand-row">
					${logo_html}
					<div class="sheet-title">${frappe.utils.escape_html(data.title || "")}</div>
				</div>
				<table class="payroll-sheet payroll-sheet-lumpsum">
					<thead>
						<tr>
							<th rowspan="2">S/N</th>
							<th rowspan="2">ID NUMBER</th>
							<th rowspan="2">NAMES</th>
							<th rowspan="2">Date of Joining</th>
							<th rowspan="2">DEPARTMENT</th>
							<th rowspan="2">POSITION</th>
							<th rowspan="2">Gross Lumpsum</th>
							<th rowspan="2">PAYE(PAY AS YOU EARN)</th>
							<th colspan="2" class="hdr-rssb">RSSB CONTRIBUTIONS</th>
							<th rowspan="2" class="col-yellow">Net Salary</th>
							<th rowspan="2">Account Number</th>
							<th rowspan="2" class="col-green">Beneficiary Bank</th>
						</tr>
						<tr>
							<th class="hdr-rssb">Pension Employee 6%</th>
							<th class="hdr-rssb">Pension Employer 6%</th>
						</tr>
					</thead>
					<tbody>${rows_html}</tbody>
					<tfoot>${totals_html}</tfoot>
				</table>
				<div class="sheet-footer">
					<div class="sheet-date-line">${this.esc(footer.date_line || "")}</div>
					<div class="sheet-signatures">${signatures_html}</div>
				</div>
			</div>
		`);
	}

	render_variable_sheet(data) {
		const sheets = data.sheets?.length ? data.sheets : data.rows?.length ? [data] : [];
		if (!sheets.length) {
			const applied = data.filters_applied || {};
			this.sheet_host.html(
				`<div class="empty-state">${__(
					"No submitted payroll for {0} ({1}). Import Excel or choose another month.",
					[applied.payroll_month || "", applied.payroll_sheet_type || "Variable"]
				)}</div>`
			);
			return;
		}
		const { filter_hint_html } = this.build_sheet_chrome(data);
		const blocks = sheets.map((sheet) => this.variable_sheet_block(sheet)).join("");
		this.sheet_host.html(`
			${filter_hint_html}
			<div class="variable-sheet-stack">${blocks}</div>
		`);
	}

	variable_sheet_block(data) {
		const rows_html = data.rows.map((row) => this.render_variable_data_row(row)).join("");
		const grand_label = data.grand_total_label || "GRAND TOTAL";
		const totals_html = this.render_variable_total_row(data.totals, grand_label);
		const { logo_html, footer, signatures_html } = this.build_sheet_chrome(data);

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
					<tfoot>${totals_html}</tfoot>
				</table>
				<div class="sheet-footer">
					<div class="sheet-date-line">${this.esc(footer.date_line || "")}</div>
					<div class="sheet-signatures">${signatures_html}</div>
				</div>
			</div>
		`;
	}

	render_variable_data_row(row) {
		const take_home = flt(row.take_home) || flt(row.net_salary);
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
			<td class="num hdr-rssb">${this.fmt(row.pension_employee)}</td>
			<td class="num hdr-rssb">${this.fmt(row.pension_employer)}</td>
			<td class="num hdr-rssb">${this.fmt(row.oh_employer)}</td>
			<td class="num hdr-rssb">${this.fmt(row.maternity_employee)}</td>
			<td class="num hdr-rssb">${this.fmt(row.maternity_employer)}</td>
			<td class="num">${this.fmt(row.net_before_cbhi)}</td>
			<td class="num">${this.fmt(row.cbhi)}</td>
			<td class="num col-yellow">${this.fmt(take_home)}</td>
			<td>${this.esc(row.account_number)}</td>
			<td class="col-green">${this.esc(row.bank)}</td>
		</tr>`;
	}

	render_variable_total_row(totals, label) {
		totals = totals || {};
		const take_home = flt(totals.take_home) || flt(totals.net_salary);
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

	render_lumpsum_data_row(row) {
		return `<tr>
			<td>${row.sn}</td>
			<td>${this.esc(row.employee_id_number)}</td>
			<td>${this.esc(row.employee_name)}</td>
			<td>${this.esc(row.date_of_joining)}</td>
			<td>${this.esc(row.department)}</td>
			<td>${this.esc(row.position)}</td>
			<td class="num">${this.fmt(row.gross_salary)}</td>
			<td class="num">${this.fmt(row.paye)}</td>
			<td class="num hdr-rssb">${this.fmt(row.pension_employee)}</td>
			<td class="num hdr-rssb">${this.fmt(row.pension_employer)}</td>
			<td class="num col-yellow">${this.fmt(row.net_salary)}</td>
			<td>${this.esc(row.account_number)}</td>
			<td class="col-green">${this.esc(row.bank)}</td>
		</tr>`;
	}

	render_lumpsum_total_row(totals, label, is_variance) {
		totals = totals || {};
		const row_class = is_variance ? "grand-total variance-row" : "grand-total";
		return `<tr class="${row_class}">
			<td colspan="6">${this.esc(label || __("GRAND TOTAL"))}</td>
			<td class="num">${this.fmt(totals.gross_salary)}</td>
			<td class="num">${this.fmt(totals.paye)}</td>
			<td class="num">${this.fmt(totals.pension_employee)}</td>
			<td class="num">${this.fmt(totals.pension_employer)}</td>
			<td class="num col-yellow">${this.fmt(totals.net_salary)}</td>
			<td colspan="2"></td>
		</tr>`;
	}

	render_data_row(row) {
		return `<tr>
			<td>${row.sn}</td>
			<td>${this.esc(row.employee_id_number)}</td>
			<td>${this.esc(row.employee_name)}</td>
			<td>${this.esc(row.date_of_joining)}</td>
			<td>${this.esc(row.department)}</td>
			<td>${this.esc(row.position)}</td>
			${this.num_cells(row, [
				"basic_salary",
				"transport_allowance",
				"itc_allowance",
				"ict_allowance",
				"gross_salary",
				"paye",
				"pension_employee",
				"pension_employer",
				"oh_employer",
				"maternity_employee",
				"maternity_employer",
				"net_before_cbhi",
				"cbhi",
			])}
			<td class="num col-yellow">${this.fmt(row.net_salary)}</td>
			<td class="num col-yellow">${this.fmt(row.net_salary)}</td>
			${this.num_cells(row, [
				"muganga_sacco_social_fund",
				"rpf",
				"brd_loan",
				"sport_subscription",
				"insurance_sanlam",
				"insurance_prime",
			])}
			<td class="num col-yellow">${this.fmt(row.net_paid)}</td>
			<td class="num col-yellow">${this.fmt(row.net_paid)}</td>
			<td class="num col-green">${this.fmt(row.compulsory_saving)}</td>
			<td class="col-green">${this.esc(row.compulsory_saving_account)}</td>
			<td class="num col-green">${this.fmt(row.take_home)}</td>
			<td>${this.esc(row.account_number)}</td>
			<td>${this.esc(row.bank)}</td>
		</tr>`;
	}

	render_total_row(totals, label, is_variance) {
		totals = totals || {};
		const row_class = is_variance ? "grand-total variance-row" : "grand-total";
		return `<tr class="${row_class}">
			<td colspan="6">${this.esc(label || __("GRAND TOTAL"))}</td>
			${this.num_cells(totals, [
				"basic_salary",
				"transport_allowance",
				"itc_allowance",
				"ict_allowance",
				"gross_salary",
				"paye",
				"pension_employee",
				"pension_employer",
				"oh_employer",
				"maternity_employee",
				"maternity_employer",
				"net_before_cbhi",
				"cbhi",
			])}
			<td class="num col-yellow">${this.fmt(totals.net_salary)}</td>
			<td class="num col-yellow">${this.fmt(totals.net_salary)}</td>
			${this.num_cells(totals, [
				"muganga_sacco_social_fund",
				"rpf",
				"brd_loan",
				"sport_subscription",
				"insurance_sanlam",
				"insurance_prime",
			])}
			<td class="num col-yellow">${this.fmt(totals.net_paid)}</td>
			<td class="num col-yellow">${this.fmt(totals.net_paid)}</td>
			<td class="num col-green">${this.fmt(totals.compulsory_saving)}</td>
			<td></td>
			<td class="num col-green">${this.fmt(totals.take_home)}</td>
			<td colspan="2"></td>
		</tr>`;
	}

	payslip_dialog() {
		const period = this.split_payroll_month(this.get_payroll_month_value());
		const years = this.year_choices(period.year);
		const months = hrms.StaffPayrollDashboard.MONTHS.join("\n");
		frappe.prompt(
			[
				{
					fieldname: "employee_id_number",
					fieldtype: "Data",
					label: __("Employee ID Number"),
					reqd: 1,
				},
				{
					fieldname: "payroll_year",
					fieldtype: "Select",
					label: __("Year"),
					options: years,
					default: period.year,
					reqd: 1,
				},
				{
					fieldname: "payroll_month_name",
					fieldtype: "Select",
					label: __("Month"),
					options: months,
					default: period.month_name,
					reqd: 1,
				},
				{
					fieldname: "to_year",
					fieldtype: "Select",
					label: __("To year"),
					options: years,
					default: period.year,
					reqd: 1,
				},
				{
					fieldname: "to_month_name",
					fieldtype: "Select",
					label: __("To month"),
					options: months,
					default: period.month_name,
					reqd: 1,
				},
			],
			(values) => {
				const employee_id = (values.employee_id_number || "")
					.trim()
					.replace(/\s+/g, " ")
					.replace(/^(MSID)\s*(\d+)$/i, (_, p, n) => `${p.toUpperCase()} ${n}`);
				const from_month = this.compose_payroll_month(values.payroll_year, values.payroll_month_name);
				const to_month = this.compose_payroll_month(values.to_year, values.to_month_name);
				if (!from_month || !to_month) {
					frappe.msgprint(__("Year and Month are required."));
					return;
				}
				if (from_month > to_month) {
					frappe.msgprint(__("From month cannot be after To month."));
					return;
				}
				const params = new URLSearchParams({
					employee_id_number: employee_id,
					from_month,
					to_month,
				});
				window.location.href = frappe.urllib.get_full_url(
					`/api/method/hrms.payroll.doctype.imported_payroll_record.imported_payroll_record.download_payslip_docx?${params}`
				);
			},
			__("Download Payslip"),
			__("Download")
		);
	}

	num_cells(row, fields) {
		return fields.map((f) => `<td class="num">${this.fmt(row[f])}</td>`).join("");
	}

	fmt(val) {
		const n = flt(val);
		if (!n) {
			return "-";
		}
		return frappe.format(n, { fieldtype: "Float", precision: 0 });
	}

	esc(val) {
		return frappe.utils.escape_html(val == null ? "" : String(val));
	}
};

function flt(val) {
	return parseFloat(val) || 0;
}
