# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Email DAF / MD / HR when a payroll Excel upload is waiting for approval."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import escape_html, get_url_to_form

from hrms.payroll.payroll_import.payslip_request_email import (
	_daf_recipients,
	_emails_enabled,
	_hr_recipients,
	_md_recipients,
	_sender_email,
)


def notify_payroll_excel_approval(doc, audience: str) -> None:
	audience = (audience or "DAF").upper()
	if audience == "HR":
		recipients = _hr_recipients()
	elif audience == "MD":
		recipients = _md_recipients()
	else:
		recipients = _daf_recipients()
	_send(doc, recipients, audience)


def notify_payroll_excel_rejected(doc) -> None:
	_send(doc, _hr_recipients(), "HR", kind="rejected")


def notify_payroll_excel_approved(doc) -> None:
	_send(doc, _hr_recipients(), "HR", kind="approved")


def _send(doc, recipients: list[str], audience: str, kind: str = "pending") -> None:
	if not _emails_enabled() or not recipients:
		return
	link = get_url_to_form("Payroll Excel Upload", doc.name)
	sheet = (doc.payroll_sheet_type or "Staff Payroll").strip()
	period = (doc.payroll_period_label or doc.payroll_month_name or doc.name or "").strip()
	if kind == "rejected":
		subject = _("Payroll Excel – Rejected")
		reason = (doc.rejection_reason or "").strip()
		reason_html = (
			f"<p>{_('Reason')}: {escape_html(reason)}</p>" if reason else ""
		)
		message = f"""
			<p>Dear {escape_html(audience)}</p>
			<p>{escape_html(sheet)} for {escape_html(period)} was rejected.</p>
			{reason_html}
			<p><a href="{escape_html(link)}">{_("Open payroll Excel upload")}</a></p>
		"""
		header = [subject, "red"]
	elif kind == "approved":
		subject = _("Payroll Excel – Approved")
		message = f"""
			<p>Dear {escape_html(audience)}</p>
			<p>{escape_html(sheet)} for {escape_html(period)} has been approved by DAF and MD.</p>
			<p>Staff can now request payslips for this month.</p>
			<p><a href="{escape_html(link)}">{_("Open payroll Excel upload")}</a></p>
		"""
		header = [subject, "green"]
	else:
		subject = _("Payroll Excel – Approval Required")
		message = f"""
			<p>Dear {escape_html(audience)}</p>
			<p>HR has uploaded {escape_html(sheet)} for {escape_html(period)}.</p>
			<p>Kindly open the Excel and the signed payroll, confirm they match what you signed, and take the appropriate action.</p>
			<p><a href="{escape_html(link)}">{_("Open payroll Excel upload")}</a></p>
		"""
		header = [subject, "blue"]
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			sender=_sender_email(),
			now=True,
			expose_recipients="header",
			header=header,
		)
	except Exception:
		frappe.log_error(title="Payroll Excel upload email")
