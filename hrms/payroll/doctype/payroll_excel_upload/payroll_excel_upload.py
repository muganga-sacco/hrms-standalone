# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from hrms.payroll.payroll_import.payroll_excel_parser import parse_payroll_excel
from hrms.payroll.payroll_import.payroll_sheet_layout import (
	save_payroll_sheet_logo_from_excel,
	sync_company_logo_from_payroll_excel,
	sync_payroll_sheet_layout_from_upload,
)


class PayrollExcelUpload(Document):
	pass


@frappe.whitelist()
def refresh_sheet_layout_from_excel(docname: str):
	"""Re-read logo and signature block from the attached Excel file."""
	if sync_payroll_sheet_layout_from_upload(docname):
		return {"ok": True}
	frappe.throw(_("Could not refresh sheet layout. Check that Payroll Excel File is attached."))


@frappe.whitelist()
def import_payroll_excel(docname: str):
	doc = frappe.get_doc("Payroll Excel Upload", docname)
	if not doc.payroll_file:
		frappe.throw(_("Please attach a Payroll Excel file first."))

	file_path = frappe.get_doc("File", {"file_url": doc.payroll_file}).get_full_path()

	try:
		parsed = parse_payroll_excel(file_path)
	except Exception:
		doc.status = "Failed"
		doc.import_log = frappe.get_traceback()
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		raise

	doc.payroll_period_label = parsed.get("payroll_period_label")
	doc.payroll_month = parsed.get("payroll_month")
	if parsed.get("sheet_footer"):
		doc.payroll_sheet_footer = parsed.get("sheet_footer")
	save_payroll_sheet_logo_from_excel(file_path, doc.name)
	if doc.company:
		sync_company_logo_from_payroll_excel(file_path, doc.company)
	log_lines = []
	col_map = parsed.get("column_map") or {}
	if col_map:
		log_lines.append(_("Column mapping: {0}").format(", ".join(f"{k}→{v}" for k, v in sorted(col_map.items()))))
	created = 0

	for row in parsed.get("records") or []:
		try:
			created += _upsert_payroll_record(doc, row)
			log_lines.append(_("Imported {0} ({1})").format(row.get("employee_name"), row.get("employee_id_number")))
		except Exception as e:
			log_lines.append(
				_("Failed {0}: {1}").format(row.get("employee_id_number") or row.get("employee_name"), str(e))
			)

	doc.imported_records = created
	doc.status = "Imported" if created else "Failed"
	doc.import_log = "\n".join(log_lines)
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"imported": created, "log": doc.import_log}


def _upsert_payroll_record(upload_doc, row: dict) -> int:
	employee_id = (row.get("employee_id_number") or "").strip()
	if not employee_id:
		frappe.throw(_("Missing employee ID"))

	payroll_month = row.get("payroll_month") or upload_doc.payroll_month
	if not payroll_month:
		frappe.throw(_("Could not detect payroll month from Excel."))

	name = frappe.db.exists(
		"Imported Payroll Record",
		{"employee_id_number": employee_id, "payroll_month": payroll_month},
	)

	if name:
		existing = frappe.get_doc("Imported Payroll Record", name)
		if existing.docstatus == 1:
			existing.cancel()
		frappe.delete_doc("Imported Payroll Record", name, force=1)

	record = frappe.new_doc("Imported Payroll Record")
	record.employee_id_number = employee_id

	record.update(
		{
			"employee_name": row.get("employee_name"),
			"date_of_joining": row.get("date_of_joining"),
			"position": row.get("position"),
			"payroll_period_label": row.get("payroll_period_label") or upload_doc.payroll_period_label,
			"payroll_month": payroll_month,
			"company": upload_doc.company,
			"currency": frappe.db.get_value("Company", upload_doc.company, "default_currency")
			if upload_doc.company
			else None,
			"payroll_excel_upload": upload_doc.name,
			"basic_salary": row.get("basic_salary"),
			"transport_allowance": row.get("transport_allowance"),
			"itc_allowance": row.get("itc_allowance"),
			"ict_allowance": row.get("ict_allowance"),
			"gross_salary": row.get("gross_salary"),
			"paye": row.get("paye"),
			"pension_employee": row.get("pension_employee"),
			"pension_employer": row.get("pension_employer"),
			"oh_employer": row.get("oh_employer"),
			"maternity_employee": row.get("maternity_employee"),
			"maternity_employer": row.get("maternity_employer"),
			"net_before_cbhi": row.get("net_before_cbhi"),
			"cbhi": row.get("cbhi"),
			"net_salary": row.get("net_salary"),
			"muganga_sacco_social_fund": row.get("muganga_sacco_social_fund"),
			"rpf": row.get("rpf"),
			"brd_loan": row.get("brd_loan"),
			"sport_subscription": row.get("sport_subscription"),
			"insurance_sanlam": row.get("insurance_sanlam"),
			"insurance_prime": row.get("insurance_prime"),
			"other_deductions": row.get("other_deductions"),
			"total_deductions": row.get("total_deductions"),
			"net_paid": row.get("net_paid"),
			"compulsory_saving": row.get("compulsory_saving"),
			"compulsory_saving_account": row.get("compulsory_saving_account"),
			"take_home": row.get("take_home"),
			"account_number": row.get("account_number"),
			"bank": row.get("bank"),
		}
	)

	employee = frappe.db.get_value("Employee", {"employee_number": employee_id}, "name")
	if not employee:
		employee = frappe.db.get_value("Employee", {"name": employee_id}, "name")
	if employee:
		record.employee = employee
		record.department = record.department or frappe.db.get_value("Employee", employee, "department")

	record.flags.ignore_permissions = True
	if record.docstatus == 1:
		record.cancel()
	record.save()
	if not record.currency and record.company:
		record.db_set(
			"currency",
			frappe.db.get_value("Company", record.company, "default_currency") or "RWF",
			update_modified=False,
		)
	record.submit()
	if not frappe.db.get_value("Imported Payroll Record", record.name, "currency"):
		frappe.db.set_value(
			"Imported Payroll Record",
			record.name,
			"currency",
			frappe.db.get_value("Company", record.company, "default_currency") or "RWF",
			update_modified=False,
		)
	return 1
