SELECT employee_id_number, payroll_month, payroll_sheet_type, docstatus, net_salary
FROM `tabImported Payroll Record`
WHERE employee_id_number LIKE '%003%' OR employee_id_number LIKE '%MSID%'
ORDER BY payroll_month DESC, payroll_sheet_type;
