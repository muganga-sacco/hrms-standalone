# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from hrms.payroll.payroll_import.payroll_access import throw_if_not_hr_payroll
from hrms.payroll.payroll_import.payroll_employee_link import (
	compact_payroll_id,
	find_employee_for_payroll_id,
	link_imported_payroll_to_employee,
	sql_compact_payroll_id,
)
from hrms.payroll.payroll_import.payroll_month_utils import normalize_employee_id_number


def _payslip_counts() -> dict[str, dict[str, int]]:
	rows = frappe.db.sql(
		f"""
		SELECT
			{sql_compact_payroll_id("employee_id_number")} AS compact_id,
			SUM(CASE WHEN payroll_sheet_type = 'Staff Payroll' THEN 1 ELSE 0 END) AS staff_count,
			SUM(CASE WHEN payroll_sheet_type = 'Lumpsum' THEN 1 ELSE 0 END) AS lumpsum_count
		FROM `tabImported Payroll Record`
		WHERE docstatus = 1
		GROUP BY compact_id
		""",
		as_dict=True,
	)
	return {
		row.compact_id: {
			"staff_count": int(row.staff_count or 0),
			"lumpsum_count": int(row.lumpsum_count or 0),
		}
		for row in rows
		if row.compact_id
	}


@frappe.whitelist()
def get_payroll_id_rows(include_inactive: int = 0) -> list[dict]:
	"""Employees plus the payroll-template ID HR maintains for Excel uploads."""
	throw_if_not_hr_payroll()
	filters = {} if cint(include_inactive) else {"status": "Active"}
	employees = frappe.get_all(
		"Employee",
		filters=filters,
		fields=[
			"name",
			"employee_name",
			"department",
			"status",
			"user_id",
			"employee_number",
			"company",
		],
		order_by="employee_name asc",
		limit=2000,
	)
	counts = _payslip_counts()
	rows = []
	for employee in employees:
		payroll_id = normalize_employee_id_number(employee.employee_number)
		matched = counts.get(compact_payroll_id(payroll_id), {})
		rows.append(
			{
				"employee": employee.name,
				"employee_name": employee.employee_name,
				"department": employee.department,
				"company": employee.company,
				"status": employee.status,
				"user_id": employee.user_id,
				"payroll_id": payroll_id,
				"staff_count": matched.get("staff_count", 0),
				"lumpsum_count": matched.get("lumpsum_count", 0),
			}
		)
	return rows


@frappe.whitelist()
def save_payroll_ids(rows) -> dict:
	"""Store payroll-template ID numbers and link already uploaded payslips."""
	throw_if_not_hr_payroll()
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	if not rows:
		frappe.throw(_("Nothing to save."))

	prepared: list[tuple[str, str]] = []
	seen_ids: dict[str, str] = {}
	for row in rows:
		employee = (row.get("employee") or "").strip()
		if not employee or not frappe.db.exists("Employee", employee):
			frappe.throw(_("Employee {0} was not found.").format(employee or _("(blank)")))
		payroll_id = normalize_employee_id_number(row.get("payroll_id"))
		compact = compact_payroll_id(payroll_id)
		if compact:
			if compact in seen_ids and seen_ids[compact] != employee:
				frappe.throw(
					_("Payroll ID {0} is entered for more than one employee.").format(payroll_id)
				)
			seen_ids[compact] = employee
			other = find_employee_for_payroll_id(payroll_id)
			if other and other != employee:
				other_name = frappe.db.get_value("Employee", other, "employee_name") or other
				frappe.throw(
					_("Payroll ID {0} is already used by {1} ({2}).").format(
						payroll_id, other_name, other
					)
				)
		prepared.append((employee, payroll_id))

	linked = 0
	for employee, payroll_id in prepared:
		frappe.db.set_value(
			"Employee",
			employee,
			"employee_number",
			payroll_id or None,
			update_modified=True,
		)
		if payroll_id:
			linked += link_imported_payroll_to_employee(employee, payroll_id)

	frappe.db.commit()
	return {"saved": len(prepared), "linked_records": linked}
