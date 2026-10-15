<div align="center">
	<a href="https://frappehr.com">
		<img src="https://raw.githubusercontent.com/frappe/hrms/develop/hrms/public/images/frappe-hr-logo.png" height="128" alt="Frappe HR Logo">
	</a>
	<h2>Frappe HR</h2>
	<p align="center">
		<p>Open Source, modern, and easy-to-use HR and Payroll Software for all organizations</p>
	</p>

[![CI](https://github.com/frappe/hrms/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/frappe/hrms/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/frappe/hrms/branch/develop/graph/badge.svg?token=0TwvyUg3I5)](https://codecov.io/gh/frappe/hrms)

[https://frappehr.com](https://frappehr.com)

<div align="center" style="max-height: 40px;">
	<a href="https://frappecloud.com/hrms/signup">
		<img src=".github/try-on-f-cloud-button.svg" height="40">
	</a>
</div>

</div>

## Introduction

Frappe HR has everything you need to drive excellence within the company. It's a complete HRMS solution with over 13 different modules right from Employee Management, Onboarding, Leaves, to Payroll, Taxation, and more!

![HRMS](hrms.png)

## Key Features

- Employee Management
- Employee Lifecycle
- Leave and Attendance
- Shift Management
- Expense Claims and Advances
- Hiring
- Performance Management
- Fleet Management
- Training
- Payroll
- Taxation
- Compensation
- Analytics

## Installation

### Manual Installation

1. [Install bench](https://github.com/frappe/bench).
2. [Install ERPNext](https://github.com/frappe/erpnext#installation).
3. Once ERPNext is installed, add the hrms app to your bench by running

	```sh
	$ bench get-app hrms
	```
4. After that, you can install the hrms app on the required site by running
	```sh
	$ bench --site sitename install-app hrms
	```

## CI/CD

| Workflow | File | Runner | When |
|----------|------|--------|------|
| **CI** | `.github/workflows/hrms-ci.yml` | GitHub-hosted Ubuntu | Push / PR to `Angelique`, or **Run workflow** — compile the app and reject conflict markers |
| **Deploy** | `.github/workflows/deploy.yml` | **Self-hosted** on the bench server (`hrms` label) | Push to `Angelique` or **Run workflow** — `git pull` in the app, then `scripts/deploy.sh` |

Deploy runs `bench migrate`, `bench build --app hrms`, `bench clear-cache`, and `bench restart`. Site config stays on the server.

### One-time server setup

1. The live app must be a git clone of this repo on branch `Angelique`, at `/home/wngelique/frappe-bench/apps/hrms`.
2. GitHub → **Settings → Actions → Runners → New self-hosted runner** → Linux. Add the label **`hrms`** (Runners → gear beside labels). Install that runner as the bench user (`wngelique`) so `bench` and the site files are writable.
3. Optional repository variables (**Settings → Secrets and variables → Actions → Variables**) if the paths differ:
   - `APP_ROOT` (default `/home/wngelique/frappe-bench/apps/hrms`)
   - `BENCH_ROOT` (default `/home/wngelique/frappe-bench`)
   - `BENCH_SITE` (default `mysite.local`)

Manual deploy is the same script:

```bash
cd /home/wngelique/frappe-bench/apps/hrms
git pull --ff-only origin Angelique
BENCH_ROOT=/home/wngelique/frappe-bench BENCH_SITE=mysite.local bash scripts/deploy.sh
```

## Learning and Community

1. [Documentation](https://frappehr.com/docs) - Extensive documentation for Frappe HR.
2. [User Forum](https://discuss.hrms.com/) - Engage with the community of ERPNext users and service providers.
3. [Telegram Group](https://t.me/frappehr) - Get instant help from the community of users.

## Contribute

1. [Issue Guidelines](https://github.com/frappe/erpnext/wiki/Issue-Guidelines) - [Create an issue](https://github.com/frappe/hrms/issues/new)
1. [Contribution Guidelines](https://github.com/frappe/erpnext/wiki/Contribution-Guidelines)

## License

GNU GPL V3. (See [license.txt](license.txt) for more information).

The HR code is licensed as GNU General Public License (v3) and the copyright is owned by Frappe Technologies Pvt Ltd (Frappe) and Contributors.
