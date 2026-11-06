#!/bin/bash
cd ~/frappe-bench || exit 1
bench --site mysite.local mariadb <<'SQL'
SELECT name, currency_name, symbol FROM tabCurrency WHERE name='RWF';
SELECT name, currency FROM `tabImported Payroll Record` WHERE name LIKE 'IPR-MSID 003%';
SQL
