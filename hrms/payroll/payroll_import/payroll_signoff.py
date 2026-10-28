# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""HR and DAF signatures stamped onto an approved payslip."""

from __future__ import annotations

import json
import os
import re

import frappe
from frappe import _
from frappe.utils import format_datetime


def user_has_daf_access(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Guest":
		return False
	if user == "Administrator":
		return True
	return "DAF" in set(frappe.get_roles(user))


def throw_if_not_daf(message: str | None = None) -> None:
	if not user_has_daf_access():
		frappe.throw(message or _("Only DAF can approve this payslip."), frappe.PermissionError)


def approver_profile(user: str, request=None, prefer: str | None = None) -> dict:
	"""Name, title, and signature file for the user who is approving.

	The signature already printed on the signed payroll for this period is used
	when the approver's name is one of the signatories on that sheet.
	"""
	if not user:
		frappe.throw(_("Approver is required."))
	row = _user_signoff_row(user)
	if row and row.payroll_signature:
		return row
	if request is not None and _apply_signature_from_signed_payroll(user, request, prefer):
		row = _user_signoff_row(user)
		if row and row.payroll_signature:
			return row
	frappe.throw(
		_("Upload your signature on your User profile (Payroll Sign-off) before approving.")
	)


def _user_signoff_row(user: str):
	return frappe.db.get_value(
		"User",
		user,
		["full_name", "payroll_signature", "payroll_signatory_title"],
		as_dict=True,
	)


def _name_tokens(value: str | None) -> set[str]:
	return set(re.findall(r"[a-z]+", (value or "").lower()))


def _names_match(left: str | None, right: str | None) -> bool:
	left_tokens = _name_tokens(left)
	right_tokens = _name_tokens(right)
	if not left_tokens or not right_tokens:
		return False
	return left_tokens == right_tokens or left_tokens <= right_tokens or right_tokens <= left_tokens


def _request_months(request) -> list:
	from frappe.utils import getdate

	start = request.get("from_month") or request.get("payroll_month")
	end = request.get("to_month") or request.get("payroll_month")
	if not start:
		return []
	start = getdate(start)
	end = getdate(end) if end else start
	if end < start:
		start, end = end, start
	months = []
	year, month = start.year, start.month
	while (year, month) <= (end.year, end.month):
		months.append(f"{year:04d}-{month:02d}-01")
		month += 1
		if month == 13:
			month = 1
			year += 1
	return months


def _signed_payroll_uploads(request) -> list[dict]:
	months = _request_months(request)
	filters: dict = {"signed_payroll": ["is", "set"]}
	company = request.get("company")
	if company:
		filters["company"] = company
	if months:
		filters["payroll_month"] = ["in", months]
	return frappe.get_all(
		"Payroll Excel Upload",
		filters=filters,
		fields=["name", "signed_payroll", "payroll_sheet_footer", "payroll_month", "payroll_sheet_type"],
		order_by="payroll_month desc, modified desc",
	)


def _file_path(file_url: str | None) -> str | None:
	path = signature_image_path(file_url)
	if not path:
		return None
	if os.path.isabs(path) and os.path.exists(path):
		return path
	rooted = os.path.abspath(os.path.join(frappe.utils.get_bench_path(), "sites", path.lstrip("./")))
	if os.path.exists(rooted):
		return rooted
	return path if os.path.exists(path) else None


def _footer_signatures(raw) -> list[dict]:
	if not raw:
		return []
	if isinstance(raw, str):
		try:
			raw = json.loads(raw)
		except (TypeError, ValueError):
			return []
	signatures = raw.get("signatures") if isinstance(raw, dict) else None
	if not isinstance(signatures, list):
		return []
	return [sig for sig in signatures if isinstance(sig, dict)]


def _pdf_signature_images(path: str) -> list[dict]:
	"""Signature pictures on the sheet, left to right, excluding the logo."""
	from pypdf import PdfReader

	reader = PdfReader(path)
	if not reader.pages:
		return []
	page = reader.pages[0]
	contents = page.get_contents()
	if contents is None:
		return []
	data = contents.get_data().decode("latin1", errors="replace")
	placed = []
	pattern = re.compile(
		r"q\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)\s+([-\d.]+)\s+cm\s*/(\S+)\s+Do",
		re.S,
	)
	for match in pattern.finditer(data):
		placed.append(
			{
				"x": float(match.group(1)),
				"y": float(match.group(2)),
				"token": match.group(3).lstrip("/"),
			}
		)
	if not placed:
		return []
	rows: dict[int, list[dict]] = {}
	for item in placed:
		rows.setdefault(round(item["y"] / 40), []).append(item)
	signature_row = min(rows, key=lambda key: sum(item["y"] for item in rows[key]) / len(rows[key]))
	if len(rows) > 1:
		signature_row = min(rows, key=lambda key: sum(item["y"] for item in rows[key]) / len(rows[key]))
	ordered = sorted(rows[signature_row], key=lambda item: item["x"])
	images = []
	for item in ordered:
		blob = None
		for image in page.images:
			if item["token"] in (image.name or ""):
				blob = image.data
				break
		if blob:
			images.append(blob)
	return images


def _png_bytes(blob: bytes) -> bytes:
	import io

	from PIL import Image

	image = Image.open(io.BytesIO(blob))
	if image.mode in ("RGBA", "LA"):
		background = Image.new("RGB", image.size, "white")
		background.paste(image, mask=image.split()[-1])
		image = background
	else:
		image = image.convert("RGB")
	buffer = io.BytesIO()
	image.save(buffer, format="PNG")
	return buffer.getvalue()


def _store_user_signature(user: str, png: bytes, title: str | None) -> None:
	file_name = f"{frappe.scrub(user)}-payroll-signature.png"
	existing = frappe.db.get_value(
		"File",
		{"attached_to_doctype": "User", "attached_to_name": user, "file_name": file_name},
		"name",
	)
	if existing:
		frappe.delete_doc("File", existing, ignore_permissions=True, force=1)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"attached_to_doctype": "User",
			"attached_to_name": user,
			"is_private": 1,
			"content": png,
		}
	)
	file_doc.save(ignore_permissions=True)
	values = {"payroll_signature": file_doc.file_url}
	if title and not frappe.db.get_value("User", user, "payroll_signatory_title"):
		values["payroll_signatory_title"] = title
	frappe.db.set_value("User", user, values, update_modified=False)


def _apply_signature_from_signed_payroll(user: str, request, prefer: str | None) -> bool:
	full_name = frappe.db.get_value("User", user, "full_name")
	for upload in _signed_payroll_uploads(request):
		file_url = upload.signed_payroll or ""
		if not str(file_url).lower().endswith(".pdf"):
			continue
		path = _file_path(file_url)
		if not path:
			continue
		try:
			images = _pdf_signature_images(path)
		except Exception:
			frappe.log_error(title="Signed payroll signature")
			continue
		signatures = _footer_signatures(upload.payroll_sheet_footer)
		if not images or not signatures:
			continue
		pairs = list(zip(signatures, images, strict=False))
		matched = [
			(sig, blob)
			for sig, blob in pairs
			if _names_match(full_name, sig.get("name"))
		]
		if not matched:
			continue
		chosen = matched[0]
		if prefer:
			for sig, blob in matched:
				if prefer in (sig.get("heading") or "").lower():
					chosen = (sig, blob)
					break
		sig, blob = chosen
		try:
			_store_user_signature(user, _png_bytes(blob), (sig.get("title") or "").strip())
		except Exception:
			frappe.log_error(title="Signed payroll signature")
			continue
		return True
	return False


def signature_image_path(file_url: str | None) -> str | None:
	if not file_url:
		return None
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		return None
	path = frappe.get_doc("File", file_name).get_full_path()
	if path and os.path.exists(path):
		return path
	return None


def _block(user: str | None, approved_on, heading: str) -> dict | None:
	if not user:
		return None
	row = frappe.db.get_value(
		"User",
		user,
		["full_name", "payroll_signature", "payroll_signatory_title"],
		as_dict=True,
	) or {}
	when = ""
	if approved_on:
		when = format_datetime(approved_on, "dd MMM yyyy, HH:mm")
	return {
		"heading": heading,
		"name": row.get("full_name") or user,
		"title": row.get("payroll_signatory_title") or "",
		"approved_on": when,
		"image_path": signature_image_path(row.get("payroll_signature")),
	}


def signoff_for_request(doc) -> dict | None:
	"""Verified-by (HR) and Approved-by (DAF) blocks for the payslip document."""
	verified_user = doc.hr_approved_by
	verified_on = doc.hr_approved_on
	approved_user = doc.daf_approved_by
	approved_on = doc.daf_approved_on
	if not verified_user and doc.status == "Approved" and doc.approved_by and not approved_user:
		verified_user = doc.approved_by
		verified_on = doc.approved_on
	verified = _block(verified_user, verified_on, "Verified by")
	approved = _block(approved_user, approved_on, "Approved by")
	if not verified and not approved:
		return None
	return {"verified_by": verified, "approved_by": approved}
