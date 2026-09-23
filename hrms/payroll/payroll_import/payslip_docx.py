# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import io
import os
from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate


def get_template_path() -> str:
	return frappe.get_app_path("hrms", "payroll", "templates", "payslip_template.docx")


def _clear_paragraph_runs(paragraph) -> None:
	for run in list(paragraph.runs):
		run._element.getparent().remove(run._element)


def _remove_drawings(element) -> None:
	from docx.oxml.ns import qn

	drawing_tag = qn("w:drawing")
	for drawing in list(element.iter(drawing_tag)):
		parent = drawing.getparent()
		if parent is not None:
			parent.remove(drawing)


def _clear_template_logos(doc) -> None:
	"""Template ships logos in the section header (often duplicated) and sometimes the body."""
	for section in doc.sections:
		for paragraph in section.header.paragraphs:
			_clear_paragraph_runs(paragraph)
			_remove_drawings(paragraph._element)
		_remove_drawings(section.header._element)
		for paragraph in section.footer.paragraphs:
			_clear_paragraph_runs(paragraph)
			_remove_drawings(paragraph._element)

	for paragraph in doc.paragraphs:
		text = (paragraph.text or "").strip().upper()
		if "PAYSLIP" in text or text.startswith("EMPLOYEE") or text.startswith("POSITION"):
			break
		_clear_paragraph_runs(paragraph)
		_remove_drawings(paragraph._element)


def _inject_payslip_logo(doc, record: dict) -> None:
	from hrms.payroll.payroll_import.payroll_sheet_layout import (
		get_company_logo_path,
		get_payroll_excel_upload_for_month,
	)

	company = record.get("company")
	payroll_excel_upload = record.get("payroll_excel_upload") or get_payroll_excel_upload_for_month(
		company, record.get("payroll_month")
	)
	logo_path = get_company_logo_path(company, payroll_excel_upload)
	try:
		from docx.shared import Inches

		_clear_template_logos(doc)
		if not logo_path:
			return
		paragraph = doc.paragraphs[0] if doc.paragraphs else doc.add_paragraph()
		_clear_paragraph_runs(paragraph)
		_remove_drawings(paragraph._element)
		run = paragraph.add_run()
		run.add_picture(logo_path, height=Inches(0.85))
	except Exception:
		frappe.log_error(title="Payslip logo")


PAYSLIP_FIELDS = [
	"name",
	"company",
	"payroll_excel_upload",
	"employee_name",
	"position",
	"department",
	"payroll_period_label",
	"payroll_month",
	"payment_date",
	"basic_salary",
	"ict_allowance",
	"itc_allowance",
	"gross_salary",
	"paye",
	"pension_employee",
	"maternity_employee",
	"maternity_employer",
	"cbhi",
	"other_deductions",
	"total_deductions",
	"net_salary",
	"take_home",
]

MAX_PAYSLIP_MONTHS = 24


def get_payroll_records_for_payslip(
	employee_id_number: str,
	months: int | None = None,
	from_month: str | None = None,
	to_month: str | None = None,
	payroll_month: str | None = None,
) -> list[dict]:
	employee_id_number = (employee_id_number or "").strip()
	filters: dict = {"employee_id_number": employee_id_number, "docstatus": 1}
	limit = None

	if payroll_month:
		filters["payroll_month"] = getdate(payroll_month)
	elif from_month and to_month:
		filters["payroll_month"] = ["between", [getdate(from_month), getdate(to_month)]]
	elif from_month:
		filters["payroll_month"] = [">=", getdate(from_month)]
	elif to_month:
		filters["payroll_month"] = ["<=", getdate(to_month)]
	else:
		limit = min(int(months or 3), MAX_PAYSLIP_MONTHS)

	records = frappe.get_all(
		"Imported Payroll Record",
		filters=filters,
		fields=PAYSLIP_FIELDS,
		order_by="payroll_month desc, modified desc",
		limit=limit,
	)
	return _dedupe_by_payroll_month(records)


def _dedupe_by_payroll_month(records: list[dict]) -> list[dict]:
	seen: set[str] = set()
	deduped: list[dict] = []
	for record in records:
		month = record.get("payroll_month")
		if not month:
			deduped.append(record)
			continue
		key = getdate(month).isoformat()
		if key in seen:
			continue
		seen.add(key)
		deduped.append(record)
	return deduped


def get_last_n_payroll_records(employee_id_number: str, months: int = 3) -> list[dict]:
	return get_payroll_records_for_payslip(employee_id_number, months=months)


def build_payslip_docx(
	employee_id_number: str,
	months: int = 3,
	from_month: str | None = None,
	to_month: str | None = None,
	payroll_month: str | None = None,
) -> bytes:
	try:
		from docx import Document
	except ImportError as e:
		frappe.throw(_("python-docx is required. Install: pip install python-docx"))

	records = get_payroll_records_for_payslip(
		employee_id_number,
		months=months,
		from_month=from_month,
		to_month=to_month,
		payroll_month=payroll_month,
	)
	if not records:
		frappe.throw(_("No submitted payroll records found for employee ID {0}.").format(employee_id_number))

	if payroll_month or (from_month and to_month) or from_month or to_month:
		display_rows = len(records)
	else:
		display_rows = min(int(months or 3), MAX_PAYSLIP_MONTHS)
	records = records[:display_rows]

	template_path = get_template_path()
	if not os.path.exists(template_path):
		frappe.throw(_("Payslip template not found at {0}").format(template_path))

	doc = Document(template_path)
	latest = records[0]

	_inject_payslip_logo(doc, latest)

	for paragraph in doc.paragraphs:
		text = paragraph.text or ""
		if text.startswith("EMPLOYEE NAMES:"):
			paragraph.text = f"EMPLOYEE NAMES: {latest.get('employee_name') or ''}"
		elif text.startswith("POSITION:"):
			paragraph.text = f"POSITION: {latest.get('position') or ''}"
		elif text.startswith("DEPARTMENT:"):
			paragraph.text = f"DEPARTMENT: {latest.get('department') or ''}"

	if not doc.tables:
		frappe.throw(_("Payslip template must contain a payroll table."))

	table = doc.tables[0]
	first_data_row = 2

	while len(table.rows) < first_data_row + display_rows:
		table.add_row()

	for row_idx in range(first_data_row, len(table.rows)):
		for cell in table.rows[row_idx].cells:
			cell.text = "-"

	for idx, record in enumerate(records):
		row = table.rows[first_data_row + idx]
		values = _record_to_table_row(record)
		for col_idx, value in enumerate(values):
			if col_idx < len(row.cells):
				row.cells[col_idx].text = value

	buffer = io.BytesIO()
	doc.save(buffer)
	buffer.seek(0)
	return buffer.getvalue()


def _record_to_table_row(record: dict) -> list[str]:
	pay_period = record.get("payroll_period_label") or ""
	payment_date = record.get("payment_date")
	if payment_date:
		payment_date = getdate(payment_date).strftime("%d-%m-%Y")
	elif record.get("payroll_month"):
		payment_date = _default_payment_date(record.get("payroll_month"))
	else:
		payment_date = "-"

	lumpsum = _flt(record.get("itc_allowance"))
	maternity = _flt(record.get("maternity_employee")) + _flt(record.get("maternity_employer"))
	total_deductions = record.get("total_deductions")
	if not total_deductions:
		total_deductions = _flt(record.get("gross_salary")) - _flt(record.get("net_salary"))

	net = record.get("take_home") or record.get("net_salary")

	return [
		pay_period,
		payment_date,
		_fmt(record.get("basic_salary")),
		_fmt(record.get("ict_allowance")),
		_fmt(lumpsum) if lumpsum else "-",
		_fmt(record.get("gross_salary")),
		_fmt(record.get("paye")),
		_fmt(record.get("pension_employee")),
		_fmt(maternity / 2) if maternity else "-",
		_fmt(maternity / 2) if maternity else "-",
		_fmt(record.get("cbhi")),
		_fmt(record.get("other_deductions")),
		_fmt(total_deductions),
		_fmt(net),
	]


def _default_payment_date(payroll_month) -> str:
	d = getdate(payroll_month)
	# Typical pay date: 25th of same month
	pay_day = date(d.year, d.month, min(25, _days_in_month(d.year, d.month)))
	return pay_day.strftime("%d-%m-%Y")


def _days_in_month(year: int, month: int) -> int:
	if month == 12:
		next_month = date(year + 1, 1, 1)
	else:
		next_month = date(year, month + 1, 1)
	return (next_month - date(year, month, 1)).days


def _fmt(val) -> str:
	val = _flt(val)
	if not val:
		return "-"
	return f"{val:,.0f}".replace(",", ",")


def _flt(val):
	if val is None or val == "":
		return 0.0
	try:
		return float(val)
	except (TypeError, ValueError):
		return 0.0
