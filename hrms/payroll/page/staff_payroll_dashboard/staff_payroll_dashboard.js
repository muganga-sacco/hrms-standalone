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
			'<link id="staff-payroll-dashboard-css" rel="stylesheet" href="/assets/hrms/css/staff_payroll_dashboard.css">'
		).appendTo("head");
	}

	const dashboard = new hrms.StaffPayrollDashboard(page);
	dashboard.show();
};

hrms.StaffPayrollDashboard = class StaffPayrollDashboard {
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
			const month = this.read_payroll_month_from_field();
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
					"hrms.payroll.page.staff_payroll_dashboard.staff_payroll_dashboard.get_payroll_dashboard_companies",
			})
			.then((r) => {
				const companies = r.message || [];
				this.dashboard_companies = companies;
				const default_company =
					this.company && companies.includes(this.company)
						? this.company
						: companies[0] || this.company;
				this.company_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-company")[0],
					df: {
						fieldtype: companies.length > 1 ? "Select" : "Data",
						options: companies.join("\n"),
						label: __("Company"),
						fieldname: "company",
						default: default_company,
						read_only: companies.length <= 1 ? 1 : 0,
						onchange: () => this.schedule_filter_reload(),
					},
					render_input: true,
				});
				this.month_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-month")[0],
					df: {
						fieldtype: "Date",
						label: __("Payroll Month"),
						description: __(
							"Choose any day in the month, then click the day or press Refresh to load."
						),
						fieldname: "payroll_month",
						default: this.payroll_month,
					},
					render_input: true,
				});
				this._committed_payroll_month = this.normalize_payroll_month(this.payroll_month);
				this.sheet_type_field = frappe.ui.form.make_control({
					parent: this.wrapper.find(".filter-sheet-type")[0],
					df: {
						fieldtype: "Select",
						label: __("Sheet Type"),
						fieldname: "payroll_sheet_type",
						options: "Staff Payroll\nLumpsum\nAll",
						default: "Staff Payroll",
						onchange: () => this.schedule_filter_reload(),
					},
					render_input: true,
				});
				this.bind_month_field_reload();
			});
	}

	bind_month_field_reload() {
		const capture_from_picker = (selectedDates) => {
			if (selectedDates?.length) {
				this._committed_payroll_month = this.normalize_payroll_month(selectedDates[0]);
				this.schedule_filter_reload({ force: true });
			}
		};
		const capture_from_input = () => {
			const month = this.read_payroll_month_from_field();
			if (month) {
				this._committed_payroll_month = month;
				this.schedule_filter_reload({ force: true });
			}
		};
		const fp = this.month_field?.datepicker;
		if (fp) {
			const wrap = (handlers, fn) => {
				const prev = handlers;
				if (Array.isArray(prev)) {
					prev.push(fn);
					return prev;
				}
				return prev ? [prev, fn] : [fn];
			};
			fp.config.onChange = wrap(fp.config.onChange, capture_from_picker);
		}
		this.month_field?.$input?.on("change blur", capture_from_input);
	}

	read_payroll_month_from_field() {
		const fp = this.month_field?.datepicker;
		if (fp?.selectedDates?.length) {
			return this.normalize_payroll_month(fp.selectedDates[0]);
		}
		const raw =
			(this.month_field?.$input?.val() || "").trim() || this.month_field?.get_value();
		return this.normalize_payroll_month(raw);
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

	normalize_payroll_month(value) {
		if (!value) {
			return null;
		}
		if (value instanceof Date && !Number.isNaN(value.getTime())) {
			const y = value.getFullYear();
			const m = String(value.getMonth() + 1).padStart(2, "0");
			return `${y}-${m}-01`;
		}
		if (typeof frappe.datetime.month_start === "function") {
			const normalized = frappe.datetime.month_start(value);
			if (normalized) {
				return normalized;
			}
		}
		const d = frappe.datetime.str_to_obj(value);
		if (!d || Number.isNaN(d.getTime())) {
			return null;
		}
		const y = d.getFullYear();
		const m = String(d.getMonth() + 1).padStart(2, "0");
		return `${y}-${m}-01`;
	}

	get_payroll_month_value() {
		return (
			this._committed_payroll_month ||
			this.read_payroll_month_from_field() ||
			this.normalize_payroll_month(this.payroll_month)
		);
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
		let totals_html = this.render_total_row(data.totals, grand_label);
		if (data.prev_totals) {
			totals_html += this.render_total_row(
				data.prev_totals,
				`GRAND TOTAL_${data.prev_month_label || ""}`
			);
		}
		if (data.variance) {
			totals_html += this.render_total_row(data.variance, "Variance", true);
		}
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
		const payroll_month = this.month_field.get_value();
		frappe.prompt(
			[
				{
					fieldname: "employee_id_number",
					fieldtype: "Data",
					label: __("Employee ID Number"),
					reqd: 1,
				},
				{
					fieldname: "mode",
					fieldtype: "Select",
					label: __("Period"),
					options: [
						"Last N months",
						"Single payroll month",
						"From month – To month",
					].join("\n"),
					default: "Single payroll month",
					reqd: 1,
				},
				{
					fieldname: "months",
					fieldtype: "Int",
					label: __("Number of months"),
					default: 3,
					depends_on: 'eval:doc.mode=="Last N months"',
				},
				{
					fieldname: "payroll_month",
					fieldtype: "Date",
					label: __("Payroll month"),
					default: payroll_month,
					depends_on: 'eval:doc.mode=="Single payroll month"',
				},
				{
					fieldname: "from_month",
					fieldtype: "Date",
					label: __("From month"),
					default: payroll_month,
					depends_on: 'eval:doc.mode=="From month – To month"',
				},
				{
					fieldname: "to_month",
					fieldtype: "Date",
					label: __("To month"),
					default: payroll_month,
					depends_on: 'eval:doc.mode=="From month – To month"',
				},
			],
			(values) => {
				const employee_id = (values.employee_id_number || "")
					.trim()
					.replace(/\s+/g, " ")
					.replace(/^(MSID)\s*(\d+)$/i, (_, p, n) => `${p.toUpperCase()} ${n}`);
				const params = new URLSearchParams({
					employee_id_number: employee_id,
				});
				if (values.mode === "Last N months") {
					params.set("months", values.months || 3);
				} else if (values.mode === "Single payroll month") {
					if (!values.payroll_month) {
						frappe.msgprint(__("Payroll month is required."));
						return;
					}
					params.set("payroll_month", values.payroll_month);
				} else {
					if (!values.from_month || !values.to_month) {
						frappe.msgprint(__("From month and To month are required."));
						return;
					}
					params.set("from_month", values.from_month);
					params.set("to_month", values.to_month);
				}
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
