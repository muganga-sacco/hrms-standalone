# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors

# License: GNU General Public License v3. See license.txt



from __future__ import annotations



import frappe

from frappe import _

from frappe.model.document import Document

from frappe.utils import getdate, now_datetime



from hrms.payroll.payroll_import.payroll_access import (

	get_logged_in_employee,

	throw_if_not_hr_payroll,

	user_can_request_own_payslip,

	user_has_hr_payroll_access,

)





class PayslipRequest(Document):

	def validate(self):

		self._set_employee_for_self_service()

		self._validate_period_fields()

		if self.employee and not self.employee_id_number:

			self.employee_id_number = frappe.db.get_value(

				"Employee", self.employee, "employee_number"

			)



	def _set_employee_for_self_service(self) -> None:

		if user_has_hr_payroll_access() or frappe.flags.in_install:

			return

		if not user_can_request_own_payslip():

			return

		own_employee = get_logged_in_employee()

		if not own_employee:

			frappe.throw(_("Your user is not linked to an Employee record."))

		if self.employee and self.employee != own_employee:

			frappe.throw(_("You can only request a payslip for yourself."))

		self.employee = own_employee



	def _validate_period_fields(self) -> None:

		if self.status not in ("Draft", "Pending"):

			return

		pt = self.period_type

		if pt == "Last N months" and not self.months:

			frappe.throw(_("Number of months is required."))

		if pt == "Single payroll month" and not self.payroll_month:

			frappe.throw(_("Payroll month is required."))

		if pt == "From month – To month":

			if not self.from_month or not self.to_month:

				frappe.throw(_("From month and To month are required."))

			if getdate(self.from_month) > getdate(self.to_month):

				frappe.throw(_("From month cannot be after To month."))





def _own_payslip_rules(doc, ptype: str, user: str, employee: str | None) -> bool:

	if not employee:

		return ptype == "create"

	if not doc:

		return ptype in ("create", "read")

	if doc.employee != employee:

		return False

	if ptype in ("export", "delete"):

		return False

	if ptype == "write" and doc.status not in ("Draft", "Pending"):

		return False

	return True





def get_permission_query_conditions(user: str) -> str:

	if user_has_hr_payroll_access(user):

		return ""

	if not user_can_request_own_payslip(user):

		return "1=0"

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

	if not employee:

		return "1=0"

	return f"`tabPayslip Request`.employee = {frappe.db.escape(employee)}"





def has_permission(doc, ptype: str, user: str) -> bool:

	if user_has_hr_payroll_access(user):

		if ptype == "export":

			return True

		return True

	if not user_can_request_own_payslip(user):

		return False

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

	return _own_payslip_rules(doc, ptype, user, employee)





@frappe.whitelist()

def get_self_employee_for_payslip_request():

	"""Return the Employee linked to the logged-in user (for new payslip requests)."""

	if user_has_hr_payroll_access():

		return None

	if not user_can_request_own_payslip():

		return None

	employee = get_logged_in_employee()

	if not employee:

		return None

	return frappe.db.get_value(

		"Employee",

		employee,

		["name", "employee_name", "employee_number", "company"],

		as_dict=True,

	)





def _get_request_doc(docname: str) -> Document:

	doc = frappe.get_doc("Payslip Request", docname)

	if not frappe.has_permission("Payslip Request", "read", doc=doc):

		frappe.throw(_("Not permitted"), frappe.PermissionError)

	return doc





def _user_may_act_on_own_request(doc: Document) -> bool:

	if user_has_hr_payroll_access():

		return True

	own = get_logged_in_employee()

	return bool(own and doc.employee == own)





@frappe.whitelist()

def submit_payslip_request(docname: str):

	doc = _get_request_doc(docname)

	if doc.status != "Draft":

		frappe.throw(_("Only draft requests can be submitted."))

	if not _user_may_act_on_own_request(doc):

		frappe.throw(_("Not permitted"), frappe.PermissionError)

	doc.status = "Pending"

	doc.save(ignore_permissions=True)

	frappe.db.commit()

	return {"status": doc.status}





@frappe.whitelist()

def approve_payslip_request(docname: str):

	throw_if_not_hr_payroll()

	doc = _get_request_doc(docname)

	if doc.status != "Pending":

		frappe.throw(_("Only pending requests can be approved."))

	doc.status = "Approved"

	doc.approved_by = frappe.session.user

	doc.approved_on = now_datetime()

	doc.rejection_reason = None

	doc.save(ignore_permissions=True)

	frappe.db.commit()

	return {"status": doc.status}





@frappe.whitelist()

def reject_payslip_request(docname: str, rejection_reason: str | None = None):

	throw_if_not_hr_payroll()

	doc = _get_request_doc(docname)

	if doc.status != "Pending":

		frappe.throw(_("Only pending requests can be rejected."))

	doc.status = "Rejected"

	doc.rejection_reason = (rejection_reason or "").strip() or _("Rejected by HR")

	doc.approved_by = frappe.session.user

	doc.approved_on = now_datetime()

	doc.save(ignore_permissions=True)

	frappe.db.commit()

	return {"status": doc.status}





def build_download_params_from_request(doc: Document) -> dict:

	from hrms.payroll.payroll_import.payroll_month_utils import normalize_employee_id_number

	employee_id = normalize_employee_id_number(doc.employee_id_number)

	if not employee_id and doc.employee:

		employee_id = normalize_employee_id_number(
			frappe.db.get_value("Employee", doc.employee, "employee_number")
		)

	if not employee_id:

		frappe.throw(_("Employee ID number is missing on this request."))



	params: dict = {"employee_id_number": employee_id}

	pt = doc.period_type

	if pt == "Last N months":

		params["months"] = int(doc.months or 3)

	elif pt == "Single payroll month":

		params["payroll_month"] = doc.payroll_month

	else:

		params["from_month"] = doc.from_month

		params["to_month"] = doc.to_month

	return params





@frappe.whitelist()

def download_payslip_for_request(docname: str):

	doc = _get_request_doc(docname)

	if doc.status != "Approved":

		frappe.throw(_("Payslip can only be downloaded after HR approval."))

	if not _user_may_act_on_own_request(doc):

		frappe.throw(_("Not permitted"), frappe.PermissionError)



	from hrms.payroll.doctype.imported_payroll_record.imported_payroll_record import (

		_send_payslip_docx_response,

	)



	params = build_download_params_from_request(doc)

	_send_payslip_docx_response(**params)


