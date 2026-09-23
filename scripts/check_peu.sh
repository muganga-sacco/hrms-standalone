#!/bin/bash
cd ~/frappe-bench
bench --site mysite.local mariadb <<'SQL'
SELECT name, module FROM tabDocType WHERE name IN ('Payroll Excel Upload', 'Imported Payroll Record');
SQL
