#!/bin/bash
set -e
rsync -a "/mnt/c/Angelique Uwibambe/MS/hrms-standalone/hrms/" ~/frappe-bench/apps/hrms/hrms/
cd ~/frappe-bench
bench --site mysite.local execute frappe.db.get_value --kwargs "{'doctype': 'Company', 'filters': 'Muganga Sacco', 'fieldname': 'company_logo'}"
