SELECT parent, role, `read`, `export` FROM `tabCustom DocPerm`
WHERE parent='Imported Payroll Record'
ORDER BY role;
SELECT parent, role, `read` FROM `tabDocPerm`
WHERE parent='Imported Payroll Record' AND `read`=1
ORDER BY role;
