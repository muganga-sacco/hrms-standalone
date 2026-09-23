import glob
import os
import sys

sys.path.insert(0, "/home/wngelique/frappe-bench/apps/hrms")
from hrms.payroll.payroll_import.payroll_excel_parser import parse_payroll_excel

base = "/home/wngelique/frappe-bench/sites/mysite.local/private/files"
paths = glob.glob(base + "/Payroll in HRSe*.xlsx") + glob.glob(base + "/Payroll*.xlsx")
for path in sorted(set(paths)):
    try:
        parsed = parse_payroll_excel(path)
        print(os.path.basename(path), "->", parsed.get("payroll_period_label"), parsed.get("payroll_month"), "rows", len(parsed.get("records") or []))
    except Exception as e:
        print(os.path.basename(path), "ERROR", e)
