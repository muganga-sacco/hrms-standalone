SELECT * FROM `tabBlock Module` WHERE parent IN ('Employee', 'payroll.employee1@mysite.local');
SELECT parent, role FROM `tabHas Role` WHERE parent='payroll.employee1@mysite.local';
SELECT user_type FROM tabUser WHERE name='payroll.employee1@mysite.local';
