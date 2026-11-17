import frappe


def execute():
	if not frappe.db.table_exists("Payroll Excel Upload"):
		return
	frappe.db.sql(
		"""
		UPDATE `tabPayroll Excel Upload`
		SET status = 'Approved'
		WHERE status = 'Imported'
		"""
	)
