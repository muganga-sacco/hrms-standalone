SELECT role, `read` FROM tabDocPerm WHERE parent='Page' AND role IN ('Desk User','DAF','MD','HR Manager');
SELECT role FROM `tabHas Role` WHERE parent='payroll.daf@mysite.local';
