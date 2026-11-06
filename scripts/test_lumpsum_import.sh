#!/bin/bash
set -euo pipefail
cd ~/frappe-bench || exit 1

rsync -a '/mnt/c/Angelique Uwibambe/MS/hrms-standalone/hrms/' ~/frappe-bench/apps/hrms/hrms/

echo "=== Lumpsum files on site ==="
find ~/frappe-bench/sites/mysite.local -iname '*lumpsum*' 2>/dev/null | head -10 || true

echo "=== Existing Lumpsum imported records ==="
bench --site mysite.local mariadb <<'SQL'
SELECT COUNT(*) AS lumpsum_count FROM `tabImported Payroll Record` WHERE payroll_sheet_type='Lumpsum';
SELECT name, employee_id_number, payroll_month, gross_salary, net_salary
FROM `tabImported Payroll Record`
WHERE payroll_sheet_type='Lumpsum'
LIMIT 8;
SQL

LUMPSUM=""
for p in \
  "/mnt/c/Users/UwAngelique/Desktop/LUMPSUM.xlsx" \
  "/mnt/c/Angelique Uwibambe/Desktop/LUMPSUM.xlsx" \
  "$HOME/Desktop/LUMPSUM.xlsx" \
  "/mnt/c/Angelique Uwibambe/MS/hrms-standalone/scripts/fixtures/LUMPSUM.sample.xlsx"
do
  if [[ -f "$p" ]]; then
    LUMPSUM="$p"
    break
  fi
done

if [[ -z "$LUMPSUM" ]]; then
  echo "Generating sample LUMPSUM fixture..."
  ~/frappe-bench/env/bin/python "/mnt/c/Angelique Uwibambe/MS/hrms-standalone/scripts/generate_lumpsum_fixture.py"
  LUMPSUM="/mnt/c/Angelique Uwibambe/MS/hrms-standalone/scripts/fixtures/LUMPSUM.sample.xlsx"
fi

echo "=== Parsing $LUMPSUM ==="
~/frappe-bench/env/bin/python <<PY
import sys
sys.path.insert(0, "/home/wngelique/frappe-bench/apps/hrms")
from hrms.payroll.payroll_import.payroll_excel_parser import parse_payroll_excel

path = """$LUMPSUM"""
parsed = parse_payroll_excel(path)
print("sheet_type:", parsed.get("payroll_sheet_type"))
print("period:", parsed.get("payroll_period_label"), parsed.get("payroll_month"))
print("records:", len(parsed.get("records") or []))
print("column_map:", parsed.get("column_map"))
for r in (parsed.get("records") or [])[:3]:
    print(" ", r.get("employee_id_number"), r.get("employee_name"), "gross=", r.get("gross_salary"), "net=", r.get("net_salary"))
PY

echo "=== Import via Payroll Excel Upload (Administrator) ==="
cd ~/frappe-bench
bench --site mysite.local execute hrms.payroll.setup.run_lumpsum_import_test.run_lumpsum_import_test --kwargs "{'file_path': '$LUMPSUM'}"

echo "=== Dashboard API (September 2026, Lumpsum) ==="
bench --site mysite.local execute hrms.payroll.page.staff_payroll_dashboard.staff_payroll_dashboard.get_staff_payroll_dashboard --kwargs "{'payroll_month': '2026-09-01', 'company': 'Muganga Sacco', 'payroll_sheet_type': 'Lumpsum'}"
