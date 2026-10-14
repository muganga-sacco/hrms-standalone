// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("hrms");

frappe.pages["my-payroll"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("My Payroll"),
		single_column: true,
	});
	new hrms.MyPayroll(page).show();
};

hrms.MyPayroll = class MyPayroll {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
	}

	show() {
		this.wrapper.html(`
			<style>
				.my-payroll { padding: 4px 0 24px; }
				.my-payroll .mp-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 16px; }
				.my-payroll h4 { margin: 16px 0 8px; }
				.my-payroll table { width: 100%; border-collapse: collapse; }
				.my-payroll th, .my-payroll td { border-bottom: 1px solid var(--border-color); padding: 8px; text-align: left; }
				.my-payroll .num { text-align: right; }
			</style>
			<div class="my-payroll">
				<div class="mp-head">
					<div class="mp-who text-muted"></div>
					<button class="btn btn-primary btn-sm btn-request">${__("Request Payslip")}</button>
				</div>
				<div class="mp-host"></div>
			</div>
		`);
		this.wrapper.find(".btn-request").on("click", () => {
			frappe.set_route("List", "Payslip Request");
		});
		frappe.call({
			method: "hrms.payroll.page.my_payroll.my_payroll.get_my_payroll",
			callback: (r) => this.render(r.message || {}),
		});
	}

	render(data) {
		this.wrapper
			.find(".mp-who")
			.text(`${data.employee_name || ""} · ${__("Employee Number")} ${data.employee_number || ""}`);
		const host = this.wrapper.find(".mp-host");
		host.empty();
		host.append(this.section(__("Payroll"), data.payroll || []));
		host.append(this.section(__("Bonuses and incentives"), data.variables || [], true));
		if ((data.lumpsum || []).length) {
			host.append(this.section(__("Lumpsum"), data.lumpsum));
		}
	}

	section(title, rows, show_type) {
		if (!rows.length) {
			return `<h4>${title}</h4><p class="text-muted">${__("Nothing uploaded for you yet.")}</p>`;
		}
		const body = rows
			.map((row) => {
				const type_cell = show_type
					? `<td>${frappe.utils.escape_html(row.label || "")}</td>`
					: "";
				return `<tr>
					${type_cell}
					<td>${frappe.utils.escape_html(row.label && !show_type ? row.label : row.payroll_month || "")}</td>
					<td>${frappe.utils.escape_html(row.department || "")}</td>
					<td class="num">${format_currency(row.gross_salary || 0)}</td>
					<td class="num">${format_currency(row.net_salary || 0)}</td>
				</tr>`;
			})
			.join("");
		const type_head = show_type ? `<th>${__("Type")}</th>` : "";
		return `
			<h4>${title}</h4>
			<table>
				<thead>
					<tr>
						${type_head}
						<th>${show_type ? __("Month") : __("Period")}</th>
						<th>${__("Department")}</th>
						<th class="num">${__("Gross")}</th>
						<th class="num">${__("Net")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`;
	}
};
