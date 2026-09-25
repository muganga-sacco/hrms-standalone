# bench --site mysite.local execute hrms.payroll.setup.test_payslip_download.run

import frappe


def run():
	from hrms.payroll.doctype.imported_payroll_record.imported_payroll_record import (
		_send_payslip_docx_response,
	)

	out = {}
	for user in ("payroll.hr@mysite.local", "payroll.employee1@mysite.local"):
		frappe.set_user(user)
		try:
			_send_payslip_docx_response(
				employee_id_number="MSID 003",
				payroll_month="2026-09-01",
			)
			out[user] = {
				"ok": True,
				"bytes": len(frappe.local.response.filecontent or b""),
			}
		except Exception as e:
			out[user] = {"ok": False, "error": str(e)}
	return out
