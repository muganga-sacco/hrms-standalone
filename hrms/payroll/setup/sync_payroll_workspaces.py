# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

"""Import Payroll workspaces from app JSON (overwrites Workspace docs).

Run after deploy if desk layout looks stale:
  bench --site mysite.local execute hrms.payroll.setup.sync_payroll_workspaces.sync_payroll_workspaces
"""

from __future__ import annotations

from pathlib import Path

import frappe
from frappe.modules.import_file import import_file_by_path


def sync_payroll_workspaces() -> list[str]:
	base = Path(frappe.get_app_path("hrms")) / "payroll" / "workspace"
	updated = []
	for path in sorted(base.glob("*/*.json")):
		import_file_by_path(str(path), force=True)
		updated.append(path.stem)
	from hrms.payroll.setup.ensure_payroll_dashboard_permissions import (
		ensure_payroll_dashboard_permissions,
	)

	ensure_payroll_dashboard_permissions()
	frappe.db.commit()
	return updated
