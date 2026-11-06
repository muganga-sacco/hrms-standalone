SELECT name, status, imported_records, LEFT(import_log, 2000) AS import_log
FROM `tabPayroll Excel Upload`
ORDER BY modified DESC
LIMIT 3;
