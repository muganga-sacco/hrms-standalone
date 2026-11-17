# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""A payroll month is open for payslip requests only after DAF and MD approve the Excel."""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.utils import add_months, formatdate, getdate

from hrms.payroll.payroll_import.payroll_month_utils import (
	normalize_payroll_month,
	payroll_period_label_for_month,
)

ACTIVE_UPLOAD_STATUSES = (
	"Imported",
	"Pending DAF",
	"Pending MD",
	"Approved",
	"Rejected",
)


def throw_if_payslip_months_not_approved(doc) -> None:
	for month in months_covered_by_payslip_request(doc):
		throw_if_month_not_approved_for_payslips(month)


def months_covered_by_payslip_request(doc) -> list[date]:
	pt = (doc.period_type or "").strip()
	if pt == "Single payroll month" or (doc.payroll_month and pt not in ("From month – To month", "Last N months", "Last 3 months")):
		month = normalize_payroll_month(doc.payroll_month)
		return [month] if month else []
	if pt == "From month – To month" or (doc.from_month and doc.to_month and pt not in ("Last N months", "Last 3 months")):
		return _months_between(doc.from_month, doc.to_month)
	count = 3
	if pt in ("Last N months", "Last 3 months"):
		try:
			count = int(doc.months or 3)
		except (TypeError, ValueError):
			count = 3
	end = normalize_payroll_month(getdate())
	if not end:
		return []
	months = []
	for offset in range(count):
		month = normalize_payroll_month(add_months(end, -offset))
		if month:
			months.append(month)
	return months


def throw_if_month_not_approved_for_payslips(payroll_month) -> None:
	month = normalize_payroll_month(payroll_month)
	if not month:
		frappe.throw(_("Payroll month is required."))
	label = payroll_period_label_for_month(month) or formatdate(month, "MMMM yyyy")
	uploads = frappe.get_all(
		"Payroll Excel Upload",
		filters={"payroll_month": month, "status": ["in", list(ACTIVE_UPLOAD_STATUSES)]},
		fields=["name", "payroll_sheet_type", "status"],
		order_by="creation asc",
	)
	staff = [row for row in uploads if (row.payroll_sheet_type or "Staff Payroll") == "Staff Payroll"]
	not_ready = [row for row in uploads if row.status != "Approved"]
	if not uploads or not staff or not_ready:
		frappe.throw(_("Payslips for {0} are not available.").format(label))


def _months_between(start, end) -> list[date]:
	first = normalize_payroll_month(start)
	last = normalize_payroll_month(end)
	if not first or not last:
		return []
	if first > last:
		first, last = last, first
	months: list[date] = []
	current = first
	guard = 0
	while current <= last and guard < 36:
		months.append(current)
		current = normalize_payroll_month(add_months(current, 1))
		guard += 1
	return months
