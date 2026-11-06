SELECT * FROM `tabBlock Module` WHERE parent='payroll.employee1@mysite.local' OR parent='Employee';
SELECT module FROM `tabModule Profile Detail` mpd
JOIN `tabModule Profile` mp ON mp.name = mpd.parent
JOIN tabUser u ON u.module_profile = mp.name
WHERE u.name='payroll.employee1@mysite.local';
