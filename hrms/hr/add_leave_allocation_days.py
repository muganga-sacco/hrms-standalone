# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Add extra days on top of existing New Leaves (ledger), never replace.

Dry run (default):
  bench --site hrms.local execute hrms.hr.add_leave_allocation_days.run --kwargs '{"days": 6}'

One employee, write:
  bench --site hrms.local execute hrms.hr.add_leave_allocation_days.run --kwargs '{"days": 6, "employee": "HR-EMP-00049", "dry_run": 0}'

All Annual leave allocations that cover 31-12-2026:
  bench --site hrms.local execute hrms.hr.add_leave_allocation_days.run --kwargs '{"days": 6, "dry_run": 0}'
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, getdate

NOTE_MARKER = "[add_leave_allocation_days]"


def run(
	days: float = 6,
	leave_type: str = "Annual leave",
	year: int = 2026,
	employee: str | None = None,
	dry_run: int | bool = 1,
	force: int | bool = 0,
) -> dict:
	days = flt(days)
	if days <= 0:
		frappe.throw("days must be greater than 0")

	year_start = getdate(f"{int(year)}-01-01")
	year_end = getdate(f"{int(year)}-12-31")
	dry_run = cint_bool(dry_run)
	force = cint_bool(force)

	rows = _allocations(leave_type, year_start, year_end, employee)
	results = []

	for row in rows:
		doc = frappe.get_doc("Leave Allocation", row.name)
		if not force and _already_stamped(doc):
			results.append(
				{
					"allocation": doc.name,
					"employee": doc.employee,
					"employee_name": doc.employee_name,
					"skipped": "already tagged (use force=1 to add again)",
				}
			)
			continue

		existing = flt(doc.get_existing_leave_count(), doc.precision("new_leaves_allocated"))
		target = flt(existing + days, doc.precision("new_leaves_allocated"))
		info = {
			"allocation": doc.name,
			"employee": doc.employee,
			"employee_name": doc.employee_name,
			"from_date": str(doc.from_date),
			"to_date": str(doc.to_date),
			"field_now": flt(doc.new_leaves_allocated),
			"ledger_new_now": existing,
			"days_to_add": days,
			"field_after": target,
			"dry_run": dry_run,
		}

		if getdate(doc.to_date) < year_end:
			info["skipped"] = f"to_date {doc.to_date} is before {year_end}; extra days would expire in the year report"
			results.append(info)
			continue

		if dry_run:
			info["action"] = "would save existing ledger + extra"
			results.append(info)
			continue

		doc.new_leaves_allocated = target
		_stamp_extra(doc, days, existing, target)
		doc.save(ignore_permissions=True)
		info["action"] = "saved"
		results.append(info)

	if not dry_run:
		frappe.db.commit()

	return {
		"dry_run": dry_run,
		"days": days,
		"leave_type": leave_type,
		"count": len(results),
		"rows": results,
	}


def _allocations(leave_type, year_start, year_end, employee: str | None):
	filters = {
		"leave_type": leave_type,
		"docstatus": 1,
		"from_date": ["<=", year_end],
		"to_date": [">=", year_start],
	}
	if employee:
		filters["employee"] = employee

	rows = frappe.get_all(
		"Leave Allocation",
		filters=filters,
		fields=["name", "employee", "to_date"],
		order_by="employee, to_date desc",
	)
	# one allocation per employee: the one that lasts longest (prefer year-end)
	seen = set()
	picked = []
	for row in rows:
		if row.employee in seen:
			continue
		seen.add(row.employee)
		picked.append(row)
	return picked


@frappe.whitelist()
def get_existing_allocation(employee: str, leave_type: str, name: str | None = None) -> dict:
	"""Existing grant for the Leave Allocation form (Total starts here, New starts at 0)."""
	if not employee or not leave_type:
		return {}
	doc = None
	if name and frappe.db.exists("Leave Allocation", name):
		doc = frappe.get_doc("Leave Allocation", name)
	else:
		row = frappe.db.sql(
			"""
			select name from `tabLeave Allocation`
			where employee=%s and leave_type=%s and docstatus=1
			order by to_date desc, modified desc
			limit 1
			""",
			(employee, leave_type),
			as_dict=True,
		)
		if row:
			doc = frappe.get_doc("Leave Allocation", row[0].name)
	if not doc:
		return {"name": None, "opening": 0, "unused": 0, "ledger_new": 0, "total": 0}
	ledger_new = flt(doc.get_existing_leave_count(), doc.precision("new_leaves_allocated"))
	opening = flt(doc.unused_leaves)
	return {
		"name": doc.name,
		"employee": doc.employee,
		"leave_type": doc.leave_type,
		"from_date": str(doc.from_date),
		"to_date": str(doc.to_date),
		"opening": opening,
		"unused": opening,
		"ledger_new": ledger_new,
		"total": ledger_new,
		"docstatus": doc.docstatus,
	}


def _already_stamped(doc) -> bool:
	return bool(
		frappe.db.exists(
			"Comment",
			{
				"reference_doctype": "Leave Allocation",
				"reference_name": doc.name,
				"content": ["like", f"%{NOTE_MARKER}%"],
			},
		)
	)


def _stamp_extra(doc, extra, existing, target) -> None:
	note = f"{NOTE_MARKER} added {extra} on {frappe.utils.nowdate()} (ledger {existing} -> {target})"
	doc.add_comment("Info", note)


@frappe.whitelist()
def apply_extra_days(allocation_name: str, extra: float) -> dict:
	"""Add extra days on top of ledger New Leaves. Used by New Leave Allocation."""
	frappe.has_permission("Leave Allocation", "write", throw=True)
	extra = flt(extra)
	if extra <= 0:
		frappe.throw(frappe._("Type extra days in New Leaves Allocated"))
	doc = frappe.get_doc("Leave Allocation", allocation_name)
	existing = flt(doc.get_existing_leave_count(), doc.precision("new_leaves_allocated"))
	doc.new_leaves_allocated = flt(existing + extra, doc.precision("new_leaves_allocated"))
	_stamp_extra(doc, extra, existing, doc.new_leaves_allocated)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"name": doc.name,
		"new_leaves_allocated": doc.new_leaves_allocated,
		"total_leaves_allocated": doc.total_leaves_allocated,
		"added": extra,
	}


def cint_bool(val) -> bool:
	if val in (True, 1, "1", "true", "True"):
		return True
	if val in (False, 0, "0", "false", "False"):
		return False
	return bool(int(val))
