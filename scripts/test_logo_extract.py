import sys

sys.path.insert(0, "/home/wngelique/frappe-bench/apps/hrms")
from hrms.payroll.payroll_import.payroll_sheet_layout import extract_first_image_from_workbook

path = "/home/wngelique/frappe-bench/sites/mysite.local/private/files/Payroll in HRS.xlsx"
r = extract_first_image_from_workbook(path)
print("extracted", len(r[0]) if r else None, r[1] if r else None)
