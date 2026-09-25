"""Build PAYROLL_TEST_CREDENTIALS.docx (stdlib only)."""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parents[1] / "hrms" / "payroll" / "setup" / "PAYROLL_TEST_CREDENTIALS.docx"


def w(text: str, bold: bool = False) -> str:
	t = escape(text)
	if bold:
		return f"<w:r><w:rPr><w:b/></w:rPr><w:t xml:space=\"preserve\">{t}</w:t></w:r>"
	return f"<w:r><w:t xml:space=\"preserve\">{t}</w:t></w:r>"


def para(*runs: str, style: str | None = None) -> str:
	ppr = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
	return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def table_row(cells: list[str], header: bool = False) -> str:
	tr = []
	for cell in cells:
		tpr = "<w:tcPr><w:shd w:val=\"clear\" w:color=\"auto\" w:fill=\"D9E2F3\"/></w:tcPr>" if header else ""
		tr.append(
			f"<w:tc>{tpr}<w:p>{w(cell, bold=header)}</w:p></w:tc>"
		)
	return f"<w:tr>{''.join(tr)}</w:tr>"


def build_document_xml() -> str:
	rows = [
		table_row(
			["Login email", "Password", "Role", "Linked ID", "What to test"],
			header=True,
		),
		table_row(
			[
				"payroll.employee1@mysite.local",
				"Test@2026",
				"Employee",
				"MSID 001",
				"Request own payslip; submit; download after Approved",
			]
		),
		table_row(
			[
				"payroll.employee2@mysite.local",
				"Test@2026",
				"Employee",
				"MSID 002",
				"Same as employee 1",
			]
		),
		table_row(
			[
				"payroll.employee3@mysite.local",
				"Test@2026",
				"Employee",
				"MSID 003",
				"Same as employee 1",
			]
		),
		table_row(
			[
				"payroll.hr@mysite.local",
				"Test@2026",
				"HR Manager",
				"—",
				"Upload/import payroll, dashboard, create/approve payslip requests, download",
			]
		),
		table_row(
			[
				"payroll.daf@mysite.local",
				"Test@2026",
				"DAF",
				"—",
				"View Staff Payroll Dashboard only",
			]
		),
		table_row(
			[
				"payroll.md@mysite.local",
				"Test@2026",
				"MD",
				"—",
				"View Staff Payroll Dashboard only",
			]
		),
	]
	tbl = (
		"<w:tbl>"
		"<w:tblPr><w:tblW w:w=\"5000\" w:type=\"pct\"/></w:tblPr>"
		"<w:tblGrid>"
		+ "".join("<w:gridCol w:w=\"1800\"/>" for _ in range(5))
		+ "</w:tblGrid>"
		+ "".join(rows)
		+ "</w:tbl>"
	)

	body = [
		para(w("Payroll test credentials", bold=True), style="Title"),
		para(w("Use on site mysite.local to test imported payroll, Staff Payroll Dashboard, and Payslip Requests.")),
		para(w("Desk URL: ", bold=True), w("http://127.0.0.1:8000")),
		para(w("Default password (all users): ", bold=True), w("Test@2026")),
		para(w("Company (typical): ", bold=True), w("Muganga Sacco")),
		para(w("Test users", bold=True), style="Heading1"),
		tbl,
		para(w("Employee self-service payslip", bold=True), style="Heading2"),
		para(w("1. Log in as payroll.employee1@mysite.local")),
		para(w("2. Open Payslip Request → New → employee fixed to MSID 001 → set period → Save → Submit for Approval")),
		para(w("3. Log in as payroll.hr@mysite.local → Approve the pending request")),
		para(w("4. Log in as employee1 → Download Payslip on the approved request")),
		para(w("Expected: employee cannot request or see other staff payslips.", bold=True)),
		para(w("HR creates request for staff", bold=True), style="Heading2"),
		para(w("HR → Payslip Request → New → pick Employee → Save → Submit → Approve → Download")),
		para(w("Dashboard access", bold=True), style="Heading2"),
		para(w("HR Manager: full dashboard. DAF / MD: view only. Employee: use Payslip Request.")),
		para(w("Create or reset test users", bold=True), style="Heading1"),
		para(w("cd ~/frappe-bench")),
		para(w("bench --site mysite.local execute hrms.payroll.setup.create_payroll_test_users.create_payroll_test_users")),
		para(w("Source: hrms/payroll/setup/create_payroll_test_users.py")),
		para(w("Security", bold=True), style="Heading1"),
		para(w("Development and UAT only. Do not use on production. Disable test users before go-live.")),
	]

	return (
		'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
		'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
		f"<w:body>{''.join(body)}<w:sectPr/></w:body></w:document>"
	)


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>"""


def main() -> None:
	OUT.parent.mkdir(parents=True, exist_ok=True)
	with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
		z.writestr("[Content_Types].xml", CONTENT_TYPES)
		z.writestr("_rels/.rels", RELS)
		z.writestr("word/document.xml", build_document_xml())
		z.writestr("word/_rels/document.xml.rels", DOC_RELS)
	print(OUT)


if __name__ == "__main__":
	main()
