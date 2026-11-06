#!/bin/bash
cd ~/frappe-bench || exit 1
bench --site mysite.local mariadb <<'SQL'
SELECT name, report_type FROM tabReport WHERE name='Imported Payroll Register';
SELECT link_to FROM `tabWorkspace Link` WHERE parent='Payroll' AND link_to='Imported Payroll Register';
SQL
