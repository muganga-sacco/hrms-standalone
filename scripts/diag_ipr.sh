#!/bin/bash
cd ~/frappe-bench || exit 1
bench --site mysite.local mariadb <<'SQL'
SELECT name, company, currency, basic_salary, paye, ict_allowance FROM `tabImported Payroll Record` WHERE name='IPR-MSID 003-2026-06-01';
SELECT fieldname FROM tabDocField WHERE parent='Imported Payroll Record' AND fieldname='currency';
SELECT fieldname, options FROM tabDocField WHERE parent='Imported Payroll Record' AND fieldname='basic_salary';
SELECT default_currency FROM tabCompany WHERE name='Muganga Sacco';
SELECT field, value FROM tabSingles WHERE doctype='Global Defaults' AND field IN ('default_currency','default_company');
SELECT field, value FROM tabSingles WHERE doctype='System Settings' AND field='currency';
SQL
