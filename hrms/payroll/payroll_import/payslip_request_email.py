# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Email the next approver when a payslip request is waiting."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import escape_html, get_url_to_form


def notify_pending_hr(doc) -> None:
	notify_approval_required(doc, "HR")


def notify_pending_daf(doc) -> None:
	notify_approval_required(doc, "DAF")


def notify_pending_md(doc) -> None:
	notify_approval_required(doc, "MD")


def notify_approval_required(doc, audience: str) -> None:
	audience = (audience or "HR").upper()
	if audience == "HR":
		recipients = _hr_recipients()
	elif audience == "DAF":
		recipients = _daf_recipients()
	else:
		recipients = _md_recipients()
	_send_payslip_request_mail(doc, recipients, audience)


def _send_payslip_request_mail(doc, recipients: list[str], audience: str) -> None:
	if not _emails_enabled() or not recipients:
		return
	link = get_url_to_form("Payslip Request", doc.name)
	period = _period_label(doc)
	who = _requester_line(doc)
	message = f"""
		<p>Dear {escape_html(audience)}</p>
		<p>{escape_html(who)} has requested for payslip for the Period {escape_html(period)}.</p>
		<p>Kindly review the request and take the appropriate action.</p>
		<p><a href="{escape_html(link)}">{_("Open payslip request")}</a></p>
	"""
	try:
		frappe.sendmail(
			recipients=recipients,
			subject="Payslip Request – Approval Required",
			message=message,
			sender=_sender_email(),
			now=True,
			expose_recipients="header",
			header=[_("Payslip Request – Approval Required"), "blue"],
		)
	except Exception:
		frappe.log_error(title="Payslip request email")


def _requester_line(doc) -> str:
	name = (doc.employee_name or doc.employee or "").strip()
	title = ""
	if doc.employee:
		gender = (frappe.db.get_value("Employee", doc.employee, "gender") or "").strip()
		if gender == "Male":
			title = "Mr. "
		elif gender == "Female":
			title = "Mrs./Miss "
	return f"{title}{name}".strip() or doc.name


def _emails_enabled() -> bool:
	if not frappe.get_meta("Payroll Settings").has_field("enable_payslip_request_emails"):
		return True
	return bool(frappe.db.get_single_value("Payroll Settings", "enable_payslip_request_emails"))


def _sender_email() -> str | None:
	account = None
	meta = frappe.get_meta("Payroll Settings")
	if meta.has_field("payslip_email_account"):
		account = frappe.db.get_single_value("Payroll Settings", "payslip_email_account")
	if not account and meta.has_field("sender"):
		account = frappe.db.get_single_value("Payroll Settings", "sender")
	if not account:
		return None
	return frappe.db.get_value("Email Account", account, "email_id")


def _hr_recipients() -> list[str]:
	return _setting_or_role_emails("hr_payslip_notification_emails", ("HR Manager", "HR User"))


def _daf_recipients() -> list[str]:
	return _setting_or_role_emails("daf_payslip_notification_emails", ("DAF",))


def _md_recipients() -> list[str]:
	if frappe.get_meta("Payroll Settings").has_field("md_payslip_notification_emails"):
		listed = _split_emails(
			frappe.db.get_single_value("Payroll Settings", "md_payslip_notification_emails")
		)
		if listed:
			return listed
	return _emails_for_roles(("MD",))


def _setting_or_role_emails(fieldname: str, roles: tuple[str, ...]) -> list[str]:
	if frappe.get_meta("Payroll Settings").has_field(fieldname):
		listed = _split_emails(frappe.db.get_single_value("Payroll Settings", fieldname))
		if listed:
			return listed
	return _emails_for_roles(roles)


def _split_emails(text) -> list[str]:
	if not text:
		return []
	seen = []
	for part in re.split(r"[\s,;]+", str(text).replace("\n", " ")):
		email = part.strip().lower()
		if email and "@" in email and email not in seen:
			seen.append(email)
	return seen


def _emails_for_roles(roles: tuple[str, ...]) -> list[str]:
	users = set()
	for role in roles:
		users.update(
			frappe.get_all(
				"Has Role",
				filters={"role": role, "parenttype": "User"},
				pluck="parent",
			)
		)
	emails = []
	for user in users:
		if user in ("Guest", "Administrator"):
			continue
		row = frappe.db.get_value("User", user, ["enabled", "email"], as_dict=True) or {}
		if not row.get("enabled"):
			continue
		email = (row.get("email") or "").strip()
		if email and "@" in email and email not in emails:
			emails.append(email)
	return emails


def _period_label(doc) -> str:
	start = " ".join(part for part in (doc.payroll_month_name, str(doc.payroll_year or "")) if part)
	end = " ".join(part for part in (doc.to_month_name, str(doc.to_year or "")) if part)
	if start and end and start != end:
		return f"{start} – {end}"
	return start or end or doc.name
