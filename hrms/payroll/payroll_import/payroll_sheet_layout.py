# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import json
import os
import re
from calendar import monthrange
from datetime import date

import frappe
from frappe.utils import get_url, getdate


def _file_url_to_path(file_url: str | None) -> str | None:
	if not file_url:
		return None
	try:
		from frappe.utils.file_manager import get_file_path

		path = get_file_path(file_url)
		if path and os.path.exists(path):
			return path
	except Exception:
		pass
	try:
		file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
		if file_name:
			path = frappe.get_doc("File", file_name).get_full_path()
			if path and os.path.exists(path):
				return path
	except Exception:
		pass
	return None


def _file_url_to_public_url(file_url: str | None) -> str | None:
	if not file_url:
		return None
	if file_url.startswith("http"):
		return file_url
	return get_url(file_url)


def _company_attach_fieldnames() -> list[str]:
	meta = frappe.get_meta("Company")
	return [f for f in ("company_logo", "logo") if meta.has_field(f)]


def _letter_head_logo_file_url(company: str) -> str | None:
	if not frappe.db.table_exists("tabLetter Head"):
		return None
	letter_head = frappe.db.get_value("Company", company, "default_letter_head")
	if not letter_head:
		return None
	lh_meta = frappe.get_meta("Letter Head")
	for fieldname in ("image", "logo", "letter_head_image"):
		if lh_meta.has_field(fieldname):
			file_url = frappe.db.get_value("Letter Head", letter_head, fieldname)
			if file_url:
				return file_url
	return None


BUNDLED_LOGO_FILES = ("muganga_sacco_logo.png", "company_payroll_logo.png")


def _bundled_logo_path() -> str | None:
	try:
		import hrms

		base = os.path.join(os.path.dirname(hrms.__file__), "public", "images")
		for filename in BUNDLED_LOGO_FILES:
			path = os.path.join(base, filename)
			if os.path.exists(path):
				return path
	except Exception:
		pass
	return None


def _bundled_logo_url() -> str | None:
	path = _bundled_logo_path()
	if not path:
		return None
	return get_url(f"/assets/hrms/images/{os.path.basename(path)}")


def _upload_logo_file_url(payroll_excel_upload: str | None) -> str | None:
	if not payroll_excel_upload:
		return None
	meta = frappe.get_meta("Payroll Excel Upload")
	if not meta.has_field("payroll_sheet_logo"):
		return None
	return frappe.db.get_value("Payroll Excel Upload", payroll_excel_upload, "payroll_sheet_logo")


def _company_logo_file_url(company: str | None) -> str | None:
	if not company:
		return None
	for fieldname in _company_attach_fieldnames():
		file_url = frappe.db.get_value("Company", company, fieldname)
		if file_url:
			return file_url
	return _letter_head_logo_file_url(company)


def resolve_payroll_logo_file_url(
	company: str | None, payroll_excel_upload: str | None = None
) -> str | None:
	"""Logo order: imported Excel upload → Company logo / letter head → bundled asset."""
	upload_logo = _upload_logo_file_url(payroll_excel_upload)
	if upload_logo:
		return upload_logo
	company_logo = _company_logo_file_url(company)
	if company_logo:
		return company_logo
	return None


def get_company_logo_url(company: str | None, payroll_excel_upload: str | None = None) -> str | None:
	file_url = resolve_payroll_logo_file_url(company, payroll_excel_upload)
	if file_url:
		return _file_url_to_public_url(file_url)
	return _bundled_logo_url()


def get_company_logo_path(company: str | None, payroll_excel_upload: str | None = None) -> str | None:
	file_url = resolve_payroll_logo_file_url(company, payroll_excel_upload)
	if file_url and not str(file_url).startswith("/assets/"):
		path = _file_url_to_path(file_url)
		if path:
			return path
	return _bundled_logo_path()


def get_payroll_excel_upload_for_month(company: str | None, payroll_month) -> str | None:
	if not company or not payroll_month:
		return None
	month = getdate(payroll_month)
	rows = frappe.get_all(
		"Payroll Excel Upload",
		filters={"company": company, "payroll_month": month, "status": "Imported"},
		fields=["name"],
		order_by="modified desc",
		limit=1,
	)
	return rows[0].name if rows else None


def _load_footer_from_upload(payroll_excel_upload: str | None) -> dict | None:
	if not payroll_excel_upload:
		return None
	meta = frappe.get_meta("Payroll Excel Upload")
	if not meta.has_field("payroll_sheet_footer"):
		return None
	raw = frappe.db.get_value("Payroll Excel Upload", payroll_excel_upload, "payroll_sheet_footer")
	if not raw:
		return None
	if isinstance(raw, dict):
		return raw
	try:
		return json.loads(raw)
	except (TypeError, ValueError):
		return None


def _normalize_footer(footer: dict | None) -> dict | None:
	if not footer:
		return None
	date_line = (footer.get("date_line") or "").strip()
	signatures = footer.get("signatures") or []
	clean_sigs = []
	for sig in signatures:
		if not isinstance(sig, dict):
			continue
		name = (sig.get("name") or "").strip()
		title = (sig.get("title") or "").strip()
		heading = (sig.get("heading") or "").strip()
		if not heading and not name and not title:
			continue
		if heading and not heading.endswith(":"):
			heading = f"{heading}:"
		clean_sigs.append({"heading": heading, "name": name, "title": title})
	if not date_line and not clean_sigs:
		return None
	place = footer.get("place")
	if not place and date_line:
		match = re.match(r"Done at\s+(.+?),\s*on\s+", date_line, re.I)
		if match:
			place = match.group(1).strip()
	return {"date_line": date_line, "place": place, "signatures": clean_sigs}


def payroll_month_footer_date(payroll_month) -> date:
	month = getdate(payroll_month)
	last_day = monthrange(month.year, month.month)[1]
	return date(month.year, month.month, last_day)


def get_payroll_sheet_footer(
	company: str | None = None,
	on_date: date | None = None,
	payroll_month=None,
	payroll_excel_upload: str | None = None,
) -> dict:
	if not payroll_excel_upload and company and payroll_month:
		payroll_excel_upload = get_payroll_excel_upload_for_month(company, payroll_month)

	stored = _normalize_footer(_load_footer_from_upload(payroll_excel_upload))
	if stored:
		stored["company"] = company
		stored["source"] = "excel_import"
		return stored

	if payroll_month and not on_date:
		on_date = payroll_month_footer_date(payroll_month)
	on_date = on_date or date.today()
	return {
		"date_line": f"Done at Kigali, on {on_date.strftime('%d/%m/%Y')}",
		"place": "Kigali",
		"signatures": [],
		"company": company,
		"source": "fallback",
	}


def get_payroll_sheet_header(
	company: str | None,
	period_label: str,
	payroll_excel_upload: str | None = None,
) -> dict:
	logo_url = get_company_logo_url(company, payroll_excel_upload)
	return {
		"title": f"STAFF PAYROLL {period_label.upper()}",
		"company": company,
		"company_name": frappe.db.get_value("Company", company, "name") if company else None,
		"logo_url": logo_url,
		"logo_missing": not bool(logo_url),
		"logo_hint": _logo_setup_hint(company) if not logo_url else None,
		"payroll_excel_upload": payroll_excel_upload,
	}


def _logo_setup_hint(company: str | None) -> str:
	return frappe._(
		"Import payroll Excel to capture the sheet logo and signatures, or set Company Logo on {0}."
	).format(company or "Company")


def extract_first_image_from_workbook(file_path: str) -> tuple[bytes, str] | None:
	if not file_path or not os.path.exists(file_path):
		return None
	try:
		from openpyxl import load_workbook
	except ImportError:
		return None
	try:
		wb = load_workbook(file_path, data_only=True)
		ws = wb.active
		images = getattr(ws, "_images", None) or []
		if not images:
			wb.close()
			return None
		image = images[0]
		data = image._data() if hasattr(image, "_data") else None
		wb.close()
		if not data:
			return None
		ext = ".png"
		if hasattr(image, "format") and image.format:
			ext = f".{str(image.format).lower()}"
			if not ext.startswith("."):
				ext = f".{ext}"
		return data, ext
	except Exception:
		frappe.log_error(title="Extract payroll Excel logo")
		return None


def save_payroll_sheet_logo_from_excel(file_path: str, payroll_excel_upload: str) -> str | None:
	meta = frappe.get_meta("Payroll Excel Upload")
	if not meta.has_field("payroll_sheet_logo"):
		return None
	extracted = extract_first_image_from_workbook(file_path)
	if not extracted:
		return None
	data, ext = extracted
	from frappe.utils.file_manager import save_file

	filename = f"payroll-sheet-logo-{frappe.scrub(payroll_excel_upload)}{ext}"
	file_doc = save_file(
		filename,
		data,
		"Payroll Excel Upload",
		payroll_excel_upload,
		is_private=0,
	)
	frappe.db.set_value(
		"Payroll Excel Upload",
		payroll_excel_upload,
		"payroll_sheet_logo",
		file_doc.file_url,
		update_modified=False,
	)
	return file_doc.file_url


def sync_payroll_sheet_layout_from_upload(payroll_excel_upload: str) -> bool:
	"""Parse attached workbook and store sheet logo + footer on Payroll Excel Upload."""
	if not payroll_excel_upload:
		return False
	doc = frappe.get_doc("Payroll Excel Upload", payroll_excel_upload)
	if not doc.payroll_file:
		return False
	file_path = frappe.get_doc("File", {"file_url": doc.payroll_file}).get_full_path()
	if not file_path or not os.path.exists(file_path):
		return False

	from hrms.payroll.payroll_import.payroll_excel_parser import parse_payroll_excel

	try:
		parsed = parse_payroll_excel(file_path)
	except Exception:
		frappe.log_error(title="Refresh payroll sheet layout")
		return False

	if parsed.get("sheet_footer"):
		doc.payroll_sheet_footer = parsed["sheet_footer"]
		doc.flags.ignore_permissions = True
		doc.save()
	save_payroll_sheet_logo_from_excel(file_path, payroll_excel_upload)
	if doc.company:
		sync_company_logo_from_payroll_excel(file_path, doc.company)
	frappe.db.commit()
	return True


def ensure_payroll_sheet_layout(payroll_excel_upload: str | None) -> None:
	if not payroll_excel_upload:
		return
	meta = frappe.get_meta("Payroll Excel Upload")
	if not meta.has_field("payroll_sheet_footer"):
		return
	row = frappe.db.get_value(
		"Payroll Excel Upload",
		payroll_excel_upload,
		["payroll_sheet_logo", "payroll_sheet_footer"],
		as_dict=True,
	)
	if row and row.payroll_sheet_logo and row.payroll_sheet_footer:
		return
	sync_payroll_sheet_layout_from_upload(payroll_excel_upload)


def sync_company_logo_from_payroll_excel(file_path: str, company: str | None) -> bool:
	"""Copy workbook logo to Company when Company Logo is still empty."""
	if not company:
		return False
	meta = frappe.get_meta("Company")
	if not meta.has_field("company_logo"):
		return False
	if frappe.db.get_value("Company", company, "company_logo"):
		return False
	extracted = extract_first_image_from_workbook(file_path)
	if not extracted:
		return False
	data, ext = extracted
	from frappe.utils.file_manager import save_file

	filename = f"payroll-logo-{frappe.scrub(company)}{ext}"
	file_doc = save_file(filename, data, "Company", company, is_private=0)
	frappe.db.set_value("Company", company, "company_logo", file_doc.file_url, update_modified=True)
	return True
