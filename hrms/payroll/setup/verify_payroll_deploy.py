# Run on the server bench after deploy:
#   bench --site <your-site> execute hrms.payroll.setup.verify_payroll_deploy.verify

from __future__ import annotations

import os

import frappe


def verify() -> dict:
	"""Smoke-check that custom payroll code is present on this bench."""
	from hrms.payroll.payroll_import import payslip_docx
	from hrms.payroll.payroll_import.payroll_month_utils import normalize_employee_id_number

	app_path = frappe.get_app_path("hrms")
	checks = {
		"hrms_in_installed_apps": "hrms" in frappe.get_installed_apps(),
		"app_path": app_path,
		"payslip_template_exists": os.path.isfile(
			os.path.join(app_path, "payroll", "templates", "payslip_template.docx")
		),
		"payslip_table_cols": getattr(payslip_docx, "PAYSLIP_TABLE_COLS", None),
		"has_payslip_get_all": hasattr(payslip_docx, "_payslip_get_all"),
		"normalize_msid003": normalize_employee_id_number("MSID003"),
		"page_staff_payroll_dashboard": bool(frappe.db.exists("Page", "staff-payroll-dashboard")),
		"doctype_payslip_request": bool(frappe.db.exists("DocType", "Payslip Request")),
		"doctype_imported_payroll": bool(frappe.db.exists("DocType", "Imported Payroll Record")),
	}

	try:
		import docx  # noqa: F401

		checks["python_docx"] = True
	except ImportError:
		checks["python_docx"] = False

	checks["ok"] = all(
		checks.get(k)
		for k in (
			"hrms_in_installed_apps",
			"payslip_template_exists",
			"python_docx",
			"page_staff_payroll_dashboard",
			"doctype_payslip_request",
			"doctype_imported_payroll",
		)
	) and checks.get("payslip_table_cols") == 14

	return checks
