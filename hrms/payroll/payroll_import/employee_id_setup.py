"""Show Employee.employee_number beside the system ID. The value stays in its own column."""

from __future__ import annotations

import json

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

EMPLOYEE_ID_LABEL = "Employee Number"


def ensure_employee_id_field() -> None:
	if not frappe.db.exists("DocType", "Employee"):
		return
	if not frappe.get_meta("Employee").get_field("employee_number"):
		return

	_set_employee_id_properties()
	_place_employee_id_beside_series()
	_show_employee_id_in_list()
	frappe.clear_cache(doctype="Employee")


def _set_employee_id_properties() -> None:
	setters = (
		("hidden", "0", "Check"),
		("read_only", "0", "Check"),
		("reqd", "0", "Check"),
		("in_list_view", "1", "Check"),
		("in_standard_filter", "1", "Check"),
		("allow_in_quick_entry", "1", "Check"),
		("label", EMPLOYEE_ID_LABEL, "Data"),
		("description", "", "Text"),
	)
	for prop, value, property_type in setters:
		make_property_setter(
			"Employee",
			"employee_number",
			prop,
			value,
			property_type,
			validate_fields_for_doctype=False,
		)

	make_property_setter(
		"Employee",
		None,
		"search_fields",
		"employee_name, employee_number",
		"Data",
		for_doctype=True,
		validate_fields_for_doctype=False,
	)


def _place_employee_id_beside_series() -> None:
	"""Put Employee ID directly under the system series on the form."""
	rows = frappe.get_all(
		"DocField",
		filters={"parent": "Employee"},
		fields=["name", "fieldname"],
		order_by="idx asc",
	)
	names = [row.fieldname for row in rows]
	if "employee_number" not in names or "naming_series" not in names:
		return
	names.remove("employee_number")
	names.insert(names.index("naming_series") + 1, "employee_number")
	by_name = {row.fieldname: row.name for row in rows}
	for idx, fieldname in enumerate(names, start=1):
		frappe.db.set_value("DocField", by_name[fieldname], "idx", idx, update_modified=False)


def _show_employee_id_in_list() -> None:
	"""Place Employee ID immediately before the system ID column."""
	column = {"label": EMPLOYEE_ID_LABEL, "fieldname": "employee_number"}
	if frappe.db.exists("List View Settings", "Employee"):
		doc = frappe.get_doc("List View Settings", "Employee")
		fields = frappe.parse_json(doc.fields) or []
	else:
		doc = frappe.new_doc("List View Settings")
		doc.name = "Employee"
		fields = [
			{"label": "Full Name", "fieldname": "employee_name"},
			{"type": "Status", "label": "Status", "fieldname": "status_field"},
			{"label": "Designation", "fieldname": "designation"},
		]

	fields = [field for field in fields if field.get("fieldname") != "employee_number"]
	fields.append(column)
	doc.fields = json.dumps(fields)
	# Subject, tag, and the saved columns, plus the appended ID column.
	doc.total_fields = max(int(doc.total_fields or 0), len(fields) + 2)
	doc.flags.ignore_permissions = True
	doc.save()
