# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Email HR when a payslip request is submitted, and DAF after HR approves."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import get_url_to_form


def notify_pending_hr(doc) -> None:
	_send_payslip_request_mail(
		doc,
		recipients=_hr_recipients(),
		subject=_("Payslip request pending HR: {0}").format(doc.employee_name or doc.name),
		heading=_("A payslip request needs HR approval"),
		intro=_("A new payslip request is waiting for HR."),
	)


def notify_pending_daf(doc) -> None:
	_send_payslip_request_mail(
		doc,
		recipients=_daf_recipients(),
		subject=_("Payslip request pending DAF: {0}").format(doc.employee_name or doc.name),
		heading=_("A payslip request needs DAF approval"),
		intro=_("HR has verified this payslip request. It is waiting for DAF approval."),
	)


def _send_payslip_request_mail(doc, recipients: list[str], subject: str, heading: str, intro: str) -> None:
	if not _emails_enabled() or not recipients:
		return
	link = get_url_to_form("Payslip Request", doc.name)
	period = _period_label(doc)
	message = f"""
		<p>{frappe.utils.escape_html(intro)}</p>
		<p>
			<strong>{_("Request")}:</strong> {frappe.utils.escape_html(doc.name)}<br>
			<strong>{_("Employee")}:</strong> {frappe.utils.escape_html(doc.employee_name or doc.employee)}<br>
			<strong>{_("Period")}:</strong> {frappe.utils.escape_html(period)}
		</p>
		<p><a href="{frappe.utils.escape_html(link)}">{_("Open payslip request")}</a></p>
	"""
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			sender=_sender_email(),
			now=True,
			expose_recipients="header",
			header=[heading, "blue"],
		)
	except Exception:
		frappe.log_error(title="Payslip request email")


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
