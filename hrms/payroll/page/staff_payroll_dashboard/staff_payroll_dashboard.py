# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from hrms.payroll.payroll_import.payroll_access import (
	throw_if_not_hr_payroll,
	throw_if_not_payroll_dashboard_viewer,
	user_has_hr_payroll_access,
)
from hrms.payroll.payroll_import.payroll_employee_link import find_employee_for_payroll_id
from hrms.payroll.payroll_import.payroll_month_utils import normalize_payroll_month
from hrms.payroll.payroll_import.payroll_sheet_layout import (
	ensure_payroll_sheet_layout,
	get_payroll_excel_upload_for_month,
	get_payroll_sheet_footer,
	get_payroll_sheet_header,
	resolve_payroll_logo_file_url,
)

LUMPSUM_NUMERIC_FIELDS = [
	"gross_salary",
	"paye",
	"pension_employee",
	"pension_employer",
	"net_salary",
]

VARIABLE_NUMERIC_FIELDS = [
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
	"take_home",
]

NUMERIC_FIELDS = [
	"basic_salary",
	"transport_allowance",
	"itc_allowance",
	"ict_allowance",
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
	"muganga_sacco_social_fund",
	"rpf",
	"brd_loan",
	"sport_subscription",
	"insurance_sanlam",
	"insurance_prime",
	"net_paid",
	"compulsory_saving",
	"take_home",
]

@frappe.whitelist()
def get_payroll_dashboard_companies() -> list[str]:
	"""Companies for dashboard filter (no Company doctype read required on desk)."""
	throw_if_not_payroll_dashboard_viewer()
	companies = frappe.db.sql(
		"""
		SELECT DISTINCT company
		FROM `tabImported Payroll Record`
		WHERE docstatus = 1 AND company IS NOT NULL AND company != ''
		ORDER BY company ASC
		""",
		pluck=True,
	)
	companies = [c for c in companies if c]
	if not companies:
		default = frappe.db.get_single_value("Global Defaults", "default_company")
		if default:
			companies = [default]
	return companies


@frappe.whitelist()
def get_payroll_dashboard_options() -> dict:
	"""Company name plus the years that already have an uploaded payroll."""
	throw_if_not_payroll_dashboard_viewer()
	companies = get_payroll_dashboard_companies()
	latest = frappe.db.sql(
		"""
		SELECT MAX(payroll_month)
		FROM `tabImported Payroll Record`
		WHERE docstatus = 1 AND payroll_month IS NOT NULL
		"""
	)[0][0]
	years = frappe.db.sql(
		"""
		SELECT DISTINCT YEAR(payroll_month)
		FROM `tabImported Payroll Record`
		WHERE docstatus = 1 AND payroll_month IS NOT NULL
		""",
		pluck=True,
	)
	year_set = {int(year) for year in years if year}
	year_set.add(getdate().year)
	latest_iso = None
	if latest:
		latest_date = getdate(latest)
		latest_iso = latest_date.isoformat()
		year_set.add(latest_date.year)
	return {
		"companies": companies,
		"years": sorted(year_set, reverse=True),
		"latest_payroll_month": latest_iso,
	}


def _variable_group_key(record: dict) -> str:
	upload = (record.get("payroll_excel_upload") or "").strip()
	if upload:
		return f"upload:{upload}"
	label = (record.get("payroll_period_label") or "").strip()
	return f"label:{label or 'Variable'}"


def _variable_month_response(records: list[dict], month, company: str | None, requested_month: str) -> dict:
	"""One sheet per bonus or incentive uploaded in the month."""
	groups: dict[str, list[dict]] = {}
	for record in records:
		groups.setdefault(_variable_group_key(record), []).append(record)

	sheets = []
	for group_records in groups.values():
		sheets.append(_one_variable_sheet(group_records, month, company))

	return {
		"layout": "variable",
		"payroll_sheet_type": "Variable",
		"filters_applied": {
			"payroll_month": month.isoformat(),
			"payroll_sheet_type": "Variable",
			"company": company,
			"requested_payroll_month": normalize_payroll_month(requested_month).isoformat()
			if normalize_payroll_month(requested_month)
			else requested_month,
		},
		"payroll_month": month.isoformat(),
		"month_label": month.strftime("%B").upper(),
		"sheets": sheets,
		"rows": [],
		"count": sum(sheet["count"] for sheet in sheets),
	}


def _one_variable_sheet(records: list[dict], month, company: str | None) -> dict:
	rows = []
	for idx, record in enumerate(records, start=1):
		staff_row = _staff_payroll_row_for_employee(record.get("employee_id_number"), month)
		row = {"sn": idx}
		for field in ROW_FIELDS:
			val = record.get(field)
			if staff_row:
				if field == "date_of_joining" and not val:
					val = staff_row.get("date_of_joining")
				elif field == "department" and staff_row.get("department"):
					val = staff_row.get("department")
				elif field == "position" and not val and staff_row.get("position"):
					val = staff_row.get("position")
			if field == "date_of_joining":
				val = val or _employee_date_of_joining(record)
			if field == "date_of_joining" and val:
				val = getdate(val).strftime("%d-%m-%Y")
			elif field in NUMERIC_FIELDS:
				val = flt(val)
			row[field] = val
		if not flt(row.get("take_home")):
			row["take_home"] = flt(record.get("net_salary"))
		rows.append(row)

	totals = {field: 0.0 for field in VARIABLE_NUMERIC_FIELDS}
	for record in records:
		for field in VARIABLE_NUMERIC_FIELDS:
			totals[field] += flt(record.get(field))
	if not totals["take_home"]:
		totals["take_home"] = sum(flt(row.get("take_home")) for row in rows)

	title_label = (records[0].get("payroll_period_label") or "").strip() or month.strftime("%B %Y")
	payroll_excel_upload = records[0].get("payroll_excel_upload")
	ensure_payroll_sheet_layout(payroll_excel_upload, allow_sync=False)
	header = get_payroll_sheet_header(
		company, title_label, payroll_excel_upload, payroll_sheet_type="Variable"
	)
	banner = _lumpsum_sheet_banner(payroll_excel_upload, records, title_label)
	if banner:
		header["title"] = banner
	footer = get_payroll_sheet_footer(
		company,
		payroll_month=month,
		payroll_excel_upload=payroll_excel_upload,
		payroll_sheet_type="Variable",
	)
	if not (footer.get("signatures") or []) and company:
		staff_upload = get_payroll_excel_upload_for_month(company, month, "Staff Payroll")
		if staff_upload and staff_upload != payroll_excel_upload:
			staff_footer = get_payroll_sheet_footer(
				company, payroll_month=month, payroll_excel_upload=staff_upload
			)
			if staff_footer.get("signatures"):
				footer = staff_footer
	if payroll_excel_upload and company and not header.get("logo_url"):
		staff_upload = get_payroll_excel_upload_for_month(company, month, "Staff Payroll")
		if staff_upload and staff_upload != payroll_excel_upload:
			header["logo_url"] = get_payroll_sheet_header(
				company, title_label, staff_upload, payroll_sheet_type="Variable"
			).get("logo_url")
			header["logo_missing"] = not bool(header.get("logo_url"))

	return {
		**header,
		"payroll_excel_upload": payroll_excel_upload,
		"payroll_period_label": title_label,
		"grand_total_label": f"GRAND TOTAL_{month.strftime('%B').upper()} {month.year}",
		"rows": rows,
		"totals": totals,
		"count": len(rows),
		"footer": footer,
		"filters_applied": {
			"payroll_month": month.isoformat(),
			"payroll_sheet_type": "Variable",
			"company": company,
		},
	}


def _employee_date_of_joining(record: dict):
	employee = record.get("employee")
	if not employee:
		emp_id = (record.get("employee_id_number") or "").strip()
		if emp_id:
			employee = find_employee_for_payroll_id(emp_id)
	if not employee:
		return None
	return frappe.db.get_value("Employee", employee, "date_of_joining")


def _staff_payroll_row_for_employee(employee_id_number: str, payroll_month) -> dict | None:
	if not employee_id_number or not payroll_month:
		return None
	return frappe.db.get_value(
		"Imported Payroll Record",
		{
			"employee_id_number": employee_id_number,
			"payroll_month": payroll_month,
			"payroll_sheet_type": "Staff Payroll",
			"docstatus": 1,
		},
		["date_of_joining", "department", "position"],
		as_dict=True,
	)


def _lumpsum_sheet_banner(
	payroll_excel_upload: str | None, records: list[dict], fallback_label: str
) -> str:
	if payroll_excel_upload:
		upload_label = (frappe.db.get_value("Payroll Excel Upload", payroll_excel_upload, "payroll_period_label") or "").strip()
		if upload_label:
			return upload_label.upper()
	if records:
		labels = [(r.get("payroll_period_label") or "").strip() for r in records]
		best = max(labels, key=len, default="")
		if best and len(best) > len(fallback_label or ""):
			return best.upper()
	return (fallback_label or "").upper()


ROW_FIELDS = [
	"employee_id_number",
	"employee_name",
	"date_of_joining",
	"department",
	"position",
	*NUMERIC_FIELDS,
	"compulsory_saving_account",
	"account_number",
	"bank",
]


@frappe.whitelist()
def get_staff_payroll_dashboard(
	payroll_month: str,
	company: str | None = None,
	payroll_sheet_type: str | None = "Staff Payroll",
):
	if not payroll_month:
		frappe.throw(_("Payroll Month is required."))

	throw_if_not_payroll_dashboard_viewer()

	month = normalize_payroll_month(payroll_month)
	if not month:
		frappe.throw(_("Payroll Month is required."))
	filters: dict = {"docstatus": 1, "payroll_month": month}
	if company:
		filters["company"] = company
	effective_sheet_type = payroll_sheet_type if payroll_sheet_type not in ("All", "", None) else "Staff Payroll"
	if payroll_sheet_type and payroll_sheet_type not in ("All", ""):
		filters["payroll_sheet_type"] = payroll_sheet_type
	else:
		filters["payroll_sheet_type"] = ["in", ["Staff Payroll", "Lumpsum"]]

	records = frappe.get_all(
		"Imported Payroll Record",
		filters=filters,
		fields=ROW_FIELDS
		+ ["payroll_period_label", "currency", "payroll_excel_upload", "company", "employee"],
		order_by="payroll_period_label asc, employee_id_number asc",
	)

	effective_company = company or (records[0].get("company") if records else None)
	if effective_sheet_type == "Variable":
		return _variable_month_response(records, month, effective_company, payroll_month)

	rows = []
	for idx, record in enumerate(records, start=1):
		staff_row = (
			_staff_payroll_row_for_employee(record.get("employee_id_number"), month)
			if effective_sheet_type in ("Lumpsum", "Variable")
			else None
		)
		row = {"sn": idx}
		for field in ROW_FIELDS:
			val = record.get(field)
			if staff_row:
				if field == "date_of_joining" and not val:
					val = staff_row.get("date_of_joining")
				elif field == "department" and staff_row.get("department"):
					val = staff_row.get("department")
				elif field == "position" and not val and staff_row.get("position"):
					val = staff_row.get("position")
			if field == "date_of_joining":
				val = val or _employee_date_of_joining(record)
			if field == "date_of_joining" and val:
				val = getdate(val).strftime("%d-%m-%Y")
			elif field in NUMERIC_FIELDS:
				val = flt(val)
			row[field] = val
		if effective_sheet_type == "Variable" and not flt(row.get("take_home")):
			row["take_home"] = flt(record.get("net_salary"))
		rows.append(row)

	if effective_sheet_type == "Lumpsum":
		total_fields = LUMPSUM_NUMERIC_FIELDS
	elif effective_sheet_type == "Variable":
		total_fields = VARIABLE_NUMERIC_FIELDS
	else:
		total_fields = NUMERIC_FIELDS
	totals = {field: 0.0 for field in total_fields}
	for record in records:
		for field in total_fields:
			totals[field] += flt(record.get(field))

	title_label = month.strftime("%B %Y")
	if records:
		title_label = records[0].get("payroll_period_label") or title_label
	currency = records[0].get("currency") if records else None
	if not currency and effective_company:
		currency = frappe.db.get_value("Company", effective_company, "default_currency")

	payroll_excel_upload = (
		records[0].get("payroll_excel_upload")
		if records
		else get_payroll_excel_upload_for_month(effective_company, month, effective_sheet_type)
	)
	ensure_payroll_sheet_layout(payroll_excel_upload, allow_sync=False)
	header = get_payroll_sheet_header(
		effective_company, title_label, payroll_excel_upload, payroll_sheet_type=effective_sheet_type
	)
	if effective_sheet_type in ("Lumpsum", "Variable"):
		banner = _lumpsum_sheet_banner(payroll_excel_upload, records, title_label)
		if banner:
			header["title"] = banner
	elif records:
		period = (records[0].get("payroll_period_label") or "").strip()
		if period and "STAFF PAYROLL" in period.upper():
			header["title"] = period.upper()

	footer = get_payroll_sheet_footer(
		effective_company,
		payroll_month=month,
		payroll_excel_upload=payroll_excel_upload,
		payroll_sheet_type=effective_sheet_type,
	)
	if (
		effective_sheet_type == "Lumpsum"
		and footer.get("source") == "fallback"
		and not (footer.get("signatures") or [])
		and effective_company
	):
		staff_upload = get_payroll_excel_upload_for_month(effective_company, month, "Staff Payroll")
		if staff_upload and staff_upload != payroll_excel_upload:
			staff_footer = get_payroll_sheet_footer(
				effective_company,
				payroll_month=month,
				payroll_excel_upload=staff_upload,
			)
			if staff_footer.get("signatures"):
				footer = staff_footer

	if effective_sheet_type == "Lumpsum" and payroll_excel_upload:
		if not resolve_payroll_logo_file_url(effective_company, payroll_excel_upload) and effective_company:
			staff_upload = get_payroll_excel_upload_for_month(effective_company, month, "Staff Payroll")
			if staff_upload and staff_upload != payroll_excel_upload:
				header["logo_url"] = get_payroll_sheet_header(
					effective_company, title_label, staff_upload, payroll_sheet_type=effective_sheet_type
				).get("logo_url")
				header["logo_missing"] = not bool(header.get("logo_url"))

	if effective_sheet_type == "Lumpsum":
		layout = "lumpsum"
	elif effective_sheet_type == "Variable":
		layout = "variable"
	else:
		layout = "staff_payroll"
	grand_total_label = f"GRAND TOTAL_{month.strftime('%B').upper()} {month.year}"
	return {
		**header,
		"layout": layout,
		"payroll_sheet_type": effective_sheet_type,
		"filters_applied": {
			"payroll_month": month.isoformat(),
			"payroll_sheet_type": payroll_sheet_type or effective_sheet_type,
			"company": effective_company,
			"requested_payroll_month": normalize_payroll_month(payroll_month).isoformat()
			if normalize_payroll_month(payroll_month)
			else payroll_month,
		},
		"payroll_month": month.isoformat(),
		"month_label": month.strftime("%B").upper(),
		"grand_total_label": grand_total_label,
		"currency": currency or "RWF",
		"rows": rows,
		"totals": totals,
		"count": len(rows),
		"footer": footer,
	}


@frappe.whitelist()
def delete_payroll_for_filters(
	payroll_month: str,
	company: str | None = None,
	payroll_sheet_type: str | None = "Staff Payroll",
):
	"""Cancel and delete submitted Imported Payroll Records for the dashboard filters."""
	throw_if_not_hr_payroll()
	if not payroll_month:
		frappe.throw(_("Payroll Month is required."))
	if not frappe.has_permission("Imported Payroll Record", "delete"):
		frappe.throw(_("Not permitted to delete payroll records."), frappe.PermissionError)

	month = normalize_payroll_month(payroll_month)
	if not month:
		frappe.throw(_("Payroll Month is required."))

	filters: dict = {"docstatus": 1, "payroll_month": month}
	if company:
		filters["company"] = company
	if payroll_sheet_type and payroll_sheet_type not in ("All", ""):
		filters["payroll_sheet_type"] = payroll_sheet_type

	names = frappe.get_all("Imported Payroll Record", filters=filters, pluck="name")
	if not names:
		return {"deleted": 0, "message": _("No submitted payroll records matched these filters.")}

	deleted = 0
	for name in names:
		doc = frappe.get_doc("Imported Payroll Record", name)
		if doc.docstatus == 1:
			doc.flags.ignore_permissions = True
			doc.cancel()
		frappe.delete_doc("Imported Payroll Record", name, force=1, ignore_permissions=True)
		deleted += 1

	frappe.db.commit()
	sheet = payroll_sheet_type or _("All sheet types")
	company_part = company or _("all companies")
	return {
		"deleted": deleted,
		"message": _("Deleted {0} payroll record(s) for {1}, {2}, {3}.").format(
			deleted, company_part, month.strftime("%B %Y"), sheet
		),
	}
