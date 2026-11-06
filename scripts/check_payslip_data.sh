#!/bin/bash
cd ~/frappe-bench || exit 1
bench --site mysite.local mariadb <<'SQL'
SELECT name, employee_id_number, employee_name, payroll_month, payroll_period_label, basic_salary, docstatus
FROM `tabImported Payroll Record`
WHERE docstatus=1
ORDER BY employee_id_number, payroll_month DESC;
SQL
