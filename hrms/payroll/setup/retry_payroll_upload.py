# bench --site mysite.local execute hrms.payroll.setup.retry_payroll_upload.run --kwargs '{"docname": "HR-PEU-2026-00022"}'

import frappe


def run(docname: str = "HR-PEU-2026-00022"):
	from hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload import import_payroll_excel

	return import_payroll_excel(docname)
