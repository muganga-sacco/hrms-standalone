# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from frappe.model.document import Document

# import frappe
import frappe

# from hrms

class IncomeTaxSlab(Document):
    
    def validate(self):
        return
        # if self.company:
        #     self.currency = hrms.get_company_currency(self.company)
