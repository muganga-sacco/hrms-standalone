#!/bin/bash
cd ~/frappe-bench || exit 1
bench --site mysite.local mariadb <<'SQL'
SELECT name, default_currency FROM tabCompany WHERE name='Muganga Sacco';
SELECT fieldname, options FROM tabDocField WHERE parent='Imported Payroll Record' AND fieldname='basic_salary';
SELECT name, company FROM `tabImported Payroll Record` LIMIT 3;
SELECT value FROM tabSingles WHERE doctype='Global Defaults' AND field='default_currency';
SELECT value FROM tabSingles WHERE doctype='System Settings' AND field='currency';
SQL
