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
		this.render_shell();
		this.make_filters();
		this.load_data();
	}

	render_shell() {
		this.wrapper.html(`
			<div class="staff-payroll-dashboard">
				<div class="toolbar-row">
					<div class="filter-company"></div>
					<div class="filter-month"></div>
					<div class="filter-actions">
						<button class="btn btn-primary btn-sm btn-refresh">${__("Refresh")}</button>
						<button class="btn btn-default btn-sm btn-export">${__("Export Excel")}</button>
						<button class="btn btn-default btn-sm btn-payslip-search">${__("Download Payslip")}</button>
					</div>
				</div>
				<div class="sheet-host"></div>
			</div>
		`);

		this.sheet_host = this.wrapper.find(".sheet-host");
		this.wrapper.find(".btn-refresh").on("click", () => this.load_data());
		this.wrapper.find(".btn-export").on("click", () => this.export_excel());
		this.wrapper.find(".btn-payslip-search").on("click", () => this.payslip_dialog());
	}

	make_filters() {
		this.company_field = frappe.ui.form.make_control({
			parent: this.wrapper.find(".filter-company")[0],
			df: {
				fieldtype: "Link",
				options: "Company",
				label: __("Company"),
				fieldname: "company",
				default: this.company,
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
	}

	get_filters() {
		return {
			company: this.company_field.get_value(),
			payroll_month: this.month_field.get_value(),
		};
	}

	load_data() {
		const filters = this.get_filters();
		if (!filters.payroll_month) {
			frappe.msgprint(__("Please select Payroll Month."));
			return;
		}
		frappe.call({
			method: "hrms.payroll.page.staff_payroll_dashboard.staff_payroll_dashboard.get_staff_payroll_dashboard",
			args: filters,
			freeze: true,
			callback: (r) => {
				this.render_sheet(r.message || {});
			},
		});
	}

	export_excel() {
		const filters = this.get_filters();
		if (!filters.payroll_month) {
			frappe.msgprint(__("Please select Payroll Month."));
			return;
		}
		const params = new URLSearchParams({ payroll_month: filters.payroll_month });
		if (filters.company) {
			params.set("company", filters.company);
		}
		window.open(
			`/api/method/hrms.payroll.doctype.imported_payroll_record.imported_payroll_record.download_payroll_month_excel?${params}`,
			"_blank"
		);
	}

	render_sheet(data) {
		if (!data.rows || !data.rows.length) {
			this.sheet_host.html(
				`<div class="empty-state">${__("No submitted payroll records for this month. Import Excel first.")}</div>`
			);
			return;
		}

		const rows_html = data.rows.map((row) => this.render_data_row(row)).join("");
		const subtotal_html =
			data.rows.length > 1 ? this.render_total_row(data.totals, "S/TOTAL1") : "";
		const grand_label = data.month_label
			? `GRAND TOTAL_${data.month_label}`
			: "GRAND TOTAL";
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
		const signatures = (footer.signatures || [])
			.filter((sig) => sig && (sig.name || sig.title || sig.heading))
			.map(
				(sig) => `<div class="signature-block">
				<div class="sig-heading">${this.esc(sig.heading)}</div>
				<div class="sig-name">${this.esc(sig.name)}</div>
				<div class="sig-title">${this.esc(sig.title)}</div>
			</div>`
			)
			.join("");

		this.sheet_host.html(`
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
					<div class="sheet-signatures">${signatures}</div>
				</div>
			</div>
		`);

	}

	render_data_row(row) {
		return `<tr>
			<td>${row.sn}</td>
			<td>${this.esc(row.employee_id_number)}</td>
			<td>${this.esc(row.employee_name)}</td>
			<td>${this.esc(row.date_of_joining)}</td>
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
			<td colspan="5">${this.esc(label || __("GRAND TOTAL"))}</td>
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
					depends_on: 'eval:doc.mode=="From month – To month"',
				},
				{
					fieldname: "to_month",
					fieldtype: "Date",
					label: __("To month"),
					depends_on: 'eval:doc.mode=="From month – To month"',
				},
			],
			(values) => {
				const params = new URLSearchParams({
					employee_id_number: values.employee_id_number,
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
				window.open(
					`/api/method/hrms.payroll.doctype.imported_payroll_record.imported_payroll_record.download_payslip_docx?${params}`,
					"_blank"
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
