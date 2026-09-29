# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from hrms.payroll.payroll_import.payroll_access import throw_if_not_hr_payroll
from hrms.payroll.payroll_import.payroll_excel_parser import parse_payroll_excel
from hrms.payroll.payroll_import.payroll_month_utils import (
	normalize_payroll_month,
	payroll_period_label_for_month,
)
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
	throw_if_not_hr_payroll()
	if sync_payroll_sheet_layout_from_upload(docname):
		return {"ok": True}
	frappe.throw(_("Could not refresh sheet layout. Check that Payroll Excel File is attached."))


@frappe.whitelist()
def import_payroll_excel(docname: str):
	throw_if_not_hr_payroll()
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

	detected_type = parsed.get("payroll_sheet_type") or "Staff Payroll"
	log_lines: list[str] = []
	if (doc.payroll_sheet_type or "Auto Detect") == "Auto Detect":
		doc.payroll_sheet_type = detected_type
	elif doc.payroll_sheet_type != detected_type:
		log_lines.append(
			_("Note: Excel looks like {0}; import uses selected type {1}.").format(
				detected_type, doc.payroll_sheet_type
			)
		)
	selected_month = normalize_payroll_month(doc.payroll_month)
	parsed_month = normalize_payroll_month(parsed.get("payroll_month"))
	if selected_month:
		doc.payroll_month = selected_month
		if parsed_month and parsed_month != selected_month:
			log_lines.append(
				_("Using selected payroll month {0} (Excel suggests {1}).").format(
					selected_month.isoformat(), parsed_month.isoformat()
				)
			)
	elif parsed_month:
		doc.payroll_month = parsed_month
	else:
		frappe.throw(
			_(
				"Please set Payroll Month on this form before importing, or add the month to the Excel title (e.g. September 2026)."
			)
		)

	if parsed.get("sheet_title"):
		doc.payroll_period_label = parsed.get("sheet_title")
	elif parsed.get("payroll_period_label"):
		doc.payroll_period_label = parsed.get("payroll_period_label")
	elif not doc.payroll_period_label:
		doc.payroll_period_label = payroll_period_label_for_month(doc.payroll_month)

	if parsed.get("sheet_footer"):
		doc.payroll_sheet_footer = parsed.get("sheet_footer")

	upload_sheet_type = doc.payroll_sheet_type
	upload_month = doc.payroll_month
	period_banner = doc.payroll_period_label
	upload_footer = doc.payroll_sheet_footer

	try:
		save_payroll_sheet_logo_from_excel(file_path, doc.name)
	except Exception:
		log_lines.append(_("Note: Sheet logo from Excel was not saved (see Error Log)."))
		frappe.log_error(title="Payroll import sheet logo")
	if doc.company:
		try:
			sync_company_logo_from_payroll_excel(file_path, doc.company)
		except Exception:
			log_lines.append(_("Note: Company logo from Excel was not saved (see Error Log)."))
			frappe.log_error(title="Payroll import company logo")
	doc.reload()
	doc.payroll_sheet_type = upload_sheet_type
	doc.payroll_month = upload_month
	doc.payroll_period_label = period_banner
	if upload_footer:
		doc.payroll_sheet_footer = upload_footer

	log_lines.append(_("Sheet type: {0}").format(doc.payroll_sheet_type))
	col_map = parsed.get("column_map") or {}
	if col_map:
		log_lines.append(_("Column mapping: {0}").format(", ".join(f"{k}→{v}" for k, v in sorted(col_map.items()))))
	unmapped = parsed.get("unmapped_headers") or []
	if unmapped:
		log_lines.append(
			_("Unmapped Excel columns (add a field on Imported Payroll Record to import them): {0}").format(
				", ".join(unmapped)
			)
		)
	created = 0

	for row in parsed.get("records") or []:
		if period_banner:
			row["payroll_period_label"] = period_banner
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
	doc.flags.ignore_permissions = True
	doc.flags.ignore_version = True
	doc.save()
	frappe.db.commit()

	return {"imported": created, "log": doc.import_log}


def _staff_payroll_row_for_lumpsum(record, employee_id: str, payroll_month) -> dict | None:
	filters = {
		"payroll_month": payroll_month,
		"payroll_sheet_type": "Staff Payroll",
		"docstatus": 1,
	}
	account = (getattr(record, "account_number", None) or "").strip()
	if account:
		filters["account_number"] = account
	else:
		filters["employee_id_number"] = employee_id
	return frappe.db.get_value(
		"Imported Payroll Record",
		filters,
		[
			"employee",
			"employee_id_number",
			"employee_name",
			"date_of_joining",
			"department",
			"position",
		],
		as_dict=True,
	)


def _backfill_lumpsum_from_staff_payroll(record, employee_id: str, payroll_month, sheet_type: str) -> None:
	if sheet_type != "Lumpsum" or not payroll_month:
		return
	staff = _staff_payroll_row_for_lumpsum(record, employee_id, payroll_month)
	if not staff:
		return
	if staff.employee:
		record.employee = staff.employee
	if staff.employee_id_number and not record.employee_id_number:
		record.employee_id_number = staff.employee_id_number
	if not record.date_of_joining and staff.date_of_joining:
		record.date_of_joining = staff.date_of_joining
	if staff.department:
		record.department = staff.department
	if staff.position and not record.position:
		record.position = staff.position


def _upsert_payroll_record(upload_doc, row: dict) -> int:
	employee_id = (row.get("employee_id_number") or "").strip()
	if not employee_id:
		frappe.throw(_("Missing employee ID"))

	payroll_month = normalize_payroll_month(row.get("payroll_month") or upload_doc.payroll_month)
	if not payroll_month:
		frappe.throw(_("Payroll Month is required on the upload or in the Excel title."))

	sheet_type = upload_doc.payroll_sheet_type or "Staff Payroll"
	name = frappe.db.exists(
		"Imported Payroll Record",
		{
			"employee_id_number": employee_id,
			"payroll_month": payroll_month,
			"payroll_sheet_type": sheet_type,
		},
	)

	if name:
		existing = frappe.get_doc("Imported Payroll Record", name)
		if existing.docstatus == 1:
			existing.flags.ignore_permissions = True
			existing.cancel()
		frappe.delete_doc("Imported Payroll Record", name, force=1, ignore_permissions=True)

	record = frappe.new_doc("Imported Payroll Record")
	record.employee_id_number = employee_id

	record.update(
		{
			"employee_name": row.get("employee_name"),
			"date_of_joining": row.get("date_of_joining"),
			"position": row.get("position"),
			"department": row.get("department"),
			"payroll_sheet_type": sheet_type,
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

	_backfill_lumpsum_from_staff_payroll(record, employee_id, payroll_month, sheet_type)

	if record.docstatus == 1:
		record.flags.ignore_permissions = True
		record.cancel()
	record.save(ignore_permissions=True)
	if not record.currency and record.company:
		record.db_set(
			"currency",
			frappe.db.get_value("Company", record.company, "default_currency") or "RWF",
			update_modified=False,
		)
	record.flags.ignore_permissions = True
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
