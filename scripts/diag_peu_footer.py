import json
import sys

sys.path.insert(0, "/home/wngelique/frappe-bench/apps/hrms")
import frappe

frappe.init(site="mysite.local", sites_path="sites")
frappe.connect()

company = "Muganga Sacco"
month = "2026-06-01"

peus = frappe.get_all(
	"Payroll Excel Upload",
	filters={"company": company},
	fields=["name", "payroll_month", "status", "payroll_sheet_logo", "payroll_sheet_footer", "modified"],
	order_by="modified desc",
)
print("PEU count", len(peus))
for p in peus:
	print("---", p.name, p.status, p.payroll_month, "logo", bool(p.payroll_sheet_logo))
	footer = p.payroll_sheet_footer
	if footer:
		print("footer", footer if isinstance(footer, str) else json.dumps(footer)[:300])

rec = frappe.get_all(
	"Imported Payroll Record",
	filters={"company": company, "payroll_month": month, "docstatus": 1},
	fields=["name", "payroll_excel_upload"],
	limit=1,
)
print("sample record upload", rec)

from hrms.payroll.payroll_import.payroll_sheet_layout import (
	get_payroll_excel_upload_for_month,
	get_payroll_sheet_footer,
	get_company_logo_url,
)

peu = get_payroll_excel_upload_for_month(company, month)
print("lookup peu", peu)
print("logo_url", get_company_logo_url(company, peu))
print("footer", get_payroll_sheet_footer(company, payroll_month=month, payroll_excel_upload=peu))
