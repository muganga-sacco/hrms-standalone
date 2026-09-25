SELECT role FROM `tabHas Role` WHERE parent='staff-payroll-dashboard' AND parenttype='Page';
SELECT u.name, GROUP_CONCAT(h.role ORDER BY h.role) AS roles
FROM tabUser u
LEFT JOIN `tabHas Role` h ON h.parent=u.name AND h.parenttype='User'
WHERE u.name LIKE 'payroll.%'
GROUP BY u.name;
