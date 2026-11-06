import io
import re
import zipfile

from docx import Document

template = "/home/wngelique/frappe-bench/apps/hrms/hrms/payroll/templates/payslip_template.docx"

import sys

sys.path.insert(0, "/home/wngelique/frappe-bench/apps/hrms")
from hrms.payroll.payroll_import.payslip_docx import _clear_template_logos

doc = Document(template)
_clear_template_logos(doc)
buf = io.BytesIO()
doc.save(buf)
total = 0
with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
    for name in sorted(z.namelist()):
        if name.startswith("word/") and name.endswith(".xml"):
            n = len(re.findall("a:blip", z.read(name).decode()))
            if n:
                print(name, "blips", n)
                total += n
print("total blips after clear", total)
