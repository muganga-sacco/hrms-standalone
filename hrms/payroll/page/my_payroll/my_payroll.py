# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Logged-in staff see only their own payroll and variable pay."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from hrms.payroll.payroll_import.payroll_access import get_logged_in_employee
from hrms.payroll.payroll_import.payroll_employee_link import payroll_id_variants
from hrms.payroll.payroll_import.payroll_month_utils import normalize_employee_id_number


@frappe.whitelist()
def get_my_payroll() -> dict:
	employee = get_logged_in_employee()
	if not employee:
		frappe.throw(_("Your user is not linked to an Employee record."))

	employee_name, employee_number = frappe.db.get_value(
		"Employee", employee, ["employee_name", "employee_number"]
	)
	employee_number = normalize_employee_id_number(employee_number)
	if not employee_number:
		frappe.throw(_("Ask HR to set your Employee Number before you can see your payroll."))

	rows = _own_rows(employee, employee_number)
	payroll = [row for row in rows if row["sheet_type"] == "Staff Payroll"]
	variables = [row for row in rows if row["sheet_type"] == "Variable"]
	lumpsum = [row for row in rows if row["sheet_type"] == "Lumpsum"]
	return {
		"employee": employee,
		"employee_name": employee_name,
		"employee_number": employee_number,
		"payroll": payroll,
		"variables": variables,
		"lumpsum": lumpsum,
	}


def _own_rows(employee: str, employee_number: str) -> list[dict]:
	id_variants = payroll_id_variants(employee_number) or [employee_number]
	records = frappe.get_all(
		"Imported Payroll Record",
		filters={"docstatus": 1},
		or_filters=[
			["employee", "=", employee],
			["employee_id_number", "in", id_variants],
		],
		fields=[
			"name",
			"employee",
			"employee_id_number",
			"payroll_sheet_type",
			"payroll_period_label",
			"payroll_month",
			"gross_salary",
			"net_salary",
			"take_home",
			"department",
			"position",
		],
		order_by="payroll_month desc, payroll_sheet_type asc",
		limit=200,
		ignore_permissions=True,
	)
	own = []
	for row in records:
		same_employee = row.employee == employee
		same_number = normalize_employee_id_number(row.employee_id_number) in set(id_variants)
		if not same_employee and not same_number:
			continue
		if row.employee and row.employee != employee and not same_number:
			continue
		own.append(
			{
				"sheet_type": row.payroll_sheet_type or "Staff Payroll",
				"label": row.payroll_period_label,
				"payroll_month": str(row.payroll_month or ""),
				"department": row.department,
				"position": row.position,
				"gross_salary": flt(row.gross_salary),
				"net_salary": flt(row.net_salary or row.take_home),
			}
		)
	return own
