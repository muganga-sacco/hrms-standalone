"""Generate a minimal LUMPSUM.xlsx for parser/import smoke tests."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


def build_workbook() -> Workbook:
	wb = Workbook()
	ws = wb.active
	ws.title = "LUMPSUM"
	ws["A1"] = "LUMPSUM PAYROLL September 2026"
	headers = [
		"S/N",
		"ID Number",
		"Names",
		"Department",
		"Position",
		"Gross Lumpsum",
		"PAYE",
		"Pension Employee 6%",
		"Pension Employer 6%",
		"Net Salary",
		"Account Number",
		"Beneficiary Bank",
	]
	ws.append(headers)
	rows = [
		(1, "MSID 001", "AB", "Operations", "Officer", 1_500_000, 450_000, 90_000, 90_000, 960_000, "1234567890", "BK"),
		(2, "MSID 002", "BC", "Finance", "Accountant", 1_200_000, 300_000, 72_000, 72_000, 828_000, "0987654321", "BK"),
		(3, "MSID 003", "DE", "HR", "Assistant", 900_000, 180_000, 54_000, 54_000, 666_000, "1122334455", "BK"),
	]
	for row in rows:
		ws.append(list(row))
	ws.append(["", "GRAND TOTAL", "", "", "", 3_600_000, "", "", "", 2_454_000, "", ""])
	return wb


def main() -> None:
	out_dir = Path(__file__).resolve().parent / "fixtures"
	out_dir.mkdir(parents=True, exist_ok=True)
	out_path = out_dir / "LUMPSUM.sample.xlsx"
	build_workbook().save(out_path)
	print(out_path)


if __name__ == "__main__":
	main()
