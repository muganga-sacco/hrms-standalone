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

	user_can_see_all_payslip_requests,

	user_has_hr_payroll_access,

)



PAYSLIP_MONTHS = (

	"January",

	"February",

	"March",

	"April",

	"May",

	"June",

	"July",

	"August",

	"September",

	"October",

	"November",

	"December",

)





def _date_from_year_month(year, month_name):

	if not year or month_name not in PAYSLIP_MONTHS:

		return None

	return f"{int(year)}-{PAYSLIP_MONTHS.index(month_name) + 1:02d}-01"





class PayslipRequest(Document):

	def validate(self):

		self._set_employee_for_self_service()

		self._validate_period_fields()

		self._validate_remarks()

		self._validate_payroll_month_approved()

		if self.employee:

			resolved = resolve_employee_id_number_for_request(self)

			if not resolved:

				frappe.throw(

					_("Set Employee Number on {0}. It must match ID NUMBER on the payroll and lumpsum template.").format(

						self.employee_name or self.employee

					)

				)

			self.employee_id_number = resolved



	def _validate_remarks(self) -> None:

		if self.remarks == "Others (please specify)" and not (self.get("remarks_other") or "").strip():

			frappe.throw(_("Please specify the reason for the request."))



	def _validate_payroll_month_approved(self) -> None:

		if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:

			return

		if self.status not in ("Draft", "Pending", "Pending HR", "Pending DAF", "Pending MD"):

			return

		from hrms.payroll.payroll_import.payroll_excel_approval import (

			throw_if_payslip_months_not_approved,

		)

		throw_if_payslip_months_not_approved(self)



	def _set_employee_for_self_service(self) -> None:

		if user_can_see_all_payslip_requests() or frappe.flags.in_install:

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

		if self.status not in ("Draft", "Pending", "Pending HR", "Pending DAF", "Pending MD"):

			return

		pt = self.period_type

		if pt in ("Last N months", "Last 3 months"):

			self.months = 3

		if pt == "Single payroll month":

			composed = _date_from_year_month(self.payroll_year, self.payroll_month_name)

			if composed:

				self.payroll_month = composed

			if not self.payroll_month:

				frappe.throw(_("Year and Month are required."))

		if pt == "From month – To month":

			composed_from = _date_from_year_month(self.payroll_year, self.payroll_month_name)

			composed_to = _date_from_year_month(self.to_year, self.to_month_name)

			if composed_from:

				self.from_month = composed_from

			if composed_to:

				self.to_month = composed_to

			if not self.from_month or not self.to_month:

				frappe.throw(_("From month and To month are required."))

			if getdate(self.from_month) > getdate(self.to_month):

				frappe.throw(_("From month cannot be after To month."))





def _is_payslip_request_owner(doc, user: str) -> bool:

	return bool(doc and getattr(doc, "owner", None) == user)


def _own_payslip_rules(doc, ptype: str, user: str, employee: str | None) -> bool:

	if not doc:

		return ptype in ("create", "read")

	if _is_payslip_request_owner(doc, user):

		if ptype in ("export", "delete"):

			return False

		if ptype == "write" and doc.status != "Draft":

			return False

		return ptype in ("create", "read", "write", "print")

	if not employee:

		return ptype == "create"

	if doc.employee != employee:

		return False

	if ptype in ("export", "delete"):

		return False

	if ptype == "write" and doc.status != "Draft":

		return False

	return True





def get_permission_query_conditions(user: str) -> str:

	if user_can_see_all_payslip_requests(user):

		return ""

	if not user_can_request_own_payslip(user):

		return "1=0"

	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

	escaped_user = frappe.db.escape(user)

	if not employee:

		return f"`tabPayslip Request`.owner = {escaped_user}"

	escaped_employee = frappe.db.escape(employee)

	return (

		f"(`tabPayslip Request`.employee = {escaped_employee} "

		f"OR `tabPayslip Request`.owner = {escaped_user})"

	)





def has_permission(doc, ptype: str, user: str) -> bool:

	if user_has_hr_payroll_access(user):

		return True

	if user_can_see_all_payslip_requests(user) and ptype in ("read", "print", "report", "select"):

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

	if _is_payslip_request_owner(doc, frappe.session.user):

		return True

	own = get_logged_in_employee()

	return bool(own and doc.employee == own)





def resolve_employee_id_number_for_request(doc) -> str:

	"""Employee Number, the ID NUMBER on the payroll and lumpsum template."""

	from hrms.payroll.payroll_import.payroll_month_utils import normalize_employee_id_number

	employee = doc.employee if getattr(doc, "employee", None) else None

	if not employee:

		return ""

	return normalize_employee_id_number(

		frappe.db.get_value("Employee", employee, "employee_number")

	)





def _approval_flow_for_user(user: str | None = None) -> str:

	user = user or frappe.session.user

	if user in ("Administrator", "Guest"):

		return "Staff"

	from hrms.payroll.payroll_import.payroll_access import HR_PAYROLL_ROLES

	roles = set(frappe.get_roles(user))

	hr = bool(HR_PAYROLL_ROLES & roles)

	daf = "DAF" in roles

	# MD's own request is approved by HR then DAF, never by the MD.

	if "MD" in roles:

		return "Staff"

	if daf:

		return "DAF"

	if hr:

		return "HR"

	return "Staff"





def _is_self_payslip_request(doc, user: str | None = None) -> bool:

	user = user or frappe.session.user

	if not user or user == "Guest":

		return False

	if doc.employee:

		emp_user = frappe.db.get_value("Employee", doc.employee, "user_id")

		if emp_user and emp_user == user:

			return True

	return False





def _block_self_approval(doc) -> None:

	if _is_self_payslip_request(doc):

		frappe.throw(_("You cannot approve or reject your own payslip request."))





def _notify_next(doc) -> None:

	from hrms.payroll.payroll_import.payslip_request_email import notify_approval_required

	if doc.status == "Pending HR":

		notify_approval_required(doc, "HR")

	elif doc.status == "Pending DAF":

		notify_approval_required(doc, "DAF")

	elif doc.status == "Pending MD":

		notify_approval_required(doc, "MD")





@frappe.whitelist()

def submit_payslip_request(docname: str):

	doc = _get_request_doc(docname)

	if doc.status != "Draft":

		frappe.throw(_("Only draft requests can be submitted."))

	if not _user_may_act_on_own_request(doc):

		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from hrms.payroll.payroll_import.payroll_excel_approval import (

		throw_if_payslip_months_not_approved,

	)

	throw_if_payslip_months_not_approved(doc)

	flow = _approval_flow_for_user()

	doc.approval_flow = flow

	doc.status = "Pending DAF" if flow == "HR" else "Pending HR"

	doc.save(ignore_permissions=True)

	frappe.db.commit()

	_notify_next(doc)

	return {"status": doc.status}





@frappe.whitelist()

def approve_payslip_request(docname: str):

	throw_if_not_hr_payroll()

	doc = _get_request_doc(docname)

	if doc.status not in ("Pending HR", "Pending"):

		frappe.throw(_("Only requests waiting for HR can be approved."))

	_block_self_approval(doc)

	from hrms.payroll.payroll_import.payroll_signoff import approver_profile

	approver_profile(frappe.session.user, request=doc, prefer="prepared")

	flow = (doc.approval_flow or "Staff").strip() or "Staff"

	doc.hr_approved_by = frappe.session.user

	doc.hr_approved_on = now_datetime()

	doc.rejection_reason = None

	resolved_id = resolve_employee_id_number_for_request(doc)

	if resolved_id:

		doc.employee_id_number = resolved_id

	if flow == "DAF":

		doc.status = "Pending MD"

	elif doc.daf_approved_by:

		doc.status = "Approved"

		doc.approved_by = doc.daf_approved_by

		doc.approved_on = doc.daf_approved_on

	else:

		doc.status = "Pending DAF"

	doc.save(ignore_permissions=True)

	frappe.db.commit()

	_notify_next(doc)

	return {"status": doc.status}





@frappe.whitelist()

def daf_approve_payslip_request(docname: str):

	from hrms.payroll.payroll_import.payroll_signoff import approver_profile, throw_if_not_daf

	throw_if_not_daf()

	doc = _get_request_doc(docname)

	if doc.status != "Pending DAF":

		frappe.throw(_("Only requests waiting for DAF can be approved."))

	_block_self_approval(doc)

	flow = (doc.approval_flow or "Staff").strip() or "Staff"

	doc.daf_approved_by = frappe.session.user

	doc.daf_approved_on = now_datetime()

	doc.rejection_reason = None

	if flow == "HR":

		approver_profile(frappe.session.user, request=doc, prefer="prepared")

		doc.status = "Pending MD"

		doc.save(ignore_permissions=True)

		frappe.db.commit()

		_notify_next(doc)

		return {"status": doc.status}

	approver_profile(frappe.session.user, request=doc, prefer="verified")

	doc.status = "Approved"

	doc.approved_by = frappe.session.user

	doc.approved_on = doc.daf_approved_on

	doc.save(ignore_permissions=True)

	frappe.db.commit()

	return {"status": doc.status}





@frappe.whitelist()

def md_approve_payslip_request(docname: str):

	from hrms.payroll.payroll_import.payroll_signoff import approver_profile, throw_if_not_md

	throw_if_not_md()

	doc = _get_request_doc(docname)

	if doc.status != "Pending MD":

		frappe.throw(_("Only requests waiting for MD can be approved."))

	_block_self_approval(doc)

	approver_profile(frappe.session.user, request=doc, prefer="verified")

	doc.status = "Approved"

	doc.md_approved_by = frappe.session.user

	doc.md_approved_on = now_datetime()

	doc.approved_by = frappe.session.user

	doc.approved_on = doc.md_approved_on

	doc.rejection_reason = None

	doc.save(ignore_permissions=True)

	frappe.db.commit()

	return {"status": doc.status}





@frappe.whitelist()

def reject_payslip_request(docname: str, rejection_reason: str | None = None):

	from hrms.payroll.payroll_import.payroll_signoff import user_has_daf_access

	doc = _get_request_doc(docname)

	from hrms.payroll.payroll_import.payroll_signoff import user_has_md_access

	if doc.status not in ("Pending HR", "Pending DAF", "Pending MD", "Pending"):

		frappe.throw(_("Only requests waiting for approval can be rejected."))

	if not (user_has_hr_payroll_access() or user_has_daf_access() or user_has_md_access()):

		frappe.throw(_("Not permitted"), frappe.PermissionError)

	_block_self_approval(doc)

	doc.status = "Rejected"

	doc.rejection_reason = (rejection_reason or "").strip() or _("Rejected")

	doc.approved_by = frappe.session.user

	doc.approved_on = now_datetime()

	doc.save(ignore_permissions=True)

	frappe.db.commit()

	return {"status": doc.status}





def build_download_params_from_request(doc: Document) -> dict:

	if not doc.employee:

		frappe.throw(_("Payslip Request {0} has no Employee linked.").format(doc.name))

	employee_id = resolve_employee_id_number_for_request(doc)

	if not employee_id:

		frappe.throw(

			_("Set Employee Number on {0}. It must match ID NUMBER on the payroll and lumpsum template.").format(

				doc.employee_name or doc.employee

			)

		)

	if employee_id != (doc.employee_id_number or "").strip():

		frappe.db.set_value(

			"Payslip Request",

			doc.name,

			"employee_id_number",

			employee_id,

			update_modified=False,

		)



	params: dict = {"employee_id_number": employee_id}

	pt = doc.period_type

	if pt in ("Last N months", "Last 3 months"):

		params["months"] = 3

	elif pt == "Single payroll month":

		params["payroll_month"] = doc.payroll_month

	else:

		params["from_month"] = doc.from_month

		params["to_month"] = doc.to_month

	return params





def _user_may_preview_payslip(doc: Document) -> bool:

	from hrms.payroll.payroll_import.payroll_signoff import user_has_daf_access

	from hrms.payroll.payroll_import.payroll_signoff import user_has_md_access

	if user_has_hr_payroll_access() or user_has_daf_access() or user_has_md_access():

		return True

	return doc.status == "Approved" and _user_may_act_on_own_request(doc)





@frappe.whitelist()

def preview_payslip_for_request(docname: str):

	from hrms.payroll.payroll_import.payslip_docx import build_payslip_preview
	from hrms.payroll.payroll_import.payroll_signoff import signoff_for_request, user_has_daf_access

	doc = _get_request_doc(docname)

	if not _user_may_preview_payslip(doc):

		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if doc.status not in ("Pending", "Pending HR", "Pending DAF", "Pending MD", "Approved"):

		frappe.throw(_("Payslip can be previewed after the request is submitted."))

	from hrms.payroll.payroll_import.payroll_signoff import user_has_md_access

	if doc.status in ("Pending", "Pending HR", "Pending DAF", "Pending MD") and not (

		user_has_hr_payroll_access() or user_has_daf_access() or user_has_md_access()

	):

		frappe.throw(_("Only HR, DAF, or MD can preview a payslip before approval."))

	params = build_download_params_from_request(doc)

	preview = build_payslip_preview(**params, signoff=signoff_for_request(doc))

	preview["request"] = doc.name

	preview["status"] = doc.status

	preview["period_type"] = doc.period_type

	return preview





@frappe.whitelist()

def download_payslip_for_request(docname: str):

	doc = _get_request_doc(docname)

	if doc.status != "Approved":

		frappe.throw(_("Payslip can only be downloaded after it is approved."))

	if not _user_may_act_on_own_request(doc):

		frappe.throw(_("Not permitted"), frappe.PermissionError)



	from hrms.payroll.doctype.imported_payroll_record.imported_payroll_record import (

		_send_payslip_docx_response,

	)

	from hrms.payroll.payroll_import.payroll_signoff import signoff_for_request



	params = build_download_params_from_request(doc)

	_send_payslip_docx_response(**params, signoff=signoff_for_request(doc))


