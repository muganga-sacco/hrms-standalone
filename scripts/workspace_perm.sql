SELECT role, `read` FROM `tabDocPerm` WHERE parent='Workspace' AND role IN ('Employee', 'Desk User');
