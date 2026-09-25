# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import frappe
from frappe import _

HR_PAYROLL_ROLES = frozenset({"HR Manager", "HR User"})
PAYROLL_DASHBOARD_VIEW_ROLES = frozenset({"DAF", "MD"})
PAYSLIP_SELF_REQUEST_ROLES = frozenset({"Employee", "DAF", "MD"})


def user_has_hr_payroll_access(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Guest":
		return False
	if user == "Administrator":
		return True
	return bool(HR_PAYROLL_ROLES & set(frappe.get_roles(user)))


def user_can_view_staff_payroll_dashboard(user: str | None = None) -> bool:
	if user_has_hr_payroll_access(user):
		return True
	user = user or frappe.session.user
	if user == "Guest":
		return False
	return bool(PAYROLL_DASHBOARD_VIEW_ROLES & set(frappe.get_roles(user)))


def throw_if_not_hr_payroll(message: str | None = None) -> None:
	if not user_has_hr_payroll_access():
		frappe.throw(
			message or _("Only HR staff can access payroll data."),
			frappe.PermissionError,
		)


def throw_if_not_payroll_dashboard_viewer(message: str | None = None) -> None:
	if not user_can_view_staff_payroll_dashboard():
		frappe.throw(
			message or _("You are not allowed to view the Staff Payroll Dashboard."),
			frappe.PermissionError,
		)


def get_logged_in_employee() -> str | None:
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


def user_can_request_own_payslip(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Guest":
		return False
	return bool(PAYSLIP_SELF_REQUEST_ROLES & set(frappe.get_roles(user)))
