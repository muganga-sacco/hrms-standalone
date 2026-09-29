# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import re
from datetime import date

from frappe.utils import get_first_day, getdate


def normalize_payroll_month(value) -> date | None:
	"""Map any date in a calendar month to the 1st (stored payroll month)."""
	if not value:
		return None
	return getdate(get_first_day(getdate(value)))


def normalize_employee_id_number(value: str | None) -> str:
	"""Normalize desk / URL input to match Imported Payroll Record employee_id_number.

	Any non-empty ID is kept as-is after trim/collapse spaces. MSID-prefixed numeric IDs
	(e.g. MSID003 vs MSID 003) are spaced consistently so lookups match import data.
	"""
	text = (value or "").strip().replace("+", " ")
	text = re.sub(r"\s+", " ", text)
	if not text:
		return ""
	match = re.match(r"^(MSID)\s*(\d+)$", text, re.I)
	if match:
		return f"MSID {match.group(2)}"
	return text


def payroll_period_label_for_month(value) -> str | None:
	month = normalize_payroll_month(value)
	if not month:
		return None
	return month.strftime("%B %Y")
