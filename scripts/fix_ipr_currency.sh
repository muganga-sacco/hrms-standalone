#!/bin/bash
set -e
cd ~/frappe-bench || exit 1
bench --site mysite.local mariadb <<'SQL'
UPDATE `tabImported Payroll Record` SET currency = 'RWF' WHERE name = 'IPR-MSID 001-2026-06-01';
UPDATE `tabImported Payroll Record` SET currency = 'RWF' WHERE name = 'IPR-MSID 002-2026-06-01';
UPDATE `tabImported Payroll Record` SET currency = 'RWF' WHERE name = 'IPR-MSID 003-2026-06-01';
UPDATE tabSingles SET value = 'RWF' WHERE doctype = 'Global Defaults' AND field = 'default_currency';
SQL
bench --site mysite.local clear-cache
echo "Fixed currency on Imported Payroll Records and Global Defaults."
