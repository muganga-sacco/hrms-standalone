// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

cur_frm.add_fetch('employee', 'employee_name', 'employee_name');

frappe.ui.form.on('Leave Allocation', {
  onload: function (frm) {
    frm.ignore_doctypes_on_cancel_all = ['Leave Ledger Entry'];

    if (!frm.doc.from_date)
      frm.set_value('from_date', frappe.datetime.get_today());

    frm.set_query('employee', function () {
      return {
        query: 'basic.controllers.queries.employee_query',
      };
    });
    frm.set_query('leave_type', function () {
      return {
        filters: {
          is_lwp: 0,
        },
      };
    });
  },

  refresh: function (frm) {
    if (frm._base_total == null) {
      frm._base_total = flt(frm.doc.total_leaves_allocated);
    }
    frm.set_df_property('unused_leaves', 'label', __('Closing Balance'));
    ['unused_leaves', 'new_leaves_allocated', 'total_leaves_allocated'].forEach((fieldname) => {
      frm.set_df_property(fieldname, 'description', '');
      const field = frm.get_field(fieldname);
      if (field && field.set_description) {
        field.set_description('');
      }
    });
    frm.set_intro();

    if (frm.doc.docstatus === 1) {
      frm.page.set_primary_action(__('Update extra days'), () => {
        const extra = flt(frm.doc.new_leaves_allocated);
        if (extra <= 0) {
          frappe.msgprint(__('Type extra days in New Leaves Allocated first.'));
          return;
        }
        frappe.call({
          method: 'hrms.hr.add_leave_allocation_days.apply_extra_days',
          args: { allocation_name: frm.doc.name, extra: extra },
          freeze: true,
          freeze_message: __('Adding extra days...'),
          callback: function (r) {
            if (r.message) {
              frappe.show_alert({
                message: __('Added {0} days. New grant is now {1}.', [
                  extra,
                  r.message.new_leaves_allocated,
                ]),
                indicator: 'green',
              });
              frm.reload_doc();
            }
          },
        });
      });
    }

    if (frm.doc.docstatus === 1 && frm.doc.expired) {
      var valid_expiry = moment(frappe.datetime.get_today()).isBetween(
        frm.doc.from_date,
        frm.doc.to_date
      );
      if (valid_expiry) {
        frm.add_custom_button(__('Expire Allocation'), function () {
          frm.trigger('expire_allocation');
        });
      }
    }

    frm.trigger('load_existing_allocation');
  },

  employee: function (frm) {
    frm.trigger('load_existing_allocation');
  },

  leave_type: function (frm) {
    frm.trigger('load_existing_allocation');
  },

  expire_allocation: function (frm) {
    frappe.call({
      method:
        'hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry.expire_allocation',
      args: {
        allocation: frm.doc,
        expiry_date: frappe.datetime.get_today(),
      },
      freeze: true,
      callback: function (r) {
        if (!r.exc) {
          frappe.msgprint(__('Allocation Expired!'));
        }
        frm.refresh();
      },
    });
  },

  carry_forward: function (frm) {
    frm.trigger('calculate_total_leaves_allocated');
  },

  unused_leaves: function (frm) {
    frm.trigger('recalc_total_from_extra');
  },

  new_leaves_allocated: function (frm) {
    frm.trigger('recalc_total_from_extra');
  },

  load_existing_allocation: function (frm) {
    if (!frm.doc.employee || !frm.doc.leave_type) {
      frm._existing_ctx = { name: null, unused: 0, opening: 0, ledger_new: 0, total: 0 };
      if (frm.doc.__islocal) {
        frm.doc.new_leaves_allocated = 0;
        frm.doc.total_leaves_allocated = 0;
        frm.refresh_field('new_leaves_allocated');
        frm.refresh_field('total_leaves_allocated');
      }
      return;
    }

    frappe.call({
      method: 'hrms.hr.add_leave_allocation_days.get_existing_allocation',
      args: {
        employee: frm.doc.employee,
        leave_type: frm.doc.leave_type,
        name: frm.doc.__islocal ? null : frm.doc.name,
      },
      callback: function (r) {
        const ctx = r.message || {
          name: null,
          unused: 0,
          opening: 0,
          ledger_new: 0,
          total: 0,
        };
        frm._existing_ctx = ctx;
        frm._extra_mode = true;
        frm._base_total = flt(ctx.ledger_new);

        if (!frm.is_dirty()) {
          frm.doc.new_leaves_allocated = 0;
          frm.doc.total_leaves_allocated = frm._base_total;
          frm.doc.unused_leaves = flt(ctx.opening || ctx.unused);
          frm.refresh_field('new_leaves_allocated');
          frm.refresh_field('total_leaves_allocated');
          frm.refresh_field('unused_leaves');
        } else {
          frm.trigger('recalc_total_from_extra');
        }

        frm.set_intro();
        if (!frm.doc.__unsaved) {
          frm.dirty = false;
        }
      },
    });
  },

  recalc_total_from_extra: function (frm) {
    const extra = flt(frm.doc.new_leaves_allocated);
    if (frm._base_total == null) {
      frm._base_total = flt(frm.doc.total_leaves_allocated) - extra;
    }
    frm.doc.total_leaves_allocated = flt(frm._base_total) + extra;
    frm.refresh_field('total_leaves_allocated');
  },

  before_save: function (frm) {
    const extra = flt(frm.doc.new_leaves_allocated);
    const ctx = frm._existing_ctx || {};

    if (frm.doc.__islocal && ctx.name) {
      if (extra <= 0) {
        frappe.throw(__('Type extra days in New Leaves Allocated'));
      }
      frappe.validated = false;
      frappe.call({
        method: 'hrms.hr.add_leave_allocation_days.apply_extra_days',
        args: { allocation_name: ctx.name, extra: extra },
        freeze: true,
        callback: function (r) {
          if (r.message && r.message.name) {
            frappe.show_alert({
              message: __('Added {0} days on {1}', [extra, r.message.name]),
              indicator: 'green',
            });
            frappe.set_route('Form', 'Leave Allocation', r.message.name);
          }
        },
      });
      return;
    }

    if (ctx.ledger_new != null) {
      const stored = flt(ctx.ledger_new) + extra;
      frm.doc.new_leaves_allocated = stored;
      frm.doc.total_leaves_allocated =
        flt(ctx.unused) + stored;
    }
  },

  calculate_total_leaves_allocated: function (frm) {
    if (frm._extra_mode) {
      frm.trigger('recalc_total_from_extra');
      return;
    }
    if (
      cint(frm.doc.carry_forward) == 1 &&
      frm.doc.leave_type &&
      frm.doc.employee
    ) {
      return frappe.call({
        method: 'set_total_leaves_allocated',
        doc: frm.doc,
        callback: function () {
          frm.refresh_fields();
        },
      });
    } else if (cint(frm.doc.carry_forward) == 0) {
      frm.set_value('unused_leaves', 0);
      frm.set_value(
        'total_leaves_allocated',
        flt(frm.doc.new_leaves_allocated)
      );
    }
  },
});

frappe.tour['Leave Allocation'] = [
  {
    fieldname: 'employee',
    title: 'Employee',
    description: __(
      'Select the Employee for which you want to allocate leaves.'
    ),
  },
  {
    fieldname: 'leave_type',
    title: 'Leave Type',
    description: __(
      'Select the Leave Type like Sick leave, Privilege Leave, Casual Leave, etc.'
    ),
  },
  {
    fieldname: 'from_date',
    title: 'From Date',
    description: __(
      'Select the date from which this Leave Allocation will be valid.'
    ),
  },
  {
    fieldname: 'to_date',
    title: 'To Date',
    description: __(
      'Select the date after which this Leave Allocation will expire.'
    ),
  },
  {
    fieldname: 'new_leaves_allocated',
    title: 'New Leaves Allocated',
    description: __('Enter the number of leaves you want to allocate for the period.'),
  },
];
