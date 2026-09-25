# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Create users for payslip request / payroll dashboard test scenarios.

Run:
  bench --site mysite.local execute hrms.payroll.setup.create_payroll_test_users.create_payroll_test_users
"""

from __future__ import annotations

import frappe
from frappe import _

DEFAULT_PASSWORD = "Test@2026"

# email, first_name, last_name, roles, employee_number (optional link to Employee.employee_number)
TEST_USERS = [
	{
		"email": "payroll.employee1@mysite.local",
		"first_name": "Payroll",
		"last_name": "Employee AB",
		"roles": ["Employee"],
		"employee_number": "MSID 001",
	},
	{
		"email": "payroll.employee2@mysite.local",
		"first_name": "Payroll",
		"last_name": "Employee BC",
		"roles": ["Employee"],
		"employee_number": "MSID 002",
	},
	{
		"email": "payroll.employee3@mysite.local",
		"first_name": "Payroll",
		"last_name": "Employee DE",
		"roles": ["Employee"],
		"employee_number": "MSID 003",
	},
	{
		"email": "payroll.hr@mysite.local",
		"first_name": "Payroll",
		"last_name": "HR Approver",
		"roles": ["HR Manager"],
	},
	{
		"email": "payroll.daf@mysite.local",
		"first_name": "Payroll",
		"last_name": "DAF Viewer",
		"roles": ["DAF"],
	},
	{
		"email": "payroll.md@mysite.local",
		"first_name": "Payroll",
		"last_name": "MD Viewer",
		"roles": ["MD"],
	},
]


def _ensure_role(role: str) -> None:
	if not frappe.db.exists("Role", role):
		frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def _ensure_user(entry: dict, password: str) -> str:
	email = entry["email"]
	roles = entry["roles"]
	for role in roles:
		_ensure_role(role)

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": entry["first_name"],
				"last_name": entry["last_name"],
				"send_welcome_email": 0,
				"enabled": 1,
				"user_type": "System User",
			}
		)
		user.insert(ignore_permissions=True)

	user.reload()
	desk_roles = list(dict.fromkeys([*roles, "Desk User"]))
	existing = {r.role for r in user.roles}
	roles_changed = False
	for role in desk_roles:
		if role not in existing:
			user.append("roles", {"role": role})
			roles_changed = True
	if roles_changed:
		user.save(ignore_permissions=True)

	user.flags.ignore_password_policy = True
	user.new_password = password
	user.save(ignore_permissions=True)

	return email


def _ensure_employee_for_payroll_id(employee_id_number: str, user_email: str) -> str | None:
	employee_id_number = (employee_id_number or "").strip()
	if not employee_id_number:
		return None

	employee = frappe.db.get_value("Employee", {"employee_number": employee_id_number}, "name")
	if not employee:
		employee = frappe.db.get_value("Employee", {"name": employee_id_number}, "name")

	if not employee:
		payroll_row = frappe.db.get_value(
			"Imported Payroll Record",
			{"employee_id_number": employee_id_number, "docstatus": 1},
			["employee_name", "company", "position"],
			as_dict=True,
			order_by="payroll_month desc",
		)
		if not payroll_row:
			return None
		company = payroll_row.company or frappe.db.get_single_value("Global Defaults", "default_company")
		payload = {
			"doctype": "Employee",
			"first_name": (payroll_row.employee_name or employee_id_number).split()[0][:140],
			"employee_name": payroll_row.employee_name or employee_id_number,
			"employee_number": employee_id_number,
			"company": company,
			"status": "Active",
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
		}
		position = (payroll_row.position or "").strip()
		if position and frappe.db.exists("Designation", position):
			payload["designation"] = position
		doc = frappe.get_doc(payload)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		employee = doc.name

	frappe.db.set_value("Employee", employee, "user_id", user_email, update_modified=False)
	return employee


@frappe.whitelist()
def create_payroll_test_users(password: str | None = None):
	"""Create test users and link employees. Returns summary (no password in response)."""
	password = password or DEFAULT_PASSWORD
	created = []
	links = []
	missing_employees = []

	for entry in TEST_USERS:
		email = _ensure_user(entry, password)
		created.append(email)
		emp_no = entry.get("employee_number")
		if emp_no:
			linked = _ensure_employee_for_payroll_id(emp_no, email)
			if linked:
				links.append(f"{emp_no} → {email}")
			else:
				missing_employees.append(emp_no)

	from hrms.payroll.setup.ensure_payroll_dashboard_permissions import (
		ensure_payroll_dashboard_permissions,
	)

	ensure_payroll_dashboard_permissions()

	frappe.db.commit()
	return {
		"users": created,
		"employee_links": links,
		"missing_employees": missing_employees,
		"default_password": password,
		"note": _("Each employee user can only create Payslip Requests for their own Employee record."),
	}
