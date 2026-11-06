#!/usr/bin/env bash
rsync -a "/mnt/c/Angelique Uwibambe/MS/hrms-standalone/hrms/" ~/frappe-bench/apps/hrms/hrms/
cd ~/frappe-bench
bench --site mysite.local clear-cache
bench --site mysite.local execute hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload.refresh_sheet_layout_from_excel --kwargs '{"docname": "HR-PEU-2026-00002"}'
bench --site mysite.local mariadb -N -e "SELECT payroll_sheet_logo IS NOT NULL, CHAR_LENGTH(IFNULL(payroll_sheet_footer,'')) FROM \`tabPayroll Excel Upload\` WHERE name='HR-PEU-2026-00002';"
