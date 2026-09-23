#!/bin/bash
set -e
RSYNC="/mnt/c/Angelique Uwibambe/MS/hrms-standalone/hrms/"
DEST=~/frappe-bench/apps/hrms/hrms/
rsync -a "$RSYNC" "$DEST"
rsync -a "/mnt/c/Angelique Uwibambe/MS/hrms-standalone/hrms/hooks.py" ~/frappe-bench/apps/hrms/hrms/hooks.py
cd ~/frappe-bench
bench --site mysite.local migrate
bench build --app hrms
bench --site mysite.local clear-cache
WS="/home/wngelique/frappe-bench/apps/hrms/hrms/payroll/workspace/payroll/payroll.json"
bench --site mysite.local import-doc "$WS" 2>/dev/null || true
echo "Deploy done."
