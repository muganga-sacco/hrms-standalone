# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""HR dashboard for variable pay: bonuses and incentives uploaded from Excel."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from hrms.payroll.payroll_import.payroll_access import throw_if_not_hr_payroll
from hrms.payroll.payroll_import.payroll_month_utils import normalize_payroll_month


def _variable_filters(
	variable_type: str | None = None,
	payroll_month: str | None = None,
	company: str | None = None,
) -> dict:
	filters: dict = {"docstatus": 1, "payroll_sheet_type": "Variable"}
	month = normalize_payroll_month(payroll_month) if payroll_month else None
	if month:
		filters["payroll_month"] = month
	if company:
		filters["company"] = company
	if variable_type:
		filters["payroll_period_label"] = variable_type
	return filters


def _delete_imported_record(name: str) -> None:
	doc = frappe.get_doc("Imported Payroll Record", name)
	if doc.payroll_sheet_type != "Variable":
		frappe.throw(_("This is not a variable pay record."))
	if doc.docstatus == 1:
		doc.flags.ignore_permissions = True
		doc.cancel()
	frappe.delete_doc("Imported Payroll Record", name, force=1, ignore_permissions=True)


@frappe.whitelist()
def get_variable_dashboard(
	variable_type: str | None = None,
	payroll_month: str | None = None,
	company: str | None = None,
) -> dict:
	throw_if_not_hr_payroll()
	filters = _variable_filters(variable_type, payroll_month, company)

	rows = frappe.get_all(
		"Imported Payroll Record",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_id_number",
			"employee_name",
			"date_of_joining",
			"department",
			"position",
			"payroll_period_label",
			"payroll_month",
			"basic_salary",
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
			"take_home",
			"account_number",
			"bank",
			"company",
		],
		order_by="payroll_period_label asc, employee_name asc",
		limit=2000,
	)
	types = frappe.get_all(
		"Imported Payroll Record",
		filters={"docstatus": 1, "payroll_sheet_type": "Variable"},
		fields=["payroll_period_label"],
		distinct=True,
		order_by="payroll_period_label asc",
	)
	return {
		"types": [row.payroll_period_label for row in types if row.payroll_period_label],
		"rows": [_variable_row(row) for row in rows],
	}


def _money(value) -> float:
	return flt(value)


def _variable_row(row) -> dict:
	take_home = _money(row.take_home) or _money(row.net_salary)
	if not take_home and row.net_before_cbhi:
		take_home = _money(row.net_before_cbhi) - _money(row.cbhi)
	return {
		"name": row.name,
		"employee": row.employee,
		"employee_number": row.employee_id_number,
		"employee_name": row.employee_name,
		"date_of_joining": str(row.date_of_joining or ""),
		"department": row.department,
		"position": row.position,
		"variable_type": row.payroll_period_label,
		"payroll_month": str(row.payroll_month or ""),
		"basic_salary": _money(row.basic_salary),
		"gross_salary": _money(row.gross_salary),
		"paye": _money(row.paye),
		"pension_employee": _money(row.pension_employee),
		"pension_employer": _money(row.pension_employer),
		"oh_employer": _money(row.oh_employer),
		"maternity_employee": _money(row.maternity_employee),
		"maternity_employer": _money(row.maternity_employer),
		"net_before_cbhi": _money(row.net_before_cbhi),
		"cbhi": _money(row.cbhi),
		"net_take_home": take_home,
		"account_number": row.account_number,
		"bank": row.bank,
		"company": row.company,
	}


@frappe.whitelist()
def upload_variable_excel(file_url: str, payroll_month: str, company: str | None = None) -> dict:
	"""Create a Variable payroll upload from an Excel file and import it."""
	throw_if_not_hr_payroll()
	if not file_url:
		frappe.throw(_("Attach the bonus or incentive Excel file."))
	month = normalize_payroll_month(payroll_month)
	if not month:
		frappe.throw(_("Payroll Month is required."))
	company = company or frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		frappe.throw(_("Company is required."))

	upload = frappe.get_doc(
		{
			"doctype": "Payroll Excel Upload",
			"company": company,
			"payroll_sheet_type": "Variable",
			"payroll_month": month,
			"payroll_file": file_url,
		}
	)
	upload.insert(ignore_permissions=True)
	from hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload import import_payroll_excel

	result = import_payroll_excel(upload.name)
	upload.reload()
	return {
		"upload": upload.name,
		"imported": result.get("imported") if isinstance(result, dict) else 0,
		"variable_type": upload.payroll_period_label,
		"payroll_month": str(getdate(upload.payroll_month)),
		"log": upload.import_log,
	}


@frappe.whitelist()
def download_variable_excel(
	payroll_month: str,
	company: str | None = None,
	variable_type: str | None = None,
):
	"""Download variable pay in the shared Excel template."""
	from hrms.payroll.payroll_import.payroll_month_export import build_variable_month_excel

	throw_if_not_hr_payroll()
	month = normalize_payroll_month(payroll_month)
	if not month:
		frappe.throw(_("Payroll Month is required."))
	content = build_variable_month_excel(month, company=company, variable_type=variable_type or None)
	frappe.local.response.filename = f"Variable_Pay_{month.strftime('%Y-%m')}.xlsx"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"


@frappe.whitelist()
def delete_variable_record(name: str) -> dict:
	"""Cancel and delete one variable pay row."""
	throw_if_not_hr_payroll()
	if not name:
		frappe.throw(_("Choose a row to delete."))
	if not frappe.has_permission("Imported Payroll Record", "delete"):
		frappe.throw(_("Not permitted to delete payroll records."), frappe.PermissionError)
	_delete_imported_record(name)
	frappe.db.commit()
	return {"deleted": 1, "message": _("Variable pay row deleted.")}


@frappe.whitelist()
def delete_variable_for_filters(
	payroll_month: str,
	company: str | None = None,
	variable_type: str | None = None,
) -> dict:
	"""Cancel and delete submitted variable pay rows for the dashboard filters."""
	throw_if_not_hr_payroll()
	if not payroll_month:
		frappe.throw(_("Payroll Month is required."))
	if not frappe.has_permission("Imported Payroll Record", "delete"):
		frappe.throw(_("Not permitted to delete payroll records."), frappe.PermissionError)

	filters = _variable_filters(variable_type, payroll_month, company)
	if "payroll_month" not in filters:
		frappe.throw(_("Payroll Month is required."))
	names = frappe.get_all("Imported Payroll Record", filters=filters, pluck="name", limit_page_length=0)
	if not names:
		return {"deleted": 0, "message": _("No variable pay records matched these filters.")}

	for name in names:
		_delete_imported_record(name)
	frappe.db.commit()
	return {
		"deleted": len(names),
		"message": _("Deleted {0} variable pay record(s).").format(len(names)),
	}
