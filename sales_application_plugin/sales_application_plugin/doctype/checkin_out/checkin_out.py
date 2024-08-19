# Copyright (c) 2023, Akhilam INC and contributors
# For license information, please see license.txt

import frappe
from frappe.contacts.doctype.address.address import get_address_display
from frappe.model.document import Document

class CheckInOut(Document):
	# pass
    def validate(self):
        if self.customer_location:
            self.customer_address = get_address_display(str(self.customer_location))
            
        
