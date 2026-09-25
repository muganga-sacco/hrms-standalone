# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Desk permissions so HR / DAF / MD see Payroll workspace links and Staff Payroll Dashboard.

Run:
  bench --site mysite.local execute hrms.payroll.setup.ensure_payroll_dashboard_permissions.ensure_payroll_dashboard_permissions
"""

from __future__ import annotations

import frappe

PAYROLL_DASHBOARD_ROLES = ("HR Manager", "HR User", "DAF", "MD")
HR_PAYROLL_ROLES = ("HR Manager", "HR User")
VIEW_ONLY_ROLES = frozenset({"DAF", "MD"})
PAYSLIP_EMPLOYEE_ROLES = ("Employee",)
EMPLOYEE_MY_PAYSLIPS_DOCTYPES = ("Payslip Request", "Workspace", "Page", "Employee")
VIEWER_IMPORTED_PAYROLL_FLAGS = {
	"read": 1,
	"export": 1,
	"print": 1,
	"report": 1,
}

HR_IMPORT_DOCTYPES = ("Imported Payroll Record", "Payroll Excel Upload")
HR_IMPORT_PERM_FLAGS = (
	"create",
	"read",
	"write",
	"delete",
	"submit",
	"cancel",
	"export",
	"print",
	"report",
	"email",
	"share",
)

# Doctypes DAF/MD need read to show Payroll workspace links (not HR upload).
VIEWER_LINK_DOCTYPES = ("Page", "Workspace", "Report", "Company", "Imported Payroll Record", "Payslip Request")


def _ensure_custom_docperm_flags(doctype: str, role: str, flags: dict[str, int]) -> bool:
	"""Ensure Custom DocPerm row exists with the given permission flags (permlevel 0)."""
	existing = frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Custom DocPerm", existing)
		changed = False
		for key, val in flags.items():
			if int(doc.get(key) or 0) != val:
				doc.set(key, val)
				changed = True
		if changed:
			doc.save(ignore_permissions=True)
			return True
		return False

	payload = {
		"doctype": "Custom DocPerm",
		"parent": doctype,
		"parenttype": "DocType",
		"parentfield": "permissions",
		"role": role,
		"permlevel": 0,
	}
	payload.update(flags)
	frappe.get_doc(payload).insert(ignore_permissions=True)
	return True


def _ensure_hr_import_docperms() -> dict[str, list[str]]:
	flags = {key: 1 for key in HR_IMPORT_PERM_FLAGS}
	added: dict[str, list[str]] = {}
	for doctype in HR_IMPORT_DOCTYPES:
		for role in HR_PAYROLL_ROLES:
			if _ensure_custom_docperm_flags(doctype, role, flags):
				added.setdefault(doctype, []).append(role)
	return added


def _ensure_doctype_read(doctype: str, role: str) -> bool:
	if frappe.db.exists(
		"DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0, "read": 1},
	):
		return False
	if frappe.db.exists(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0, "read": 1},
	):
		return False

	frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			"read": 1,
		}
	).insert(ignore_permissions=True)
	return True


def _ensure_report_role(report: str, role: str) -> bool:
	if frappe.db.exists("Has Role", {"parent": report, "parenttype": "Report", "role": role}):
		return False
	frappe.get_doc(
		{
			"doctype": "Has Role",
			"parent": report,
			"parenttype": "Report",
			"parentfield": "roles",
			"role": role,
		}
	).insert(ignore_permissions=True)
	return True


def _ensure_workspace_role(workspace: str, role: str) -> bool:
	if frappe.db.exists("Has Role", {"parent": workspace, "parenttype": "Workspace", "role": role}):
		return False
	frappe.get_doc(
		{
			"doctype": "Has Role",
			"parent": workspace,
			"parenttype": "Workspace",
			"parentfield": "roles",
			"role": role,
		}
	).insert(ignore_permissions=True)
	return True


def _ensure_page_role(page: str, role: str) -> bool:
	if frappe.db.exists("Has Role", {"parent": page, "parenttype": "Page", "role": role}):
		return False
	frappe.get_doc(
		{
			"doctype": "Has Role",
			"parent": page,
			"parenttype": "Page",
			"parentfield": "roles",
			"role": role,
		}
	).insert(ignore_permissions=True)
	return True


@frappe.whitelist()
def ensure_payroll_dashboard_permissions() -> dict:
	doctype_read: dict[str, list[str]] = {}
	hr_import = _ensure_hr_import_docperms()
	report_roles: list[str] = []
	page_roles: list[str] = []

	for role in PAYROLL_DASHBOARD_ROLES:
		doctypes = VIEWER_LINK_DOCTYPES if role in VIEW_ONLY_ROLES else ("Company", "Page", "Workspace", "Report")
		for doctype in doctypes:
			if _ensure_doctype_read(doctype, role):
				doctype_read.setdefault(doctype, []).append(role)

	for role in PAYROLL_DASHBOARD_ROLES:
		if _ensure_page_role("staff-payroll-dashboard", role):
			page_roles.append(role)

	for role in VIEW_ONLY_ROLES:
		if _ensure_report_role("Imported Payroll Register", role):
			report_roles.append(role)
		if _ensure_custom_docperm_flags("Imported Payroll Record", role, VIEWER_IMPORTED_PAYROLL_FLAGS):
			doctype_read.setdefault("Imported Payroll Record", []).append(role)

	for role in PAYSLIP_EMPLOYEE_ROLES:
		for doctype in EMPLOYEE_MY_PAYSLIPS_DOCTYPES:
			if _ensure_doctype_read(doctype, role):
				doctype_read.setdefault(doctype, []).append(role)
		if _ensure_workspace_role("My Payslips", role):
			page_roles.append(f"My Payslips:{role}")

	for doctype in doctype_read:
		frappe.clear_cache(doctype=doctype)

	frappe.clear_cache()
	frappe.db.commit()
	return {
		"doctype_read_added": doctype_read,
		"hr_import_perms_updated": hr_import,
		"report_roles_added": report_roles,
		"page_roles_added": page_roles,
	}
