"""Import LUMPSUM Excel via Payroll Excel Upload (run from bench env).

Usage:
  cd ~/frappe-bench
  ./env/bin/python /mnt/c/Angelique\\ Uwibambe/MS/hrms-standalone/scripts/run_lumpsum_import.py [path/to/LUMPSUM.xlsx]
"""
from __future__ import annotations

import sys
from pathlib import Path

import frappe

from hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload import import_payroll_excel


def main() -> None:
	frappe.init(site="mysite.local", sites_path="sites")
	frappe.connect()
	frappe.set_user("Administrator")

	path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
	if not path or not path.is_file():
		raise SystemExit(f"File not found: {path}")

	company = frappe.db.get_value("Company", {"name": "Muganga Sacco"}, "name") or frappe.db.get_value(
		"Company", {}, "name"
	)
	if not company:
		raise SystemExit("No Company found on site")

	doc = frappe.get_doc(
		{
			"doctype": "Payroll Excel Upload",
			"company": company,
			"payroll_sheet_type": "Auto Detect",
		}
	)
	doc.insert(ignore_permissions=True)

	from frappe.utils.file_manager import save_file

	save_file(path.name, path.read_bytes(), "Payroll Excel Upload", doc.name, is_private=1)
	doc.reload()
	file_url = frappe.db.get_value("File", {"attached_to_name": doc.name}, "file_url")
	doc.payroll_file = file_url
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	result = import_payroll_excel(doc.name)
	print("upload:", doc.name)
	print("company:", company)
	print("result:", result)

	count = frappe.db.count("Imported Payroll Record", {"payroll_sheet_type": "Lumpsum", "docstatus": 1})
	print("lumpsum_records_submitted:", count)


if __name__ == "__main__":
	main()
