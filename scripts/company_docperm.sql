SELECT role, `read`, `write` FROM tabDocPerm WHERE parent='Company' AND role IN ('HR Manager','HR User','DAF','MD');
SELECT role FROM `tabHas Role` WHERE parent='payroll.hr@mysite.local';
