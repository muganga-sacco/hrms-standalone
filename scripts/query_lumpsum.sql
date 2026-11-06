SELECT COUNT(*) AS lumpsum_count FROM `tabImported Payroll Record` WHERE payroll_sheet_type='Lumpsum';
SELECT employee_id_number, employee_name FROM `tabImported Payroll Record` WHERE docstatus=1 LIMIT 5;
