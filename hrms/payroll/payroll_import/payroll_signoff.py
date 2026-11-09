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


def user_has_md_access(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Guest":
		return False
	if user == "Administrator":
		return True
	return "MD" in set(frappe.get_roles(user))


def throw_if_not_md(message: str | None = None) -> None:
	if not user_has_md_access():
		frappe.throw(message or _("Only MD can approve this payslip."), frappe.PermissionError)


def approver_profile(user: str, request=None, prefer: str | None = None) -> dict:
	"""Name, title, and signature from this user's Payroll Sign-off, not the sheet."""
	if not user:
		frappe.throw(_("Approver is required."))
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


def _write_png(png: bytes, prefix: str) -> str:
	folder = frappe.get_site_path("private", "files")
	os.makedirs(folder, exist_ok=True)
	path = os.path.join(folder, f"{prefix}-{frappe.generate_hash(length=10)}.png")
	with open(path, "wb") as handle:
		handle.write(png)
	return path


def _is_printed_rule_pixel(red: int, green: int, blue: int) -> bool:
	"""Gray/black printed rule, not blue pen."""
	hi, lo = max(red, green, blue), min(red, green, blue)
	return hi - lo < 22 and hi < 205 and lo < 195


def _clean_signature_image(image):
	"""Remove leftover underlines and dashed rules under handwriting. Pen pixels stay as they are."""
	if image.mode != "RGB":
		image = image.convert("RGB")
	pixels = image.load()
	width, height = image.size
	if width < 8 or height < 8:
		return image
	start = int(height * 0.45)
	for y in range(start, height):
		rule_xs = []
		pen = 0
		for x in range(width):
			red, green, blue = pixels[x, y]
			if _is_pen_ink(red, green, blue):
				pen += 1
			elif _is_printed_rule_pixel(red, green, blue):
				rule_xs.append(x)
		if not rule_xs:
			continue
		span = rule_xs[-1] - rule_xs[0] + 1
		if len(rule_xs) < max(6, int(width * 0.08)):
			continue
		if span < width * 0.18:
			continue
		if pen > len(rule_xs) * 0.5:
			continue
		for x in rule_xs:
			pixels[x, y] = (255, 255, 255)
	return image


def _flatten_signature_on_white(image):
	from PIL import Image

	if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
		rgba = image.convert("RGBA")
		bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
		return Image.alpha_composite(bg, rgba).convert("RGB")
	if image.mode != "RGB":
		return image.convert("RGB")
	return image


def _is_signature_mark(red: int, green: int, blue: int) -> bool:
	"""Any ink on a user-uploaded signature, including gray/black and faint pen."""
	if _is_pen_ink(red, green, blue) or _is_stamp_ink(red, green, blue):
		return True
	return min(red, green, blue) < 248


def _longest_ink_span(counts, minimum):
	"""Longest contiguous band with real ink, not first-to-last stray marks."""
	best = None
	start = None
	for idx, count in enumerate(counts):
		if count >= minimum:
			if start is None:
				start = idx
			continue
		if start is not None:
			run = (start, idx - 1)
			if best is None or run[1] - run[0] > best[1] - best[0]:
				best = run
			start = None
	if start is not None:
		run = (start, len(counts) - 1)
		if best is None or run[1] - run[0] > best[1] - best[0]:
			best = run
	if best:
		return best
	hits = [idx for idx, count in enumerate(counts) if count > 0]
	if not hits:
		return None
	return hits[0], hits[-1]


def _extend_span_through_ink(counts, start: int, end: int, empty_limit: int = 6):
	"""Keep thin strokes (the tail of g/y/j) that sit next to the main band."""
	left = start
	empty = 0
	for idx in range(start - 1, -1, -1):
		if counts[idx] > 0:
			left = idx
			empty = 0
		else:
			empty += 1
			if empty >= empty_limit:
				break
	right = end
	empty = 0
	for idx in range(end + 1, len(counts)):
		if counts[idx] > 0:
			right = idx
			empty = 0
		else:
			empty += 1
			if empty >= empty_limit:
				break
	return left, right


def _ink_bounding_box(image):
	"""Full handwriting including descenders, ignoring a distant stray tick."""
	width, height = image.size
	pixels = image.load()
	row_counts = [0] * height
	col_counts = [0] * width
	for y in range(height):
		for x in range(width):
			red, green, blue = pixels[x, y]
			if _is_signature_mark(red, green, blue):
				row_counts[y] += 1
				col_counts[x] += 1
	row_peak = max(row_counts) if row_counts else 0
	min_row = max(6, int(row_peak * 0.12))
	rows = _longest_ink_span(row_counts, min_row)
	if not rows:
		return None
	rows = _extend_span_through_ink(row_counts, rows[0], rows[1])
	band_cols = [0] * width
	for y in range(rows[0], rows[1] + 1):
		for x in range(width):
			red, green, blue = pixels[x, y]
			if _is_signature_mark(red, green, blue):
				band_cols[x] += 1
	hits = [idx for idx, count in enumerate(band_cols) if count > 0]
	if not hits:
		return None
	pad_x, pad_top, pad_bottom = 14, 12, 22
	return (
		max(0, hits[0] - pad_x),
		max(0, rows[0] - pad_top),
		min(width, hits[-1] + 1 + pad_x),
		min(height, rows[1] + 1 + pad_bottom),
	)


def _tight_content_crop(image):
	"""Crop empty margin only. Pixels are not recolored."""
	image = _flatten_signature_on_white(image)
	image = _clean_signature_image(image)
	box = _ink_bounding_box(image)
	if not box:
		return image
	if box[2] - box[0] < 8 or box[3] - box[1] < 8:
		return image
	return image.crop(box)


def _fit_signature_slot(image):
	"""Keep the original handwriting: full crop, no upscale, scale down only if huge."""
	from PIL import Image

	image = _flatten_signature_on_white(image)
	box = _ink_bounding_box(image)
	fitted = image.crop(box) if box else image
	src_w, src_h = fitted.size
	max_w, max_h = 640, 220
	scale = min(max_w / max(src_w, 1), max_h / max(src_h, 1), 1.0)
	if scale < 0.999:
		fitted = fitted.resize(
			(max(1, int(src_w * scale)), max(1, int(src_h * scale))),
			Image.Resampling.LANCZOS,
		)
	return fitted


def fit_payslip_signature_path(image_path: str | None) -> str | None:
	"""Same slot for HR, DAF, or MD. Returns a PNG path or the original on failure."""
	if not image_path or not os.path.exists(image_path):
		return image_path
	try:
		from PIL import Image

		fitted = _fit_signature_slot(Image.open(image_path))
		return _write_png(_png_bytes_from_image(fitted), "payslip-sign")
	except Exception:
		return image_path


def _page_scan_image(page):
	import io

	from PIL import Image

	if not page.images:
		return None
	picture = max(page.images, key=lambda image: len(image.data))
	image = Image.open(io.BytesIO(picture.data)).convert("RGB")
	rotation = int(page.get("/Rotate") or 0) % 360
	if rotation:
		image = image.rotate(360 - rotation, expand=True)
	return image


def _table_end_row(image) -> int:
	pixels = image.load()
	width, height = image.size
	last = int(height * 0.15)
	for y0 in range(0, int(height * 0.55), 8):
		dark = 0
		n = 0
		for y in range(y0, min(height, y0 + 8), 2):
			for x in range(0, width, 6):
				red, green, blue = pixels[x, y]
				n += 1
				if max(red, green, blue) < 95:
					dark += 1
		if n and dark / n > 0.04:
			last = y0 + 8
	return last


def _is_pen_ink(red: int, green: int, blue: int) -> bool:
	"""Handwritten blue/violet ink, not printed black text or rules."""
	hi, lo = max(red, green, blue), min(red, green, blue)
	if hi - lo >= 22 and blue >= red + 6 and blue >= green - 10 and hi < 225 and lo < 190:
		return True
	return hi < 70 and blue > red + 4 and blue > green + 2


def _is_stamp_ink(red: int, green: int, blue: int) -> bool:
	hi, lo = max(red, green, blue), min(red, green, blue)
	if hi - lo < 12 or hi >= 245:
		return False
	if green >= red - 4 and green > 55:
		return True
	if red > green + 10 and red > blue + 12:
		return True
	return False


def _bbox_matching(image, box: tuple[int, int, int, int], match) -> tuple[int, int, int, int]:
	pixels = image.load()
	left, top, right, bottom = box
	xs, ys = [], []
	for y in range(top, bottom):
		for x in range(left, right):
			red, green, blue = pixels[x, y]
			if match(red, green, blue):
				xs.append(x)
				ys.append(y)
	if not xs:
		return box
	pad = 5
	return (
		max(0, min(xs) - pad),
		max(0, min(ys) - pad),
		min(image.width, max(xs) + pad),
		min(image.height, max(ys) + pad),
	)


def _connected_ink_box(image, box: tuple[int, int, int, int], seed_fn) -> tuple[int, int, int, int]:
	"""Keep strokes attached to the signature/stamp, skip printed words and dashes below."""
	seed_box = _bbox_matching(image, box, seed_fn)
	left = max(0, seed_box[0] - 10)
	top = max(0, seed_box[1] - 8)
	right = min(image.width, seed_box[2] + 18)
	bottom = min(image.height, seed_box[3] + 4)
	pixels = image.load()
	width, height = right - left, bottom - top
	mask = [[False] * width for _ in range(height)]
	for y in range(top, bottom):
		for x in range(left, right):
			red, green, blue = pixels[x, y]
			if seed_fn(red, green, blue):
				mask[y - top][x - left] = True
	for _ in range(3):
		added = False
		for y in range(height):
			for x in range(width):
				if mask[y][x]:
					continue
				red, green, blue = pixels[x + left, y + top]
				if max(red, green, blue) > 200:
					continue
				near = False
				for dy in (-2, -1, 0, 1, 2):
					for dx in (-2, -1, 0, 1, 2):
						ny, nx = y + dy, x + dx
						if 0 <= ny < height and 0 <= nx < width and mask[ny][nx]:
							near = True
							break
					if near:
						break
				if near:
					mask[y][x] = True
					added = True
		if not added:
			break
	xs, ys = [], []
	for y in range(height):
		for x in range(width):
			if mask[y][x]:
				xs.append(x + left)
				ys.append(y + top)
	if not xs:
		return seed_box
	pad = 6
	return (
		max(0, min(xs) - pad),
		max(0, min(ys) - pad),
		min(image.width, max(xs) + pad),
		min(image.height, max(ys) + pad),
	)


def _colored_clusters(image, y_start: int, y_end: int) -> list[list]:
	pixels = image.load()
	width, _height = image.size
	points = []
	for y in range(max(0, y_start), min(image.height, y_end)):
		for x in range(width):
			red, green, blue = pixels[x, y]
			if _is_pen_ink(red, green, blue) or _is_stamp_ink(red, green, blue):
				points.append((x, y))
	if len(points) < 40:
		return []
	points.sort()
	clusters = [[points[0]]]
	for point in points[1:]:
		if point[0] - clusters[-1][-1][0] > 70:
			clusters.append([point])
		else:
			clusters[-1].append(point)
	return [cluster for cluster in clusters if len(cluster) > 80]


def _scan_signoff_crops(page) -> list[bytes]:
	"""Original pixels of the three sign-off marks under the payroll table."""
	image = _page_scan_image(page)
	if image is None:
		return []
	start = _table_end_row(image) + 8
	end = min(image.height, start + 320)
	clusters = _colored_clusters(image, start, end)
	if len(clusters) < 2:
		clusters = _colored_clusters(image, int(image.height * 0.18), int(image.height * 0.45))
	if len(clusters) < 2:
		return []
	crops = []
	for index, cluster in enumerate(clusters[:3]):
		xs = [point[0] for point in cluster]
		ys = [point[1] for point in cluster]
		box = (
			max(0, min(xs) - 8),
			max(0, min(ys) - 8),
			min(image.width, max(xs) + 8),
			min(image.height, max(ys) + 8),
		)
		if index < 2:
			box = _connected_ink_box(image, box, _is_pen_ink)
			crop = _clean_signature_image(image.crop(box))
			crops.append(_png_bytes_from_image(_tight_content_crop(crop)))
			continue
		else:
			search = (
				max(0, box[0]),
				max(0, box[1] - 20),
				min(image.width, box[2] + 36),
				min(image.height, box[3] + 36),
			)
			box = _bbox_matching(image, search, _is_stamp_ink)
			box = (
				max(0, box[0] - 6),
				max(0, box[1] - 16),
				min(image.width, box[2] + 18),
				min(image.height, box[3] + 18),
			)
		crops.append(_png_bytes_from_image(image.crop(box)))
	return crops


def _raw_sheet_crops(path: str) -> list[bytes]:
	"""Unmodified sign-off images from the signed payroll file, left to right."""
	if not path or not str(path).lower().endswith(".pdf"):
		return []
	from pypdf import PdfReader

	try:
		reader = PdfReader(path)
		if not reader.pages:
			return []
		page = reader.pages[0]
		scan_crops = _scan_signoff_crops(page)
		if len(scan_crops) >= 2:
			return scan_crops
		page_width = float(page.mediabox.width)
		page_height = float(page.mediabox.height)
		chunks = _pdf_text_chunks(page)
		headings = _heading_markers(chunks)
		images = _placed_images(page)
		large = [image for image in images if image["w"] >= page_width * 0.55]
		if headings and large:
			crops = []
			for heading in headings:
				blob = _crop_column_signature(large[0], heading, headings, page_width, page_height)
				if blob:
					crops.append(blob)
			if crops:
				return crops
		small = [image for image in images if image["w"] < page_width * 0.45 and image["h"] < page_height * 0.4]
		return [image["blob"] for image in sorted(small, key=lambda image: image["x"])[:3]]
	except Exception:
		frappe.log_error(title="Payslip signed payroll crops")
		return []


def _request_sheet_crops(doc) -> list[bytes]:
	for upload in _signed_payroll_uploads(doc):
		path = _file_path(upload.signed_payroll)
		if not path:
			continue
		if str(path).lower().endswith(".pdf"):
			crops = _raw_sheet_crops(path)
			if crops:
				return crops
		footer = _footer_signatures(upload.payroll_sheet_footer)
		try:
			found = _signatories_from_file(path, footer)
		except Exception:
			frappe.log_error(title="Payslip signed payroll images")
			continue
		blobs = [item.get("blob") for item in found if item.get("blob")]
		if blobs:
			return blobs
	return []


def _set_block_image(block: dict, blob: bytes, prefix: str) -> None:
	path = _write_png(_png_bytes(blob), prefix)
	block["image_path"] = path
	block["image_url"] = None


def _apply_sheet_signatures(doc, verified: dict | None, approved: dict | None) -> None:
	"""Copy the signed-payroll signature images as they are, in sheet order."""
	crops = _request_sheet_crops(doc)
	if not crops:
		return
	if verified and len(crops) >= 1:
		_set_block_image(verified, crops[0], "payslip-hr-sign")
	if approved and len(crops) >= 2:
		_set_block_image(approved, crops[1], "payslip-daf-sign")


def _cachet_from_blob(blob: bytes) -> bytes | None:
	"""Keep the full cachet. Fill Test-3 pen with nearby stamp colour, never white."""
	import io

	from PIL import Image

	try:
		image = Image.open(io.BytesIO(blob))
	except Exception:
		return None
	width, height = image.size
	if width < 8 or height < 8:
		return None
	if image.mode != "RGB":
		image = image.convert("RGB")
	pixels = image.load()

	def is_dark_pen(red: int, green: int, blue: int) -> bool:
		luma = 0.299 * red + 0.587 * green + 0.114 * blue
		return luma < 148 and blue >= red + 18 and blue >= green + 10 and green < 170 and red < 165

	pen = [[is_dark_pen(*pixels[x, y]) for x in range(width)] for y in range(height)]
	for y in range(height):
		for x in range(width):
			if not pen[y][x]:
				continue
			samples = []
			for dy in range(-5, 6):
				for dx in range(-5, 6):
					nx, ny = x + dx, y + dy
					if 0 <= nx < width and 0 <= ny < height and not pen[ny][nx]:
						samples.append(pixels[nx, ny])
			if samples:
				pixels[x, y] = tuple(sum(channel[i] for channel in samples) // len(samples) for i in range(3))
	return _png_bytes_from_image(image)


def _png_bytes_from_image(image) -> bytes:
	import io

	if image.mode not in ("RGB", "RGBA"):
		image = image.convert("RGB")
	buffer = io.BytesIO()
	image.save(buffer, format="PNG")
	return buffer.getvalue()


def user_can_manage_cachet(user: str | None = None) -> bool:
	from hrms.payroll.payroll_import.payroll_access import HR_PAYROLL_ROLES

	user = user or frappe.session.user
	if user in ("Guest",):
		return False
	if user == "Administrator":
		return True
	return bool(HR_PAYROLL_ROLES & set(frappe.get_roles(user)))


def _throw_if_cannot_manage_cachet() -> None:
	if not user_can_manage_cachet():
		frappe.throw(_("Only HR can add the payslip cachet."), frappe.PermissionError)


def get_payroll_cachet_path() -> str | None:
	"""Stamp uploaded with Add Cachet, not a crop from the signed payroll scan."""
	url = None
	if frappe.get_meta("Payroll Settings").has_field("payroll_cachet"):
		url = frappe.db.get_single_value("Payroll Settings", "payroll_cachet")
	path = signature_image_path(url) if url else None
	if path:
		return path
	rows = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Payroll Settings"},
		fields=["file_url", "file_name"],
		order_by="modified desc",
		limit=20,
	)
	for row in rows:
		label = f"{row.file_name or ''} {row.file_url or ''}".lower()
		if "cachet" in label or "stamp" in label:
			path = signature_image_path(row.file_url)
			if path:
				return path
	return None


@frappe.whitelist()
def save_payroll_cachet(file_url: str):
	"""Attach an uploaded stamp and use it on approved / downloadable payslips."""
	_throw_if_cannot_manage_cachet()
	file_url = (file_url or "").strip()
	if not file_url:
		frappe.throw(_("Please choose a cachet image."))
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("Could not find the uploaded cachet file."))
	file_doc = frappe.get_doc("File", file_name)
	old = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Payroll Settings",
			"attached_to_name": "Payroll Settings",
			"name": ["!=", file_doc.name],
		},
		pluck="name",
	)
	for name in old:
		label = (frappe.db.get_value("File", name, "file_name") or "").lower()
		if "cachet" in label or "stamp" in label or (
			frappe.get_meta("Payroll Settings").has_field("payroll_cachet")
			and frappe.db.get_value("File", name, "attached_to_field") == "payroll_cachet"
		):
			frappe.delete_doc("File", name, ignore_permissions=True, force=1)
	file_doc.attached_to_doctype = "Payroll Settings"
	file_doc.attached_to_name = "Payroll Settings"
	file_doc.attached_to_field = "payroll_cachet"
	file_doc.file_name = file_doc.file_name or "payroll-cachet.png"
	if "cachet" not in (file_doc.file_name or "").lower():
		base, ext = os.path.splitext(file_doc.file_name)
		file_doc.file_name = f"payroll-cachet{ext or '.png'}"
	file_doc.flags.ignore_permissions = True
	file_doc.save()
	if frappe.get_meta("Payroll Settings").has_field("payroll_cachet"):
		frappe.db.set_value(
			"Payroll Settings",
			"Payroll Settings",
			"payroll_cachet",
			file_doc.file_url,
			update_modified=False,
		)
	return {"file_url": file_doc.file_url, "file_name": file_doc.file_name}


def _cachet_block(doc) -> dict | None:
	"""Company cachet from Add Cachet, used on preview, approval, and download."""
	path = get_payroll_cachet_path()
	if not path:
		return None
	return {
		"heading": "",
		"name": "",
		"title": "",
		"approved_on": "",
		"image_path": path,
		"is_cachet": True,
	}


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
	file_url = str(file_url).strip()
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		base = os.path.basename(file_url.split("?", 1)[0])
		if base:
			file_name = frappe.db.get_value("File", {"file_name": base}, "name")
	if file_name:
		path = frappe.get_doc("File", file_name).get_full_path()
		if path and os.path.exists(path):
			return path
		rooted = os.path.abspath(os.path.join(frappe.utils.get_bench_path(), "sites", str(path or "").lstrip("./")))
		if os.path.exists(rooted):
			return rooted

	rel = file_url.split("?", 1)[0].lstrip("/")
	base = os.path.basename(rel)
	candidates = [
		frappe.get_site_path("public", rel),
		frappe.get_site_path("private", "files", base),
		frappe.get_site_path("public", "files", base),
		os.path.join(frappe.utils.get_site_path(), rel),
	]
	for path in candidates:
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
	image_url = row.get("payroll_signature")
	image_path = signature_image_path(image_url)
	if not image_path:
		attached = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "User", "attached_to_name": user},
			fields=["file_url", "file_name"],
			order_by="creation desc",
			limit=20,
		)
		for item in attached:
			label = f"{item.file_name or ''} {item.file_url or ''}".lower()
			if "sign" in label or "payroll" in label:
				image_path = signature_image_path(item.file_url)
				if image_path:
					image_url = item.file_url
					break
	if image_path and not image_url:
		image_url = row.get("payroll_signature")
	if not image_path:
		image_url = None
	else:
		image_path = fit_payslip_signature_path(image_path)
		image_url = None
	return {
		"heading": heading,
		"name": row.get("full_name") or user,
		"title": row.get("payroll_signatory_title") or "",
		"approved_on": when,
		"image_path": image_path,
		"image_url": image_url,
	}


def signoff_for_request(doc) -> dict | None:
	"""Signatures of the two people who actually approved this request."""
	flow = (getattr(doc, "approval_flow", None) or "Staff").strip()
	if flow == "HR":
		verified_user, verified_on = doc.daf_approved_by, doc.daf_approved_on
		approved_user, approved_on = getattr(doc, "md_approved_by", None), getattr(
			doc, "md_approved_on", None
		)
	elif flow == "DAF":
		verified_user, verified_on = doc.hr_approved_by, doc.hr_approved_on
		approved_user, approved_on = getattr(doc, "md_approved_by", None), getattr(
			doc, "md_approved_on", None
		)
	else:
		verified_user, verified_on = doc.hr_approved_by, doc.hr_approved_on
		approved_user, approved_on = doc.daf_approved_by, doc.daf_approved_on
	if not verified_user and doc.status == "Approved" and doc.approved_by and not approved_user:
		verified_user = doc.approved_by
		verified_on = doc.approved_on
	verified = _block(verified_user, verified_on, "Verified by")
	approved = _block(approved_user, approved_on, "Approved by")
	cachet = _cachet_block(doc)
	if not verified and not approved:
		return None
	return {"verified_by": verified, "approved_by": approved, "cachet": cachet}
