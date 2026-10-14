# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Desk permissions so HR / DAF / MD see Payroll workspace links and Staff Payroll Dashboard.

Run:
  bench --site mysite.local execute hrms.payroll.setup.ensure_payroll_dashboard_permissions.ensure_payroll_dashboard_permissions
"""

from __future__ import annotations

import json

import frappe

PAYROLL_DASHBOARD_ROLES = ("HR Manager", "HR User", "DAF", "MD")
HR_PAYROLL_ROLES = ("HR Manager", "HR User")
VIEW_ONLY_ROLES = frozenset({"DAF", "MD"})
PAYSLIP_REQUEST_ALL_FLAGS = {
	"read": 1,
	"create": 1,
	"write": 1,
	"print": 1,
	"email": 1,
	"export": 1,
	"report": 1,
	"share": 1,
}
PAYSLIP_SELF_SERVICE_DOCTYPES = ("Workspace", "Page", "Employee")
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


def _payslip_self_service_roles() -> list[str]:
	"""Every enabled Role except Guest — no whitelist (Requester, *Employee*, etc. all included)."""
	return frappe.get_all(
		"Role",
		filters={"disabled": 0, "name": ["not in", ["Guest"]]},
		pluck="name",
		order_by="name",
	)


def _ensure_payslip_self_service_for_all_roles() -> dict[str, list[str]]:
	"""Grant Payslip Request + My Payslips workspace to every role on the site."""
	payslip_roles: list[str] = []
	workspace_roles: list[str] = []
	employee_read_roles: list[str] = []
	for role in _payslip_self_service_roles():
		if _ensure_custom_docperm_flags("Payslip Request", role, PAYSLIP_REQUEST_ALL_FLAGS):
			payslip_roles.append(role)
		for doctype in PAYSLIP_SELF_SERVICE_DOCTYPES:
			if _ensure_doctype_read(doctype, role):
				employee_read_roles.append(f"{doctype}:{role}")
		if _ensure_workspace_role("My Payslips", role):
			workspace_roles.append(role)
	return {
		"payslip_request_custom_docperm_added": payslip_roles,
		"self_service_doctype_read_added": employee_read_roles,
		"my_payslips_workspace_roles_added": workspace_roles,
	}


def _ensure_variable_and_my_payroll_pages() -> None:
	from pathlib import Path

	from frappe.modules.import_file import import_file_by_path

	base = Path(frappe.get_app_path("hrms")) / "payroll" / "page"
	for folder in ("variable_dashboard", "my_payroll"):
		path = base / folder / f"{folder}.json"
		if path.exists():
			import_file_by_path(str(path), force=True)

	for role in ("HR Manager", "HR User"):
		_ensure_page_role("variable-dashboard", role)
	for role in _payslip_self_service_roles():
		_ensure_page_role("my-payroll", role)
	_ensure_workspace_page_link("My Payslips", "My Payroll", "my-payroll")
	_place_variable_dashboard_in_payroll()


def _place_variable_dashboard_in_payroll() -> None:
	"""Show Variable Dashboard under Payroll & payslips, not Settings."""
	if not frappe.db.exists("Workspace", "Payroll"):
		return
	_ensure_workspace_page_link("Payroll", "Variable Dashboard", "variable-dashboard")
	workspace = frappe.get_doc("Workspace", "Payroll")
	content = frappe.parse_json(workspace.content) or []
	changed = False
	for block in content:
		if block.get("type") != "header":
			continue
		text = (block.get("data") or {}).get("text") or ""
		if "Imported payroll" in text:
			block["data"]["text"] = text.replace("Imported payroll &amp; payslips", "Payroll &amp; payslips").replace(
				"Imported payroll & payslips", "Payroll & payslips"
			)
			changed = True
	if changed:
		workspace.content = json.dumps(content)
		workspace.db_update()

	payslip_idx = frappe.db.get_value(
		"Workspace Link",
		{"parent": "Payroll", "label": "Payslip workflow", "type": "Card Break"},
		"idx",
	)
	link_name = frappe.db.get_value(
		"Workspace Link",
		{"parent": "Payroll", "link_to": "variable-dashboard"},
		"name",
	)
	if not payslip_idx or not link_name:
		return
	current_idx = frappe.db.get_value("Workspace Link", link_name, "idx")
	if current_idx and current_idx < payslip_idx:
		return
	frappe.db.sql(
		"""
		UPDATE `tabWorkspace Link`
		SET idx = idx + 1
		WHERE parent = 'Payroll' AND idx >= %s AND name != %s
		""",
		(payslip_idx, link_name),
	)
	frappe.db.set_value("Workspace Link", link_name, "idx", payslip_idx, update_modified=False)


def _ensure_workspace_page_link(workspace: str, label: str, page: str) -> None:
	if not frappe.db.exists("Workspace", workspace):
		return
	_insert_workspace_child(
		"Workspace Link",
		workspace,
		"links",
		{"type": "Link", "label": label, "link_type": "Page", "link_to": page, "link_count": 0},
		page,
	)
	_insert_workspace_child(
		"Workspace Shortcut",
		workspace,
		"shortcuts",
		{"type": "Page", "label": label, "link_to": page},
		page,
	)


def _insert_workspace_child(doctype: str, workspace: str, parentfield: str, values: dict, page: str) -> None:
	if frappe.db.exists(doctype, {"parent": workspace, "link_to": page}):
		return
	idx = frappe.db.sql(
		f"SELECT COALESCE(MAX(idx), 0) + 1 FROM `tab{doctype}` WHERE parent=%s",
		workspace,
	)[0][0]
	doc = frappe.get_doc({"doctype": doctype, "parent": workspace, "parenttype": "Workspace", "parentfield": parentfield, "idx": idx, **values})
	doc.db_insert()


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

	payslip_self_service = _ensure_payslip_self_service_for_all_roles()
	_ensure_variable_and_my_payroll_pages()

	for doctype in doctype_read:
		frappe.clear_cache(doctype=doctype)

	frappe.clear_cache()
	frappe.db.commit()
	return {
		"doctype_read_added": doctype_read,
		"hr_import_perms_updated": hr_import,
		"report_roles_added": report_roles,
		"page_roles_added": page_roles,
		"payslip_self_service": payslip_self_service,
	}
