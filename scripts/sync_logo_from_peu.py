"""Run: cd ~/frappe-bench && ./env/bin/python check_sync_logo.py (copy this file there)."""
import frappe

frappe.init(site="mysite.local", sites_path="sites")
frappe.connect()

from hrms.payroll.payroll_import.payroll_sheet_layout import (
	get_company_logo_url,
	sync_company_logo_from_payroll_excel,
)

company = "Muganga Sacco"
peu = frappe.db.get_value(
	"Payroll Excel Upload",
	{"company": company, "status": "Imported"},
	["name", "payroll_file"],
	as_dict=True,
)
if not peu:
	print("No imported Payroll Excel Upload found")
else:
	path = frappe.get_doc("File", {"file_url": peu.payroll_file}).get_full_path()
	ok = sync_company_logo_from_payroll_excel(path, company)
	print("sync_ok:", ok, "logo_url:", get_company_logo_url(company))
