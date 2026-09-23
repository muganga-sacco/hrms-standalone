import sys

sys.path.insert(0, "/home/wngelique/frappe-bench/apps/hrms")
import frappe

frappe.init(site="mysite.local")
frappe.connect()
from hrms.payroll.payroll_import.payroll_month_export import build_payroll_month_excel

data = build_payroll_month_excel("2026-06-01", "Muganga Sacco")
print("bytes", len(data))
