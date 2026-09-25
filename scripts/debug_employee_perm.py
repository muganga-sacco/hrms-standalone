import frappe
from frappe.permissions import get_role_permissions

user = "payroll.employee1@mysite.local"
frappe.set_user(user)
u = frappe.get_doc("User", user)
print("user_type", u.user_type)
print("roles", [r.role for r in u.roles])
meta = frappe.get_meta("Payslip Request")
print("role_permissions", get_role_permissions(meta, user=user))
print("has_permission create", frappe.has_permission("Payslip Request", "create"))
print("blocked", frappe.get_all("Block Module", filters={"parent": user}, pluck="module"))
