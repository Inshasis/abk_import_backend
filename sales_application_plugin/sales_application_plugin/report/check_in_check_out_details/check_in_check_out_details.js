// Copyright (c) 2024, Akhilam INC and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Check-In Check-Out Details"] = {
	"filters": [
		{
			"fieldname": "from_date", 
			"label": "From Date", 
			"fieldtype": "Date", 
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "to_date", 
			"label": "To Date", 
			"fieldtype": "Date", 
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), 1)
		},
    	{
			"fieldname": "sales_person", 
			"label": "Sales Person", 
			"fieldtype": "Link", 
     		"options": "Sales Person"
		},
	]
};
