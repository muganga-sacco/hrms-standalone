# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

from pathlib import Path

import frappe

from hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload import import_payroll_excel


@frappe.whitelist()
def run_lumpsum_import_test(file_path: str) -> dict:
	"""Attach LUMPSUM.xlsx and import (Administrator / bench execute only)."""
	frappe.only_for("Administrator")
	path = Path(file_path)
	if not path.is_file():
		frappe.throw(f"File not found: {file_path}")

	company = frappe.db.get_value("Company", {"name": "Muganga Sacco"}, "name") or frappe.db.get_value(
		"Company", {}, "name"
	)
	from frappe.utils.file_manager import save_file

	doc = frappe.new_doc("Payroll Excel Upload")
	doc.company = company
	doc.payroll_sheet_type = "Auto Detect"
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)

	save_file(path.name, path.read_bytes(), "Payroll Excel Upload", doc.name, is_private=1)
	doc.reload()
	doc.payroll_file = frappe.db.get_value("File", {"attached_to_name": doc.name}, "file_url")
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	result = import_payroll_excel(doc.name)
	count = frappe.db.count(
		"Imported Payroll Record", {"payroll_sheet_type": "Lumpsum", "docstatus": 1, "payroll_month": doc.payroll_month}
	)
	return {"upload": doc.name, "import": result, "lumpsum_rows_for_month": count}
