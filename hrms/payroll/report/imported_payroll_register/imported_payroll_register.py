# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import getdate

from hrms.payroll.payroll_import.payroll_month_export import EXPORT_COLUMNS


def execute(filters=None):
	filters = filters or {}
	columns = _get_columns()
	data = _get_data(filters)
	return columns, data


def _get_columns():
	columns = [
		{
			"label": _("ID Number"),
			"fieldname": "employee_id_number",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Employee Name"),
			"fieldname": "employee_name",
			"fieldtype": "Data",
			"width": 140,
		},
	]
	for fieldname, label in EXPORT_COLUMNS[2:]:
		fieldtype = "Date" if fieldname == "date_of_joining" else "Currency"
		if fieldname in ("position", "account_number", "bank"):
			fieldtype = "Data"
		columns.append(
			{
				"label": _(label),
				"fieldname": fieldname,
				"fieldtype": fieldtype,
				"width": 120,
			}
		)
	return columns


def _get_data(filters):
	if not filters.get("payroll_month") and not (
		filters.get("from_month") and filters.get("to_month")
	):
		frappe.throw(_("Set Payroll Month or both From Month and To Month."))

	query_filters = {"docstatus": 1}
	if filters.get("company"):
		query_filters["company"] = filters["company"]

	if filters.get("from_month") and filters.get("to_month"):
		query_filters["payroll_month"] = [
			"between",
			[getdate(filters["from_month"]), getdate(filters["to_month"])],
		]
	elif filters.get("payroll_month"):
		query_filters["payroll_month"] = getdate(filters["payroll_month"])

	fields = ["employee_id_number", "employee_name"] + [f[0] for f in EXPORT_COLUMNS[2:]]

	return frappe.get_all(
		"Imported Payroll Record",
		filters=query_filters,
		fields=fields,
		order_by="payroll_month desc, employee_id_number asc",
	)
