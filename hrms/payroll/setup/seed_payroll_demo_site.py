# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Seed a site with payroll Excel imports and test users (bench execute only).

Example (after site has basic + hrms and a Company):

  bench --site hr-management.local execute "frappe.get_attr('hrms.payroll.setup.seed_payroll_demo_site.seed_payroll_demo_site')()" --kwargs "{
    'staff_excel_path': '/home/msacco/payroll/STAFF.xlsx',
    'lumpsum_excel_path': '/home/msacco/payroll/LUMPSUM.xlsx'
  }"
"""

from __future__ import annotations

from pathlib import Path

import frappe

from hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload import import_payroll_excel
from hrms.payroll.setup.create_payroll_test_users import create_payroll_test_users


def _import_excel_file(file_path: str) -> dict:
	path = Path(file_path)
	if not path.is_file():
		frappe.throw(f"File not found: {file_path}")

	company = frappe.db.get_value("Company", {"name": "Muganga Sacco"}, "name") or frappe.db.get_value(
		"Company", {}, "name"
	)
	if not company:
		frappe.throw("Create a Company on this site before seeding payroll (Setup → Company).")

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
	count = frappe.db.count("Imported Payroll Record", {"docstatus": 1, "payroll_month": doc.payroll_month})
	return {
		"upload": doc.name,
		"payroll_month": str(doc.payroll_month),
		"import": result,
		"submitted_rows_for_month": count,
	}


@frappe.whitelist()
def seed_payroll_demo_site(
	staff_excel_path: str | None = None,
	lumpsum_excel_path: str | None = None,
	password: str | None = None,
) -> dict:
	"""Import optional staff/lumpsum files, then create payroll test users."""
	frappe.only_for("Administrator")
	frappe.set_user("Administrator")

	out: dict = {"imports": {}, "row_counts": {}}
	if staff_excel_path:
		out["imports"]["staff"] = _import_excel_file(staff_excel_path)
	if lumpsum_excel_path:
		out["imports"]["lumpsum"] = _import_excel_file(lumpsum_excel_path)

	out["row_counts"]["total_submitted"] = frappe.db.count("Imported Payroll Record", {"docstatus": 1})
	out["users"] = create_payroll_test_users(password)
	frappe.db.commit()
	return out
