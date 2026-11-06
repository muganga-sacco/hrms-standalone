import sys

sys.path.insert(0, "/mnt/c/Angelique Uwibambe/MS/hrms-standalone")
from hrms.payroll.payroll_import.payroll_excel_parser import parse_payroll_excel

path = "/home/wngelique/frappe-bench/sites/mysite.local/private/files/Payroll in HRS.xlsx"
parsed = parse_payroll_excel(path)
cm = parsed.get("column_map") or {}
for f in (
	"paye",
	"pension_employee",
	"pension_employer",
	"oh_employer",
	"maternity_employee",
	"maternity_employer",
	"transport_allowance",
	"itc_allowance",
	"ict_allowance",
):
	print(f, cm.get(f))
for r in parsed.get("records") or []:
	if "003" in str(r.get("employee_id_number")):
		print(
			"MSID003",
			"paye",
			r.get("paye"),
			"pen_emp",
			r.get("pension_employee"),
			"pen_er",
			r.get("pension_employer"),
			"oh",
			r.get("oh_employer"),
			"mat_emp",
			r.get("maternity_employee"),
			"mat_er",
			r.get("maternity_employer"),
		)
