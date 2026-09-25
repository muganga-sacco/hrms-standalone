SELECT payroll_month, payroll_sheet_type, COUNT(*) AS n
FROM `tabImported Payroll Record`
WHERE docstatus = 1
GROUP BY payroll_month, payroll_sheet_type
ORDER BY payroll_month, payroll_sheet_type;

SELECT name, employee_id_number, payroll_month, payroll_sheet_type, date_of_joining, payroll_period_label
FROM `tabImported Payroll Record`
WHERE docstatus = 1
ORDER BY payroll_month DESC, payroll_sheet_type
LIMIT 12;
