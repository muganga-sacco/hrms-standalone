#!/bin/bash
set -e
cd ~/frappe-bench
DOC="/home/wngelique/frappe-bench/apps/hrms/hrms/payroll/workspace/payroll/payroll.json"
# sync from Windows repo if newer
RSYNC="/mnt/c/Angelique Uwibambe/MS/hrms-standalone/hrms/payroll/workspace/payroll/payroll.json"
if [ -f "$RSYNC" ]; then
  cp "$RSYNC" "$DOC"
fi
bench --site mysite.local import-doc "$DOC"
bench --site mysite.local clear-cache
echo "Done. Open: http://127.0.0.1:8000/app/payroll-excel-upload"
