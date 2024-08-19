# Copyright (c) 2024, Akhilam INC and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date must be before To Date"))
	columns, data = get_columns(filters), get_data(filters)
	return columns, data


def get_data(filters):

	conditions = get_conditions(filters)
	data = frappe.db.sql("""
		SELECT cico.customer,cico.in_datetime,cico.out_datetime
		,cico.customer_address,cico.sales_person,cico.checkin_address,cico.notes
		FROM `tabCheckIn-Out` cico
		WHERE cico.sales_person IS NOT NULL {conditions}
	""".format(conditions=conditions), filters,as_dict=True)

	return data


def get_conditions(filters):
	conditions = []

	if filters.get("from_date") and filters.get("to_date"):
		conditions.append("cico.in_datetime BETWEEN %(from_date)s AND %(to_date)s")
	
	if filters.get("sales_person"):
		conditions.append("cico.sales_person = %(sales_person)s")

	return "and {}".format(" and ".join(conditions)) if conditions else ""	


def get_columns(filters):
	columns = [
		{
			"label": _("Checkin Time"), 
			"fieldname": "in_datetime", 
			"fieldtype": "Datetime",
			"width": 180
		},
		{
			"label": _("Checkout Time"),
			"fieldname": "out_datetime",
			"fieldtype": "Datetime",
			"width": 180
		},
		{
			"label": _("Customer"), 
			"fieldname": "customer", 
			"fieldtype": "Link", 
			"options": "Customer", 
			"width": 180
		},
		{
			"label": _("Sales Person"), 
			"fieldname": "sales_person", 
			"fieldtype": "Link",
			"options": "Sales Person", 
			"width": 180
		},
		{
			"label": _("Customer Address"), 
			"fieldname": "customer_address", 
			"fieldtype": "Small text", 
			"width": 220
		},
		{
			"label": _("Checkin Address"), 
			"fieldname": "checkin_address", 
			"fieldtype": "Small Text", 
			"width": 220
		},
		{
			"label": _("Notes"), 
			"fieldname": "notes", 
			"fieldtype": "Small Text", 
			"width": 230
		},
	]
	return columns