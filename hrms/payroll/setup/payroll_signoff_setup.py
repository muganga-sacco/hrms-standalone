# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""User signature fields and payslip-request status names for Payroll Sign-off."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_payroll_signoff():
	create_custom_fields(
		{
			"User": [
				{
					"fieldname": "payroll_signoff_section",
					"label": "Payroll Sign-off",
					"fieldtype": "Section Break",
					"insert_after": "bio",
					"collapsible": 1,
				},
				{
					"fieldname": "payroll_signature",
					"label": "Signature",
					"fieldtype": "Attach Image",
					"insert_after": "payroll_signoff_section",
					"description": "PNG of your signature. Printed on a payslip when you approve it.",
				},
				{
					"fieldname": "payroll_signatory_title",
					"label": "Signatory Title",
					"fieldtype": "Data",
					"insert_after": "payroll_signature",
					"description": "Title printed under your name on the payslip.",
				},
			]
		},
		update=True,
	)
	if frappe.db.table_exists("Payslip Request"):
		frappe.db.sql(
			"""update `tabPayslip Request` set status = 'Pending HR' where status = 'Pending'"""
		)
	frappe.db.commit()
