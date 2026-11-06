import frappe

frappe.connect()
for name in ("Payroll Excel Upload", "Imported Payroll Record"):
	print(name, "->", frappe.db.exists("DocType", name))
