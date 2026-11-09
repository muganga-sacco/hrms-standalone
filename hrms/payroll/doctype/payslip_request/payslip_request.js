// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// License: GNU General Public License v3. See license.txt

function payslip_is_hr_approver() {
	return (
		frappe.session.user === "Administrator" ||
		frappe.user.has_role("HR Manager") ||
		frappe.user.has_role("HR User")
	);
}

function payslip_is_daf() {
	return frappe.session.user === "Administrator" || frappe.user.has_role("DAF");
}

function payslip_is_md() {
	return frappe.session.user === "Administrator" || frappe.user.has_role("MD");
}

function payslip_hr_picks_employee() {
	return payslip_is_hr_approver();
}

const PAYSLIP_MONTHS = [
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
];

function payslip_period_from_date(value) {
	if (value) {
		const parts = String(value).split("-");
		const month_index = parseInt(parts[1] || "1", 10) - 1;
		if (parts[0] && month_index >= 0 && month_index <= 11) {
			return { year: parts[0], month_name: PAYSLIP_MONTHS[month_index] };
		}
	}
	const now = frappe.datetime.str_to_obj(frappe.datetime.nowdate());
	return { year: String(now.getFullYear()), month_name: PAYSLIP_MONTHS[now.getMonth()] };
}

function payslip_date_from_period(year, month_name) {
	const month_index = PAYSLIP_MONTHS.indexOf(month_name);
	if (!year || month_index < 0) {
		return "";
	}
	return `${year}-${String(month_index + 1).padStart(2, "0")}-01`;
}

function payslip_show_select(frm, fieldname, value) {
	const field = frm.fields_dict[fieldname];
	// set_input before the <select> exists records the option list and then
	// refuses to fill the real dropdown, so the field stays blank.
	if (field && field.$input && field.$input[0] && !field.$input[0].options.length) {
		field.last_options = null;
		field.set_options();
	}
	if (!value || frm.doc[fieldname] === value) {
		if (value && field && field.$input) {
			field.set_input(value);
		}
		return;
	}
	if (!field || !field.$input) {
		frm.doc[fieldname] = value;
		return;
	}
	frm.doc[fieldname] = value;
	field.set_input(value);
}

function payslip_sync_single(frm) {
	const value = payslip_date_from_period(frm.doc.payroll_year, frm.doc.payroll_month_name);
	if (!value) {
		return;
	}
	if (frm.doc.period_type === "From month – To month") {
		if (frm.doc.from_month !== value) {
			frm.set_value("from_month", value);
		}
		return;
	}
	if (frm.doc.payroll_month !== value) {
		frm.set_value("payroll_month", value);
	}
}

function payslip_sync_range(frm) {
	const to_month = payslip_date_from_period(frm.doc.to_year, frm.doc.to_month_name);
	if (to_month && frm.doc.to_month !== to_month) {
		frm.set_value("to_month", to_month);
	}
	payslip_sync_single(frm);
}

function payslip_fill_period(frm) {
	if ((frm.is_new() || frm.doc.status === "Draft") && frm.doc.period_type !== "From month – To month") {
		frm.set_value("period_type", "From month – To month");
	}
	const is_range = frm.doc.period_type === "From month – To month";
	const start = payslip_period_from_date(
		is_range ? frm.doc.from_month || frm.doc.payroll_month : frm.doc.payroll_month
	);
	const to_period = payslip_period_from_date(frm.doc.to_month || frm.doc.payroll_month);
	payslip_show_select(frm, "payroll_year", start.year);
	payslip_show_select(frm, "payroll_month_name", start.month_name);
	payslip_show_select(frm, "to_year", to_period.year);
	payslip_show_select(frm, "to_month_name", to_period.month_name);
	if (frm.is_new() || frm.doc.status === "Draft") {
		payslip_sync_single(frm);
		payslip_sync_range(frm);
	}
}

frappe.ui.form.on("Payslip Request", {
	setup(frm) {
		if (!payslip_hr_picks_employee()) {
			frm.set_query("employee", () => ({
				filters: { user_id: frappe.session.user },
			}));
		}
	},

	onload(frm) {
		payslip_fill_period(frm);
		if (frm.is_new() && !payslip_hr_picks_employee()) {
			frappe.call({
				method:
					"hrms.payroll.doctype.payslip_request.payslip_request.get_self_employee_for_payslip_request",
				callback(r) {
					if (r.message && r.message.name) {
						frm.set_value("employee", r.message.name);
					} else {
						frappe.msgprint(
							__(
								"Your login is not linked to an Employee record. Ask HR to set User ID on your Employee profile."
							)
						);
					}
				},
			});
		}
	},

	refresh(frm) {
		frm.clear_custom_buttons();
		frm.remove_custom_button(__("Add Cachet"));
		const is_hr = payslip_is_hr_approver();
		const is_daf = payslip_is_daf();
		const is_md = payslip_is_md();
		payslip_fill_period(frm);

		if (!payslip_hr_picks_employee()) {
			frm.set_df_property("employee", "read_only", 1);
		}

		if (frm.doc.status === "Draft" && !frm.is_new()) {
			frm.add_custom_button(__("Submit for Approval"), () => {
				frappe.call({
					method: "hrms.payroll.doctype.payslip_request.payslip_request.submit_payslip_request",
					args: { docname: frm.doc.name },
					freeze: true,
					callback() {
						frm.reload_doc();
						frappe.show_alert({ message: __("Submitted to HR"), indicator: "green" });
					},
				});
			}).addClass("btn-primary");
		}

		const after_own = (is_own) => {
			payslip_add_decision_buttons(frm, { is_hr, is_daf, is_md, is_own });
		};
		if (!frm.doc.employee) {
			after_own(false);
		} else {
			frappe.db.get_value("Employee", frm.doc.employee, "user_id", (r) => {
				const uid = typeof r === "string" ? r : r && r.user_id;
				after_own(!!(uid && uid === frappe.session.user));
			});
		}
	},
});

function payslip_add_decision_buttons(frm, roles) {
		const { is_hr, is_daf, is_md, is_own } = roles;

		if (
			((is_hr || is_daf || is_md) &&
				["Pending HR", "Pending DAF", "Pending MD", "Pending"].includes(frm.doc.status)) ||
			frm.doc.status === "Approved"
		) {
			frm.add_custom_button(__("Preview Payslip"), () => {
				payslip_open_preview(frm);
			});
		}

		if (!is_own && is_hr && (frm.doc.status === "Pending HR" || frm.doc.status === "Pending")) {
			frm.add_custom_button(__("Approve"), () => {
				payslip_open_preview(frm, () => {
					frappe.call({
						method: "hrms.payroll.doctype.payslip_request.payslip_request.approve_payslip_request",
						args: { docname: frm.doc.name },
						freeze: true,
						callback() {
							frm.reload_doc();
						},
					});
				});
			}).addClass("btn-primary");
		}

		if (!is_own && is_daf && frm.doc.status === "Pending DAF") {
			frm.add_custom_button(__("Approve"), () => {
				payslip_open_preview(frm, () => {
					frappe.call({
						method: "hrms.payroll.doctype.payslip_request.payslip_request.daf_approve_payslip_request",
						args: { docname: frm.doc.name },
						freeze: true,
						callback() {
							frm.reload_doc();
						},
					});
				});
			}).addClass("btn-primary");
		}

		if (!is_own && is_md && frm.doc.status === "Pending MD") {
			frm.add_custom_button(__("Approve"), () => {
				payslip_open_preview(frm, () => {
					frappe.call({
						method: "hrms.payroll.doctype.payslip_request.payslip_request.md_approve_payslip_request",
						args: { docname: frm.doc.name },
						freeze: true,
						callback() {
							frm.reload_doc();
						},
					});
				});
			}).addClass("btn-primary");
		}

		if (
			!is_own &&
			(is_hr || is_daf || is_md) &&
			["Pending HR", "Pending DAF", "Pending MD", "Pending"].includes(frm.doc.status)
		) {
			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					[
						{
							fieldname: "rejection_reason",
							fieldtype: "Small Text",
							label: __("Reason"),
							reqd: 1,
						},
					],
					(values) => {
						frappe.call({
							method: "hrms.payroll.doctype.payslip_request.payslip_request.reject_payslip_request",
							args: {
								docname: frm.doc.name,
								rejection_reason: values.rejection_reason,
							},
							freeze: true,
							callback() {
								frm.reload_doc();
							},
						});
					},
					__("Reject Payslip Request")
				);
			});
		}

		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("Download Payslip"), () => {
				const qs = new URLSearchParams({ docname: frm.doc.name });
				window.location.href = frappe.urllib.get_full_url(
					`/api/method/hrms.payroll.doctype.payslip_request.payslip_request.download_payslip_for_request?${qs}`
				);
			}).addClass("btn-primary");
		}

		if (!is_hr && frm.doc.status !== "Draft") {
			[
				"period_type",
				"months",
				"payroll_year",
				"payroll_month_name",
				"to_year",
				"to_month_name",
				"remarks",
				"remarks_other",
			].forEach((fieldname) => frm.set_df_property(fieldname, "read_only", 1));
		}
		frm.remove_custom_button(__("Add Cachet"));
}

frappe.ui.form.on("Payslip Request", {
	payroll_year: payslip_sync_single,
	payroll_month_name: payslip_sync_single,
	period_type: payslip_sync_range,
	to_year: payslip_sync_range,
	to_month_name: payslip_sync_range,
});

function payslip_escape(value) {
	return frappe.utils.escape_html(value == null ? "" : String(value));
}

function payslip_file_src(url) {
	if (!url) {
		return "";
	}
	const value = String(url);
	if (value.startsWith("data:") || value.startsWith("http://") || value.startsWith("https://")) {
		return value;
	}
	return frappe.urllib.get_full_url(value);
}

function payslip_sign_block(block) {
	block = block || {};
	const src = payslip_file_src(block.image_data_uri);
	const img = src
		? `<img src="${payslip_escape(src)}" alt="signature" style="height:70px;width:auto;max-width:210px;object-fit:contain;display:block;">`
		: "";
	const when = block.approved_on ? `Approved on ${payslip_escape(block.approved_on)}` : "";
	return `
		<td style="border:0;vertical-align:top;padding:0 18px 0 0;">
			<div style="font-weight:700;min-height:18px;">${payslip_escape(block.heading || "")}</div>
			<div style="font-weight:700;min-height:18px;">${payslip_escape(block.name || "")}</div>
			<div style="font-size:10pt;min-height:28px;margin-top:1px;">${payslip_escape(block.title || "")}</div>
			<div style="height:74px;margin:6px 0 4px;">${img}</div>
			<div style="font-size:10pt;min-height:16px;">${when}</div>
		</td>
	`;
}

function payslip_preview_html(data) {
	const include_ict = Boolean(data.include_ict);
	const earning_labels = [
		"Pay Period",
		"Payment Date",
		"Basic Salary",
		"Transport allowance",
		"TC Allowance",
	];
	if (include_ict) {
		earning_labels.push("ICT Allowance");
	}
	earning_labels.push("Bonus and other Incentives", "Gross Lumpsum", "Gross Salary");
	const deduction_labels = ["PAYE", "Pension", "Maternity", "CBHI", "Other Deduction"];
	const th_style =
		"border:1px solid #000;padding:4px 3px;text-align:center;color:#000;font-weight:700;background:#ED7D31;";
	const th_green =
		"border:1px solid #000;padding:4px 3px;text-align:center;color:#000;font-weight:700;background:#00B050;";
	const td_style = "border:1px solid #000;padding:4px 3px;text-align:center;";
	const head1 =
		earning_labels
			.map((label) => `<th rowspan="2" style="${th_style}">${payslip_escape(label)}</th>`)
			.join("") +
		`<th colspan="${deduction_labels.length}" style="${th_green}">DEDUCTIONS</th>` +
		`<th rowspan="2" style="${th_green}">TOTAL Deductions</th>` +
		`<th rowspan="2" style="${th_style}">NET SALARY</th>`;
	const head2 = deduction_labels
		.map((label) => `<th style="${th_green}">${payslip_escape(label)}</th>`)
		.join("");
	const rows = (data.rows || [])
		.map(
			(row) =>
				`<tr>${(row || [])
					.map((cell) => `<td style="${td_style}">${payslip_escape(cell)}</td>`)
					.join("")}</tr>`
		)
		.join("");
	const logo_src = payslip_file_src(data.logo_url);
	const photo_src = payslip_file_src(data.photo_url);
	const signoff = data.signoff || {};
	const sign_blocks = ["verified_by", "approved_by"]
		.map((key) => {
			const block = signoff[key];
			if (!block || !(block.name || block.image_data_uri || block.image_url)) {
				return "";
			}
			if (!block.heading) {
				block.heading = key === "verified_by" ? "Verified by" : "Approved by";
			}
			return payslip_sign_block(block);
		})
		.join("");
	const cachet = signoff.cachet || {};
	const cachet_src = payslip_file_src(cachet.image_data_uri || cachet.image_url);
	const cachet_cell = cachet_src
		? `<td class="cachet" style="border:0;text-align:right;vertical-align:top;padding:0;width:32%;">
			<div style="min-height:18px;">&nbsp;</div>
			<div style="min-height:18px;">&nbsp;</div>
			<div style="min-height:28px;">&nbsp;</div>
			<div style="height:145px;margin:6px 0 4px;">
				<img src="${payslip_escape(cachet_src)}" alt="cachet" style="height:140px;width:auto;max-width:100%;object-fit:contain;">
			</div>
		</td>`
		: "";
	return `
		<div class="payslip-sheet" style="font-family:Calibri,Arial,sans-serif;color:#111;background:#fff;padding:10px 8px;">
			<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;">
				<div>${
					logo_src
						? `<img src="${payslip_escape(logo_src)}" alt="logo" style="max-height:70px;max-width:220px;">`
						: ""
				}</div>
				<div>${
					photo_src
						? `<img src="${payslip_escape(photo_src)}" alt="employee" style="max-height:86px;max-width:86px;object-fit:cover;">`
						: ""
				}</div>
			</div>
			<div style="text-align:center;font-weight:700;text-decoration:underline;letter-spacing:1px;margin:2px 0 8px;">PAYSLIP</div>
			<div style="font-size:11px;line-height:1.4;margin:6px 0 10px;">
				<div><strong>EMPLOYEE NAMES:</strong> ${payslip_escape(data.employee_name)}</div>
				<div><strong>EMPLOYEE ID:</strong> ${payslip_escape(data.employee_id_number)}</div>
				<div><strong>POSITION:</strong> ${payslip_escape(data.position)}</div>
				<div><strong>DEPARTMENT:</strong> ${payslip_escape(data.department)}</div>
				<div><strong>ACCOUNT NUMBER:</strong> ${payslip_escape(data.account_number)}</div>
				<div><strong>BENEFICIARY BANK:</strong> ${payslip_escape(data.bank)}</div>
			</div>
			<div style="overflow-x:auto;">
				<table style="width:100%;border-collapse:collapse;table-layout:fixed;font-size:8pt;">
					<thead><tr>${head1}</tr><tr>${head2}</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
			<div style="font-weight:700;margin:18px 0 10px;">For MUGANGA SACCO</div>
			<table style="width:100%;border-collapse:collapse;table-layout:fixed;font-size:11pt;">
				<tr>${sign_blocks}${cachet_cell}</tr>
			</table>
		</div>
	`;
}

function payslip_open_preview(frm, on_approve) {
	frappe.call({
		method: "hrms.payroll.doctype.payslip_request.payslip_request.preview_payslip_for_request",
		args: { docname: frm.doc.name },
		freeze: true,
		freeze_message: __("Loading payslip preview"),
		callback(r) {
			const dialog = new frappe.ui.Dialog({
				title: on_approve ? __("Preview payslip before approval") : __("Payslip Preview"),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "preview" }],
				primary_action_label: on_approve ? __("Approve") : __("Close"),
				primary_action() {
					dialog.hide();
					if (on_approve) {
						on_approve();
					}
				},
			});
			if (on_approve) {
				dialog.set_secondary_action_label(__("Cancel"));
				dialog.set_secondary_action(() => dialog.hide());
			}
			dialog.fields_dict.preview.$wrapper.css({
				overflow: "auto",
				background: "#fff",
				maxHeight: "75vh",
			});
			const data = r.message || {};
			dialog.fields_dict.preview.$wrapper.html(data.html || payslip_preview_html(data));
			dialog.show();
		},
	});
}
