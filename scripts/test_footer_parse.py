import sys

sys.path.insert(0, "/home/wngelique/frappe-bench/apps/hrms")
from hrms.payroll.payroll_import.payroll_excel_parser import parse_payroll_excel

path = "/home/wngelique/frappe-bench/sites/mysite.local/private/files/Payroll in HRS.xlsx"
parsed = parse_payroll_excel(path)
print(parsed.get("sheet_footer"))
