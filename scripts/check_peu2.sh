#!/bin/bash
cd ~/frappe-bench || exit 1
bench --site mysite.local mariadb <<'SQL'
SELECT link_to, label FROM `tabWorkspace Link`
WHERE parent='Payroll' AND link_to LIKE '%Payroll%';
SQL
