import frappe

frappe.init(site="mysite.local")
frappe.connect()

company = "Muganga Sacco"
meta = frappe.get_meta("Company")
print("Company fields with logo:", [f.fieldname for f in meta.fields if "logo" in f.fieldname.lower()])
print("default_letter_head:", frappe.db.get_value("Company", company, "default_letter_head"))

from hrms.payroll.payroll_import.payroll_sheet_layout import (
	get_company_logo_url,
	get_company_logo_path,
)

print("logo_url:", get_company_logo_url(company))
print("logo_path:", get_company_logo_path(company))
