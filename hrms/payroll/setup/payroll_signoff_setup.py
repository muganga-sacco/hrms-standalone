# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""User signature fields and payslip-request status names for Payroll Sign-off."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_payroll_signoff():
	create_custom_fields(
		{
			"Payroll Settings": [
				{
					"fieldname": "payslip_cachet_section",
					"label": "Payslip Cachet",
					"fieldtype": "Section Break",
					"insert_after": "process_payroll_accounting_entry_based_on_employee",
					"collapsible": 0,
				},
				{
					"fieldname": "payroll_cachet",
					"label": "Cachet",
					"fieldtype": "Attach Image",
					"insert_after": "payslip_cachet_section",
					"description": "Company stamp used on approved payslips. Add it with the Add Cachet command.",
				},
				{
					"fieldname": "payslip_email_section",
					"label": "Payslip Request Emails",
					"fieldtype": "Section Break",
					"insert_after": "payroll_cachet",
				},
				{
					"fieldname": "enable_payslip_request_emails",
					"label": "Send payslip request emails",
					"fieldtype": "Check",
					"insert_after": "payslip_email_section",
					"default": "1",
					"description": "Email HR when a request is submitted, and email DAF when HR has approved.",
				},
				{
					"fieldname": "payslip_email_account",
					"label": "From Email Account",
					"fieldtype": "Link",
					"options": "Email Account",
					"insert_after": "enable_payslip_request_emails",
					"description": "Outgoing account used as From. SMTP host, From address, and app password are set on this Email Account (Desk → Email Account).",
				},
				{
					"fieldname": "hr_payslip_notification_emails",
					"label": "HR notification emails",
					"fieldtype": "Small Text",
					"insert_after": "payslip_email_account",
					"description": "One or more addresses, comma or new line. If empty, all enabled users with role HR Manager or HR User are emailed.",
				},
				{
					"fieldname": "daf_payslip_notification_emails",
					"label": "DAF notification emails",
					"fieldtype": "Small Text",
					"insert_after": "hr_payslip_notification_emails",
					"description": "One or more addresses, comma or new line. If empty, all enabled users with role DAF are emailed.",
				},
			],
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
	from hrms.payroll.setup.ensure_payroll_dashboard_permissions import (
		_ensure_payslip_request_pending_badge,
	)

	_ensure_payslip_request_pending_badge()
	frappe.db.commit()
