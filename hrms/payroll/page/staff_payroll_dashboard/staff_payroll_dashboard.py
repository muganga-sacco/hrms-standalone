# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate

from hrms.payroll.payroll_import.payroll_sheet_layout import (
	ensure_payroll_sheet_layout,
	get_payroll_excel_upload_for_month,
	get_payroll_sheet_footer,
	get_payroll_sheet_header,
)

NUMERIC_FIELDS = [
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
	"net_salary",
	"muganga_sacco_social_fund",
	"rpf",
	"brd_loan",
	"sport_subscription",
	"insurance_sanlam",
	"insurance_prime",
	"net_paid",
	"compulsory_saving",
	"take_home",
]

ROW_FIELDS = [
	"employee_id_number",
	"employee_name",
	"date_of_joining",
	"position",
	*NUMERIC_FIELDS,
	"compulsory_saving_account",
	"account_number",
	"bank",
]


@frappe.whitelist()
def get_staff_payroll_dashboard(payroll_month: str, company: str | None = None):
	if not payroll_month:
		frappe.throw(_("Payroll Month is required."))

	if not frappe.has_permission("Imported Payroll Record", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	month = getdate(payroll_month)
	filters: dict = {"docstatus": 1, "payroll_month": month}
	if company:
		filters["company"] = company

	records = frappe.get_all(
		"Imported Payroll Record",
		filters=filters,
		fields=ROW_FIELDS + ["payroll_period_label", "currency", "payroll_excel_upload"],
		order_by="employee_id_number asc",
	)

	rows = []
	for idx, record in enumerate(records, start=1):
		row = {"sn": idx}
		for field in ROW_FIELDS:
			val = record.get(field)
			if field == "date_of_joining" and val:
				val = getdate(val).strftime("%d-%m-%Y")
			elif field in NUMERIC_FIELDS:
				val = flt(val)
			row[field] = val
		rows.append(row)

	totals = {field: 0.0 for field in NUMERIC_FIELDS}
	for record in records:
		for field in NUMERIC_FIELDS:
			totals[field] += flt(record.get(field))

	title_label = records[0].get("payroll_period_label") if records else month.strftime("%B %Y")
	currency = records[0].get("currency") if records else None
	if not currency and company:
		currency = frappe.db.get_value("Company", company, "default_currency")

	prev_month = getdate(add_months(month, -1))
	prev_filters = {**filters, "payroll_month": prev_month}
	prev_records = frappe.get_all(
		"Imported Payroll Record",
		filters=prev_filters,
		fields=NUMERIC_FIELDS,
	)
	prev_totals = {field: 0.0 for field in NUMERIC_FIELDS}
	for record in prev_records:
		for field in NUMERIC_FIELDS:
			prev_totals[field] += flt(record.get(field))
	variance = {field: totals[field] - prev_totals.get(field, 0) for field in NUMERIC_FIELDS}

	payroll_excel_upload = (
		records[0].get("payroll_excel_upload")
		if records
		else get_payroll_excel_upload_for_month(company, month)
	)
	ensure_payroll_sheet_layout(payroll_excel_upload)
	header = get_payroll_sheet_header(company, title_label, payroll_excel_upload)
	footer = get_payroll_sheet_footer(
		company, payroll_month=month, payroll_excel_upload=payroll_excel_upload
	)

	return {
		**header,
		"payroll_month": month.isoformat(),
		"month_label": month.strftime("%B").upper(),
		"prev_month_label": prev_month.strftime("%B").upper(),
		"currency": currency or "RWF",
		"rows": rows,
		"totals": totals,
		"prev_totals": prev_totals if prev_records else None,
		"variance": variance if prev_records else None,
		"count": len(rows),
		"footer": footer,
	}
