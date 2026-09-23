import sys

sys.path.insert(0, "/home/wngelique/frappe-bench/apps/hrms")
from hrms.payroll.payroll_import.payroll_excel_parser import parse_payroll_excel

path = "/home/wngelique/frappe-bench/sites/mysite.local/private/files/Payroll in HRS.xlsx"
parsed = parse_payroll_excel(path)
print("column_map:", parsed.get("column_map"))
for r in parsed.get("records") or []:
	if "003" in str(r.get("employee_id_number")):
		print("MSID 003:", {k: r[k] for k in sorted(r) if k not in ("payroll_period_label", "payroll_month")})
