import frappe
from sales_application_plugin.api.utils import create_response,get_children,get_child,get_url_for_pdf
from frappe.utils import (getdate,today)
from erpnext.accounts.party import get_party_details
import json


@frappe.whitelist()
def sales_invoice():
    invoice = frappe.local.form_dict.invoice

    sales_invoice_data =  frappe.db.sql("""
		select si.name, si.posting_date,si.due_date, si.project, si.customer, si.remarks, si.total, si.total_taxes_and_charges as tax, si.grand_total, si.total_advance, si.status, si.discount_amount, si.rounding_adjustment
		from `tabSales Invoice` si where si.name = %(name)s""", {
            "name" : invoice
        } , as_dict=1)
    
    
    invoice_data = None
    if len(sales_invoice_data) >0:
        invoice_data = sales_invoice_data[0]

        if invoice_data:
            sales_invoice_items =  frappe.db.sql("""
            select sii.item_code, sii.item_name, sii.description, sii.brand, sii.image, sii.qty, sii.stock_uom, sii.rate, sii.amount
            from `tabSales Invoice Item` sii where sii.parent = %(name)s""", {
                "name" : invoice
            } , as_dict=1)

            invoice_data["items"] = sales_invoice_items
            invoice_data["url"] = get_url_for_pdf("Sales Invoice" , invoice_data.name)
            

    create_response(200 , "Sales Report fetched succcessfully", invoice_data if invoice_data is not None else {})


@frappe.whitelist()
def sales_order():
    order = frappe.local.form_dict.order

    sales_order_data =  frappe.db.sql("""
		select name, customer, transaction_date, delivery_date, grand_total , advance_paid as total_advance, status, delivery_status, per_delivered, per_billed, billing_status, base_grand_total, discount_amount, order_type, rounding_adjustment
		from `tabSales Order` where name = %(name)s""", {
            "name" : order
        } , as_dict=1)
      
    if len(sales_order_data) > 0:
        order_data = sales_order_data[0]

        if order_data:
            sales_order_items =  frappe.db.sql("""
            select sii.item_code, sii.item_name, sii.description, sii.brand, sii.image, sii.qty, sii.stock_uom, sii.rate, sii.amount
            from `tabSales Order Item` sii where sii.parent = %(name)s""", {
                "name" : order
            } , as_dict=1)

            sales_taxes = frappe.db.sql("""
            select sii.item_code, sii.item_name, sii.description, sii.brand, sii.image, sii.qty, sii.stock_uom, sii.rate, sii.amount
            from `tabSales Order Item` sii where sii.parent = %(name)s""", {
                "name" : order
            } , as_dict=1)

            order_data["items"] = sales_order_items
            order_data["url"] = get_url_for_pdf("Sales Order" , order_data.name)
            

    create_response(200 , "Sales Report fetched succcessfully", order_data if order_data is not None else {})


@frappe.whitelist()
def receipt_details():
    pid = frappe.local.form_dict.pid

    if "ACC-JV" in pid:
        receipt_data = frappe.db.sql("""
            select je.name, je.total_credit as paid_amount, je.name, je.posting_date, je.remark as remarks, jea.payment_ref
            from `tabJournal Entry` je
            left join 
            (select name , parent , group_concat(CONCAT_WS(':', reference_type , reference_name, credit)) as payment_ref from `tabJournal Entry Account` ja 
            where ja.parent = %(pid)s and ja.party_type = 'Customer' group by ja.parent) as jea
            on je.name = jea.parent where je.name = %(pid)s""", {
                "pid" : pid
            } , as_dict=1)
        if len(receipt_data) > 0:
            receipt_data[0]["url"] = get_url_for_pdf("Journal Entry" , pid)
    else:            
        receipt_data =  frappe.db.sql("""
            select pe.name, pe.payment_type, pe.posting_date, pe.reference_date, pe.remarks , pe.paid_to, pe.paid_amount, pr.payment_ref
            from `tabPayment Entry` pe
            left join 
            (select name,parent , group_concat(CONCAT_WS(':', reference_doctype , reference_name, allocated_amount)) as payment_ref from `tabPayment Entry Reference` per 
            where per.parent = %(pid)s group by per.parent) as pr
            on pe.name = pr.parent where pe.name = %(pid)s""", {
                "pid" : pid
            } , as_dict=1)
        if len(receipt_data) > 0:
            receipt_data[0]["url"] = get_url_for_pdf("Payment Entry" , pid)
         
    create_response(200 , "Receipt Details fetched succcessfully", receipt_data[0] if len(receipt_data) > 0 else {})

@frappe.whitelist()
def create_sales_order():
    customer  = frappe.local.form_dict.customer
    delivery_date = frappe.local.form_dict.delivery_date
    items = frappe.local.form_dict.sales_items
    sales_team = frappe.local.form_dict.sales_team
    series  = frappe.local.form_dict.series
    naming_series = frappe.local.form_dict.naming_series
    narration = frappe.local.form_dict.narration
    
    price_list = get_customer_price_list(frappe.local.form_dict.customer)
    company = frappe.get_single("Global Defaults").default_company
    

    if not price_list:
        create_response(406,"Price list is not assigned in customer group of customer {}".format(frappe.local.form_dict.customer), {})
        return

    try:
        so = frappe.get_doc({
            'doctype': "Sales Order",
            'company' : company,
            'customer' : customer,
            'delivery_date' : delivery_date,
            'sales_team' : sales_team,
            'price_list'  : price_list,
            'items': items,
            'order_type' : "Sales",
            'custom_remarks' : narration,
            'naming_series' : series,
            'custom_series_name' : naming_series
        })
        
        party_details = get_party_details(party=so.customer,party_type='Customer',posting_date=frappe.utils.today(),company=company,doctype='Sales Order')
        so.taxes_and_charges = party_details.get("taxes_and_charges")
        so.set("taxes", party_details.get("taxes"))        
        so.set_missing_values()
        so.calculate_taxes_and_totals()
        res = so.insert(ignore_permissions=True)

        # res.submit()
        create_response(200 , "Sales Order created succcessfully", )
    except Exception as e:
        frappe.log_error(title = "Sales Order Creation",message=frappe.get_traceback())
        create_response(406,"Sales Order Creation Error", e)

def get_customer_price_list(customer):
    customer_group = frappe.db.get_value("Customer",customer,"customer_group")
    return frappe.db.get_value("Customer Group",customer_group,"default_price_list")
    

@frappe.whitelist()
def get_sales_hierarchy():
    label= parent= frappe.local.form_dict.sales_person
    doctype = "Sales Person"

    data = get_children(doctype, parent)     
    parent = dict(name= label)
    child = get_child([], doctype , data)
    parent["children"] = child
    return create_response(200 , "Sales Person Hierarchy Fetched succcessfully", parent)




