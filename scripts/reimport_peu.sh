#!/bin/bash
set -e
rsync -a "/mnt/c/Angelique Uwibambe/MS/hrms-standalone/hrms/payroll/payroll_import/" ~/frappe-bench/apps/hrms/hrms/payroll/payroll_import/
rsync -a "/mnt/c/Angelique Uwibambe/MS/hrms-standalone/hrms/payroll/doctype/payroll_excel_upload/payroll_excel_upload.py" ~/frappe-bench/apps/hrms/hrms/payroll/doctype/payroll_excel_upload/
cd ~/frappe-bench
bench --site mysite.local execute hrms.payroll.doctype.payroll_excel_upload.payroll_excel_upload.import_payroll_excel --args '["HR-PEU-2026-00002"]'
