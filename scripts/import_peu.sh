#!/usr/bin/env bash
cd ~/frappe-bench
bench --site mysite.local execute hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload.import_payroll_excel --kwargs '{"docname": "HR-PEU-2026-00002"}'
bench --site mysite.local execute hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload.import_payroll_excel --kwargs '{"docname": "HR-PEU-2026-00008"}'
bench --site mysite.local mariadb -N -e "SELECT payroll_month, COUNT(*) FROM \`tabImported Payroll Record\` WHERE payroll_excel_upload='HR-PEU-2026-00008' GROUP BY payroll_month;"
