# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from hrms.payroll.payroll_import.payroll_access import throw_if_not_hr_payroll
from hrms.payroll.payroll_import.payroll_month_utils import (
	normalize_employee_id_number,
	normalize_payroll_month,
)


class ImportedPayrollRecord(Document):
	def validate(self):
		if self.company and not self.currency:
			self.currency = frappe.db.get_value("Company", self.company, "default_currency")
		if not self.currency:
			self.currency = frappe.db.get_single_value("System Settings", "currency") or "RWF"


def _send_payslip_docx_response(
	employee_id_number: str,
	months: int | None = None,
	from_month: str | None = None,
	to_month: str | None = None,
	payroll_month: str | None = None,
):
	from hrms.payroll.payroll_import.payslip_docx import build_payslip_docx

	employee_id_number = normalize_employee_id_number(employee_id_number)
	try:
		content = build_payslip_docx(
			employee_id_number,
			months=int(months) if months else 3,
			from_month=from_month,
			to_month=to_month,
			payroll_month=payroll_month,
		)
	except Exception:
		frappe.log_error(title="Payslip download failed")
		raise
	suffix = employee_id_number.replace(" ", "_")
	if payroll_month:
		suffix += f"_{getdate(payroll_month).strftime('%Y-%m')}"
	elif from_month and to_month:
		suffix += f"_{getdate(from_month).strftime('%Y-%m')}_to_{getdate(to_month).strftime('%Y-%m')}"
	elif months:
		suffix += f"_{int(months)}m"

	frappe.local.response.filename = f"Payslip_{suffix}.docx"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"


@frappe.whitelist()
def download_payslip_docx(
	employee_id_number: str,
	months: int | None = None,
	from_month: str | None = None,
	to_month: str | None = None,
	payroll_month: str | None = None,
):
	"""Direct payslip download — HR only. Employees must use an approved Payslip Request."""
	throw_if_not_hr_payroll()

	_send_payslip_docx_response(
		employee_id_number,
		months=months,
		from_month=from_month,
		to_month=to_month,
		payroll_month=payroll_month,
	)


@frappe.whitelist()
def download_payroll_month_excel(
	payroll_month: str,
	company: str | None = None,
	payroll_sheet_type: str | None = "Staff Payroll",
):
	from hrms.payroll.payroll_import.payroll_month_export import build_payroll_month_excel

	throw_if_not_hr_payroll()
	if not frappe.has_permission("Imported Payroll Record", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	month = normalize_payroll_month(payroll_month)
	if not month:
		frappe.throw(_("Payroll Month is required."))

	sheet_type = payroll_sheet_type if payroll_sheet_type not in ("All", "", None) else "Staff Payroll"
	content = build_payroll_month_excel(month, company=company, payroll_sheet_type=sheet_type)
	label = month.strftime("%Y-%m")
	prefix = "Lumpsum_Payroll" if sheet_type == "Lumpsum" else "Staff_Payroll"
	frappe.local.response.filename = f"{prefix}_{label}.xlsx"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"
