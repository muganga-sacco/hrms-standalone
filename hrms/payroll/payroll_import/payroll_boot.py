# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

from __future__ import annotations

import frappe

from hrms.payroll.payroll_import.payroll_access import (
	HR_PAYROLL_ROLES,
	PAYROLL_DASHBOARD_VIEW_ROLES,
	PAYSLIP_SELF_REQUEST_ROLES,
)


def extend_bootinfo(bootinfo) -> None:
	"""Send employees to My Payslips; payroll viewers keep HR app default."""
	if frappe.session.user in ("Guest", "Administrator"):
		return

	roles = set(frappe.get_roles())
	if not roles & PAYSLIP_SELF_REQUEST_ROLES:
		return
	if roles & (HR_PAYROLL_ROLES | PAYROLL_DASHBOARD_VIEW_ROLES | {"System Manager"}):
		return

	apps_data = bootinfo.get("apps_data") or {}
	apps_data["default_path"] = "/app/my-payslips"
	bootinfo["apps_data"] = apps_data
