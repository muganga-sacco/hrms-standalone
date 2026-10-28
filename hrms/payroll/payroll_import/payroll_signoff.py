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
	if request is not None and _apply_signature_from_signed_payroll(user, request, prefer):
		row = _user_signoff_row(user)
		if row and row.payroll_signature:
			return row
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
	rows = frappe.get_all(
		"Payroll Excel Upload",
		filters=filters,
		fields=["name", "signed_payroll", "payroll_sheet_footer", "payroll_month", "payroll_sheet_type"],
		order_by="modified desc",
	)
	if not months:
		return rows
	matched = []
	for row in rows:
		month = row.payroll_month
		key = month.isoformat() if hasattr(month, "isoformat") else str(month or "")
		if key in set(months):
			matched.append(row)
	# The signed file may be attached to a neighbouring month. Use the latest one.
	return matched or rows[:1]


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


_HEADINGS = (
	("prepared by", "Prepared by"),
	("verified by", "Verified by"),
	("approved by", "Approved by"),
)


def _pdf_text_chunks(page) -> list[dict]:
	chunks = []

	def visitor(text, cm, tm, font_dict, font_size):
		cleaned = (text or "").replace("\x00", "").strip()
		if cleaned:
			chunks.append({"text": cleaned, "x": float(tm[4]), "y": float(tm[5])})

	page.extract_text(visitor_text=visitor)
	return chunks


def _placed_images(page) -> list[dict]:
	contents = page.get_contents()
	if contents is None:
		return []
	data = contents.get_data().decode("latin1", errors="replace")
	pattern = re.compile(
		r"q\s+([-\d.]+)\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+cm\s*/(\S+)\s+Do",
		re.S,
	)
	blobs = {image.name or "": image.data for image in page.images}
	placed = []
	for match in pattern.finditer(data):
		token = match.group(5).lstrip("/")
		blob = next((value for name, value in blobs.items() if token in name), None)
		if not blob:
			continue
		placed.append(
			{
				"x": float(match.group(3)),
				"y": float(match.group(4)),
				"w": abs(float(match.group(1))),
				"h": abs(float(match.group(2))),
				"blob": blob,
			}
		)
	return placed


def _heading_markers(chunks: list[dict]) -> list[dict]:
	found = []
	seen = set()
	for chunk in chunks:
		lower = chunk["text"].lower()
		for key, label in _HEADINGS:
			if key in lower and key not in seen:
				seen.add(key)
				found.append({**chunk, "heading": label, "key": key})
				break
	return sorted(found, key=lambda item: item["x"])


def _name_and_title(chunks: list[dict], heading: dict) -> tuple[str, str]:
	below = [
		chunk
		for chunk in chunks
		if abs(chunk["x"] - heading["x"]) < 90 and chunk["y"] < heading["y"] - 1
	]
	below.sort(key=lambda chunk: chunk["y"], reverse=True)
	name = ""
	title = ""
	for chunk in below:
		lower = chunk["text"].lower()
		if any(key in lower for key, _label in _HEADINGS) or lower.startswith("signature"):
			continue
		if not name:
			name = chunk["text"].strip(" :")
			continue
		title = chunk["text"].strip(" :")
		break
	return name, title


def _image_above_heading(images: list[dict], heading: dict, page_width: float) -> dict | None:
	candidates = []
	for image in images:
		center = image["x"] + image["w"] / 2
		if abs(center - heading["x"]) > page_width * 0.18:
			continue
		if image["y"] + image["h"] < heading["y"] - 8:
			continue
		candidates.append(image)
	if not candidates:
		return None
	return min(candidates, key=lambda image: abs(image["y"] - heading["y"]))


def _trim_signature(image):
	from PIL import Image

	if image.mode not in ("RGB", "RGBA"):
		image = image.convert("RGB")
	gray = image.convert("L")
	mask = gray.point(lambda pixel: 255 if pixel < 240 else 0)
	box = mask.getbbox()
	if not box:
		return image
	left, top, right, bottom = box
	pad = 6
	left = max(0, left - pad)
	top = max(0, top - pad)
	right = min(image.width, right + pad)
	bottom = min(image.height, bottom + pad)
	if right - left < 8 or bottom - top < 8:
		return image
	return image.crop((left, top, right, bottom))


def _crop_column_signature(page_image: dict, heading: dict, headings: list[dict], page_width: float, page_height: float) -> bytes | None:
	import io

	from PIL import Image

	image = Image.open(io.BytesIO(page_image["blob"]))
	scale_x = image.width / page_image["w"] if page_image["w"] else 1
	scale_y = image.height / page_image["h"] if page_image["h"] else 1
	index = headings.index(heading)
	left_edge = 0 if index == 0 else (headings[index - 1]["x"] + heading["x"]) / 2
	right_edge = page_width if index == len(headings) - 1 else (heading["x"] + headings[index + 1]["x"]) / 2
	top_pdf = heading["y"] + 78
	bottom_pdf = heading["y"] + 8

	def to_pixel(x_pos, y_pos):
		pixel_x = int((x_pos - page_image["x"]) * scale_x)
		pixel_y = int((page_image["y"] + page_image["h"] - y_pos) * scale_y)
		return pixel_x, pixel_y

	left, top = to_pixel(left_edge, top_pdf)
	right, bottom = to_pixel(right_edge, bottom_pdf)
	left, right = sorted((max(0, left), min(image.width, right)))
	top, bottom = sorted((max(0, top), min(image.height, bottom)))
	if right - left < 8 or bottom - top < 8:
		return None
	cropped = _trim_signature(image.crop((left, top, right, bottom)))
	buffer = io.BytesIO()
	cropped.convert("RGB").save(buffer, format="PNG")
	return buffer.getvalue()


def _pen_signature_blobs(page) -> list[bytes]:
	"""Handwritten signatures on a scanned page, left to right. Printed text is ignored."""
	import io

	from PIL import Image

	if not page.images:
		return []
	picture = max(page.images, key=lambda image: len(image.data))
	image = Image.open(io.BytesIO(picture.data)).convert("RGB")
	rotation = int(page.get("/Rotate") or 0) % 360
	if rotation:
		image = image.rotate(360 - rotation, expand=True)
	pixels = image.load()
	width, height = image.size
	points = []
	for y in range(0, height, 2):
		for x in range(0, width, 2):
			red, green, blue = pixels[x, y]
			if max(red, green, blue) - min(red, green, blue) >= 28 and max(red, green, blue) < 220:
				points.append((x, y))
	if len(points) < 30:
		return []
	points.sort()
	clusters = [[points[0]]]
	for point in points[1:]:
		if point[0] - clusters[-1][-1][0] > 70:
			clusters.append([point])
		else:
			clusters[-1].append(point)
	blobs = []
	for cluster in clusters:
		if len(cluster) < 20:
			continue
		xs = [point[0] for point in cluster]
		ys = [point[1] for point in cluster]
		pad = 4
		box = (
			max(0, min(xs) - pad),
			max(0, min(ys) - pad),
			min(width, max(xs) + pad),
			min(height, max(ys) + pad),
		)
		cropped = image.crop(box)
		ink = cropped.load()
		for py in range(cropped.height):
			for px in range(cropped.width):
				red, green, blue = ink[px, py]
				if max(red, green, blue) - min(red, green, blue) < 28 or max(red, green, blue) >= 220:
					ink[px, py] = (255, 255, 255)
		buffer = io.BytesIO()
		_trim_signature(cropped).save(buffer, format="PNG")
		blobs.append(buffer.getvalue())
	return blobs


def _signatories_from_pdf(path: str) -> list[dict]:
	from pypdf import PdfReader

	reader = PdfReader(path)
	if not reader.pages:
		return []
	page = reader.pages[0]
	page_width = float(page.mediabox.width)
	page_height = float(page.mediabox.height)
	chunks = _pdf_text_chunks(page)
	headings = _heading_markers(chunks)
	images = _placed_images(page)
	small = [image for image in images if image["w"] < page_width * 0.45 and image["h"] < page_height * 0.4]
	large = [image for image in images if image["w"] >= page_width * 0.55]
	signatories = []
	if headings and small:
		for heading in headings:
			image = _image_above_heading(small, heading, page_width)
			if not image:
				continue
			name, title = _name_and_title(chunks, heading)
			signatories.append(
				{"heading": heading["heading"], "name": name, "title": title, "blob": image["blob"]}
			)
	if not signatories and headings and large:
		for heading in headings:
			blob = _crop_column_signature(large[0], heading, headings, page_width, page_height)
			if not blob:
				continue
			name, title = _name_and_title(chunks, heading)
			signatories.append(
				{"heading": heading["heading"], "name": name, "title": title, "blob": blob}
			)
	if not signatories and large:
		blobs = _pen_signature_blobs(page)
		labels = ["Prepared by", "Verified by", "Approved by"]
		for index, blob in enumerate(blobs[:3]):
			signatories.append(
				{
					"heading": labels[index] if index < len(labels) else "",
					"name": "",
					"title": "",
					"blob": blob,
				}
			)
	if signatories:
		return signatories
	ordered = sorted(small, key=lambda image: image["x"])
	return [{"heading": "", "name": "", "title": "", "blob": image["blob"]} for image in ordered]


def _signatories_from_excel(path: str, footer: list[dict]) -> list[dict]:
	try:
		from openpyxl import load_workbook
	except ImportError:
		return []
	workbook = load_workbook(path)
	sheet = workbook.active
	pictures = sorted(getattr(sheet, "_images", []), key=lambda image: getattr(getattr(image.anchor, "_from", None), "col", 0))
	signatories = []
	for index, picture in enumerate(pictures):
		try:
			blob = picture._data()
		except Exception:
			continue
		source = footer[index] if index < len(footer) else {}
		signatories.append(
			{
				"heading": source.get("heading") or "",
				"name": source.get("name") or "",
				"title": source.get("title") or "",
				"blob": blob,
			}
		)
	return signatories


def _signatories_from_file(path: str, footer: list[dict]) -> list[dict]:
	lower = path.lower()
	if lower.endswith(".pdf"):
		found = _signatories_from_pdf(path)
	elif lower.endswith(".xlsx"):
		found = _signatories_from_excel(path, footer)
	else:
		found = []
	if not found:
		return []
	if any(item.get("name") for item in found):
		return found
	merged = []
	for item, source in zip(found, footer, strict=False):
		merged.append(
			{
				"heading": item.get("heading") or source.get("heading") or "",
				"name": source.get("name") or "",
				"title": source.get("title") or "",
				"blob": item["blob"],
			}
		)
	return merged or found


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
	if title:
		values["payroll_signatory_title"] = title
	frappe.db.set_value("User", user, values, update_modified=False)


def _apply_signature_from_signed_payroll(user: str, request, prefer: str | None) -> bool:
	full_name = frappe.db.get_value("User", user, "full_name")
	for upload in _signed_payroll_uploads(request):
		path = _file_path(upload.signed_payroll)
		if not path:
			continue
		footer = _footer_signatures(upload.payroll_sheet_footer)
		try:
			signatories = _signatories_from_file(path, footer)
		except Exception:
			frappe.log_error(title="Signed payroll signature")
			continue
		matched = [item for item in signatories if _names_match(full_name, item.get("name"))]
		if not matched:
			continue
		chosen = matched[0]
		if prefer:
			for item in matched:
				if prefer in (item.get("heading") or "").lower():
					chosen = item
					break
		try:
			_store_user_signature(user, _png_bytes(chosen["blob"]), (chosen.get("title") or "").strip())
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
