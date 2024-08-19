import frappe
import json
from sales_application_plugin.api.utils import create_response,get_item_groups,get_allowed_customer,get_allowed_price_list

@frappe.whitelist()
def item_details(item):
    try:
        if "item" not in frappe.local.form_dict.keys():
            create_response("400","Bad request. Item parameter is mendatory for this request")
            return
        if not frappe.db.exists("Item", item):
            create_response("409","No item Found with ID {}".format(item))
            return
        
        #Get allowed warehouse for user, So user can only see warehouse assigned to him.
        warehouses = frappe.db.get_list('Warehouse', pluck='name')

        #Get allowed Customer for user, So user can only see warehouse assigned to him.
        customers = get_allowed_customer(frappe.session.user)
        # return customers

        allowed_price_lists = get_allowed_price_list(frappe.session.user)
        
        sales_summary = frappe.db.sql("""
        select sum(sii.qty) as total_qty,sum(sii.amount) as total_sales,sii.rate as last_rate,min(sii.rate) as min_rate,max(sii.rate) as max_rate from `tabSales Invoice Item` sii inner join `tabSales Invoice` si on si.name = sii.parent where sii.item_code = %(item)s and si.customer in %(customers)s and si.docstatus = 1 group by sii.item_code order by si.creation desc
        """,({
            'item':item,
            'customers':customers
        }),as_dict=1)

        last_sales_date = frappe.db.sql("""
        select si.posting_date as last_sales_date from `tabSales Invoice Item` sii inner join `tabSales Invoice` si on si.name = sii.parent where sii.item_code = %(item)s and si.docstatus = 1 and si.customer in %(customers)s order by si.posting_date desc limit 1;
        """,({
            'item':item,
            'customers':customers
        }),as_dict=1)

        total_invoice = frappe.db.sql("""
        select count(si.name) as total_count from `tabSales Invoice` si inner join `tabSales Invoice Item` sii on sii.parent = si.name where sii.item_code = %(item)s and si.docstatus = 1 and si.is_return = 0 and si.customer in %(customers)s
        """,({
            'item':item,
            'customers':customers
        }),as_dict=1)

        price_lists = frappe.db.sql("""
        select price_list,price_list_rate,valid_from from `tabItem Price` where item_code = %(item)s and selling = 1 and price_list in %(price_lists)s;
        """,({
            'item':item,
            'price_lists':allowed_price_lists
        }),as_dict=1)

        item_stock = frappe.db.sql("""
        select item_code,actual_qty,reserved_qty,warehouse from `tabBin` where item_code = %(item)s and warehouse in %(warehouse)s;
        """,({
            'item':item,
            'warehouse':warehouses
        }),as_dict=1)

        item_taxes = frappe.db.sql("""
        select item_tax_template,valid_from,tax_category from `tabItem Tax` where parent = %(item)s;
        """,({
            'item':item
        }),as_dict=1)

        pending_sales_summary = frappe.db.sql("""
        select sum(soi.qty - soi.delivered_qty) as total_qty,sum(soi.rate*(soi.qty - soi.delivered_qty)) as total_sales from `tabSales Order Item` soi inner join `tabSales Order` so on so.name = soi.parent where soi.item_code = %(item)s and so.docstatus = 1 and soi.qty != soi.delivered_qty and so.customer in %(customers)s
        """,({
            'item':item,
            'customers':customers
        }),as_dict=1)


        meta = frappe.get_meta("Item")
        # 1 line expr
        hsn_code = frappe.db.get_value("Item",item,"gst_hsn_code") if meta.has_field("gst_hsn_code") else frappe.db.get_value("Item",item,"hsn") if meta.has_field("hsn") else ""
    
        # multiline expr
            # hsn_code = ""
            # if meta.has_field("gst_hsn_code"):
            #     hsn_code = frappe.db.get_value("Item",item,"gst_hsn_code") 
            # if meta.has_field("hsn"):
            #     hsn_code = frappe.db.get_value("Item",item,"hsn")     

        response = {	
                "sales_summary" : {
                    "total_net_sales" : sales_summary[0]['total_sales'] if sales_summary else 0.0, 
                    "last_sale_date" : last_sales_date[0]['last_sales_date'] if last_sales_date else '', 
                    "total_sale_qty" : sales_summary[0]['total_qty'] if sales_summary else 0, 
                    "last_rate" : sales_summary[0]['last_rate'] if sales_summary else 0.0, 
                    "min_rate" : sales_summary[0]['min_rate'] if sales_summary else 0.0, 
                    "max_rate" : sales_summary[0]['max_rate'] if sales_summary else 0.0, 
                    "no_of_invoices" : total_invoice[0]['total_count'] if total_invoice else 0,
                    "pending_sales_order_qty" : pending_sales_summary[0]['total_qty'] if pending_sales_summary else 0,
                    "pending_sales_order_amount" : pending_sales_summary[0]['total_sales'] if pending_sales_summary else 0,
                    "hsn": hsn_code
                },
                "price_list" : price_lists,
                "inventory_closing" : item_stock,
                "item_taxes" : item_taxes
                
                }
        create_response("200","Item details fetched successfully",response)

    except Exception as e:
        create_response("417","something went wrong",e)
        return

@frappe.whitelist()
def get_items_for_group():
    
    item_group = frappe.local.form_dict.item_group
    item_groups = get_item_groups(parent_item_group=item_group)

    create_response("200","Item Groups fetched successfully",item_groups)