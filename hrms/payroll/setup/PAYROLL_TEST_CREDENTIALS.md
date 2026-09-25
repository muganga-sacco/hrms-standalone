# Payroll test credentials

Use these accounts on the **mysite.local** desk to test imported payroll, the Staff Payroll Dashboard, and Payslip Requests.

| Item | Value |
|------|--------|
| **Desk URL** | `http://127.0.0.1:8000` (or your bench host) |
| **Default password (all users below)** | `Test@2026` |
| **Company (typical)** | Muganga Sacco |

---

## Test users

| Login email | Role | Linked payroll ID | What to test |
|-------------|------|-------------------|--------------|
| `payroll.employee1@mysite.local` | Employee | MSID 001 | Request **own** payslip only; submit for HR approval; download after **Approved** |
| `payroll.employee2@mysite.local` | Employee | MSID 002 | Same as employee 1 (different staff record) |
| `payroll.employee3@mysite.local` | Employee | MSID 003 | Same as employee 1 (different staff record) |
| `payroll.hr@mysite.local` | HR Manager | — | Full payroll ops; **see all** payslip requests; **Approve/Reject**; **Export** list to Excel; can create requests for any employee |
| `payroll.daf@mysite.local` | DAF | Employee link optional | **Staff Payroll Dashboard** (view); **request own payslip** via **My Payslips** / **Payslip Request** (user must be linked on **Employee**) |
| `payroll.md@mysite.local` | MD | Employee link optional | Same as DAF |

---

## Quick test flows

### Employee self-service payslip

1. Log in as `payroll.employee1@mysite.local`.
2. Open **Payroll → My Payslips** (employee home), click **New Payslip Request**, or use **Ctrl+G** → **Payslip Request List**.
3. **New** → employee is fixed to MSID 001 → set period → **Save** → **Submit for Approval**.
4. Log in as `payroll.hr@mysite.local` → open the pending request → **Approve**.
5. Log back in as employee1 → open the same request → **Download Payslip**.

**Expected:** Employee cannot choose another employee or see other employees’ requests.

### HR creates a request on behalf of staff

1. Log in as `payroll.hr@mysite.local`.
2. **Payslip Request → New** → pick any **Employee** → period → **Save** → **Submit for Approval**.
3. **Approve** (same or another HR user) → **Download Payslip**.

### Dashboard access

| User | Staff Payroll Dashboard |
|------|-------------------------|
| HR Manager | Full (including export / payslip actions for HR) |
| DAF, MD | View dashboard |
| Employee | Not the primary path; use Payslip Request |

---

## Import lumpsum Excel (HR only)

1. Log in as **`payroll.hr@mysite.local`**.
2. **Payroll Excel Upload** → New → **Company** → **Payroll Month** (e.g. **2026-09-01** or any day in September) → attach **`LUMPSUM.xlsx`**.
3. **Payroll Sheet Type**: leave **Auto Detect** (detects **Lumpsum**) or choose **Lumpsum**.
4. **Save** → **Import from Excel**.
5. View on **Staff Payroll Dashboard** → **Sheet Type** = **Lumpsum** (month **September 2026** for the sample file).

Lumpsum rows are stored separately from monthly **Staff Payroll** (same employee + month can have both types).

---

## Create or reset test users

From the bench directory (WSL example):

```bash
cd ~/frappe-bench
bench --site mysite.local execute hrms.payroll.setup.create_payroll_test_users.create_payroll_test_users
```

Optional custom password:

```bash
bench --site mysite.local execute hrms.payroll.setup.create_payroll_test_users.create_payroll_test_users --kwargs "{'password': 'YourPassword'}"
```

The script:

- Creates or updates the six users and roles (**DAF**, **MD** if missing).
- Sets the password and re-applies roles.
- Links **MSID 001–003** to the three employee logins (creates **Employee** records from imported payroll data if needed).

Source: `hrms/payroll/setup/create_payroll_test_users.py`

---

## Troubleshooting “Not permitted” on Payslip Request

1. **Log out and log in again** after running the test-user script (roles are cached in the session).
2. Re-run the create script (fixes missing **Employee** / **Desk User** roles):

   `bench --site mysite.local execute hrms.payroll.setup.create_payroll_test_users.create_payroll_test_users`

3. Open the list via **Ctrl+G** → **Payslip Request List** → **+ Add**.

---

## Security note

These accounts are for **development and UAT only**. Do not use `Test@2026` or these emails on production. Disable or delete test users before go-live.
