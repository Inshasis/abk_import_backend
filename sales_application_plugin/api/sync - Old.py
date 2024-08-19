import frappe
from datetime import datetime
from sales_application_plugin.api.utils import create_response, get_sales_persons,get_allowed_customer, timeOfZone
from functools import reduce
import json
from frappe.utils import flt, getdate
from frappe.utils import now
from frappe.auth import get_logged_user
from frappe.utils.data import getdate, flt
import base64
from datetime import datetime, timedelta




@frappe.whitelist()
def customer_groups():
    time = frappe.local.form_dict.time

    condition = ("")
    if time is not None and time != "":
         condition += "where modified > %(time)s"

    synced_time = timeOfZone(datetime.now())
        
    groups = frappe.db.sql("""
            SELECT name FROM `tabCustomer Group` {conditions} order by modified desc
        """.format(conditions = condition) , {
            "time" : time
        } ,as_dict = True)
    
    create_response(200, "Customer Group fetched successfully" , {
        "time" : synced_time,
        "data" : groups
    })

@frappe.whitelist()
def get_territories():
    time = frappe.local.form_dict.time

    condition = ("")
    if time is not None and time != "":
         condition += "where modified > %(time)s"
    synced_time = timeOfZone(datetime.now())
    groups = frappe.db.sql("""
            SELECT name FROM `tabTerritory` {conditions} order by modified desc
        """.format(conditions = condition) , {
            "time" : time
        } ,as_dict = True)
    
    create_response(200, "Customer Group fetched successfully" , {
        "time" : synced_time,
        "data" : groups
    })


#Sales Person
@frappe.whitelist()
def get_sales_person():
    time = frappe.local.form_dict.get('time', None)
    condition = ""
    params = {}

    if time:
        condition += "AND modified > %(time)s"
        params["time"] = time

    synced_time = now()  # Assuming this is a function that returns the current time in the desired format

    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee" , {"user_id" : active_user} , "name")
    current_user = frappe.db.get_value("Sales Person" , {"employee" : emp} , "name")

    # Find the sales person linked to the current user via user_id
    sales_person = frappe.db.get_value("Sales Person", {"name": current_user}, "name")

    if not sales_person:
        return {"status": "error", "message": "Sales Person not found for the current user"}

    if not sales_person:
        return {"status": "error", "message": "Sales Person not found for the current user"}
    
    # Function to get all subordinate sales persons
    def get_subordinate_sales_persons(sales_person):
        subordinates = frappe.db.get_all("Sales Person", filters={"parent_sales_person": sales_person}, fields=["name"])
        all_subordinates = [sales_person]
        for subordinate in subordinates:
            all_subordinates.extend(get_subordinate_sales_persons(subordinate['name']))
        return all_subordinates
    # Get all subordinate sales persons including the current sales person
    all_sales_persons = get_subordinate_sales_persons(sales_person)
    # Construct the SQL IN clause with the list of sales persons
    placeholders = ', '.join(['%s'] * len(all_sales_persons))
    condition += "AND name IN ({})".format(placeholders)
    # Execute the query
    sp = frappe.db.sql("""
            SELECT name FROM `tabSales Person` 
            WHERE 1=1 {condition} 
            ORDER BY modified DESC
        """.format(condition=condition), [*all_sales_persons, *params.values()])
    # Construct the response
    response = {
        "time": synced_time,
        "data": [row[0] for row in sp]  # Extracting names from the result rows
    }
    return response

    
# Old Customer API
@frappe.whitelist()
def get_customers():
    time = frappe.local.form_dict.time
    sales_person = frappe.local.form_dict.sales_person

    try:
        sales_persons = get_sales_persons(sales_person=sales_person)
        condition = ("")
        if time is not None and time != "":
            condition += "where cus.modified > %(time)s"

        default_company = frappe.db.get_single_value('Global Defaults','default_company')
        if default_company:
            condition += " and ccl.company = %(company)s"
        
        synced_time = timeOfZone(datetime.now())
        
        customers = frappe.db.sql("""
                SELECT
                cus.name, cus.customer_name,cus.mobile_no, cus.territory, cus.customer_group, ccl.credit_limit as credit , group_concat(st.sales_person) as sales_team
                FROM `tabCustomer` cus 
                INNER JOIN `tabSales Team` st on st.parent = cus.name and st.sales_person in %(sales_persons)s
                LEFT JOIN `tabCustomer Credit Limit` ccl on ccl.parent = cus.name {conditions} group by cus.name, st.sales_person 
            """.format(conditions= condition) , {
                "company" : default_company,
                "time" : time,
                "sales_persons" : sales_persons
            }, as_dict = True)

        create_response(200,"Customers list fetched successfully",{
            "time" : synced_time,
            "data" : customers
        })
    except Exception as ex:
        create_response(422,"Something went wrong!",ex)
        return

# New Customer API
@frappe.whitelist()
def get_customers_paginated():
    time = frappe.local.form_dict.get('time')
    customer_name = frappe.local.form_dict.get('customer_name')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    offset = (page - 1) * page_length

    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
    sales_person = frappe.db.get_value("Sales Person", {"employee": emp}, "name")

    try:
        sales_persons = get_sales_persons_hierarchy(sales_person)
        condition = ""
        parameters = {
            "company": frappe.db.get_single_value('Global Defaults', 'default_company'),
            "sales_persons": sales_persons,
            "offset": offset,
            "page_length": page_length
        }

        if time:
            condition += " AND cus.modified > %(time)s"
            parameters["time"] = time
        if customer_name:
            condition += " AND cus.customer_name LIKE %(customer_name)s"
            parameters["customer_name"] = f"%{customer_name}%"

        synced_time = timeOfZone(datetime.now())

        # Count query
        count_query = f"""
            SELECT
                COUNT(DISTINCT cus.name) AS total_count
            FROM 
                `tabCustomer` cus 
            INNER JOIN 
                `tabSales Team` st ON st.parent = cus.name AND st.sales_person IN %(sales_persons)s
            LEFT JOIN 
                `tabCustomer Credit Limit` ccl ON ccl.parent = cus.name
            WHERE 1=1 {condition}
        """

        # Fetch total count
        total_count = frappe.db.sql(count_query, parameters, as_dict=True)[0]['total_count']

        # Main query
        main_query = f"""
            SELECT
                cus.name, cus.customer_name, cus.mobile_no, cus.territory, cus.customer_group,
                ccl.credit_limit AS credit, GROUP_CONCAT(st.sales_person) AS sales_team
            FROM 
                `tabCustomer` cus 
            INNER JOIN 
                `tabSales Team` st ON st.parent = cus.name AND st.sales_person IN %(sales_persons)s
            LEFT JOIN 
                `tabCustomer Credit Limit` ccl ON ccl.parent = cus.name
            WHERE 1=1 {condition}
            GROUP BY 
                cus.name
            LIMIT 
                %(offset)s, %(page_length)s
        """

        customers = frappe.db.sql(main_query, parameters, as_dict=True)

        create_response(200, "Customers list fetched successfully", {
            "time": synced_time,
            "total_count": total_count,
            "data": customers
        })
    except Exception as ex:
        create_response(422, "Something went wrong!", str(ex))

def get_sales_persons_hierarchy(sales_person):
    sales_persons = [sales_person]

    def get_subordinates(sp):
        subordinates = frappe.db.sql("""
            SELECT name FROM `tabSales Person` WHERE parent_sales_person = %s
        """, sp, as_dict=True)
        return [sub['name'] for sub in subordinates]

    subordinates = get_subordinates(sales_person)
    while subordinates:
        sales_persons.extend(subordinates)
        subordinates = [sub for sp in subordinates for sub in get_subordinates(sp)]

    return tuple(sales_persons)

# @frappe.whitelist()
# def get_customers_paginated():
#     time = frappe.local.form_dict.time
#     sales_person = frappe.local.form_dict.sales_person
#     customer_name = frappe.local.form_dict.customer_name  # New addition for customer name filter
#     page = int(frappe.local.form_dict.get('page', 1))
#     page_length = int(frappe.local.form_dict.get('page_length', 20))
#     offset = (page - 1) * page_length
#     try:
#         sales_persons = get_sales_persons(sales_person=sales_person)
#         condition = ""
#         parameters = {
#             "company": frappe.db.get_single_value('Global Defaults', 'default_company'),
#             "sales_persons": sales_persons,
#             "offset": offset,
#             "page_length": page_length
#         }

#         if time is not None and time != "":
#             condition += " AND cus.modified > %(time)s"
#             parameters["time"] = time
#         if customer_name is not None and customer_name != "":
#             condition += " AND cus.customer_name LIKE %(customer_name)s"
#             parameters["customer_name"] = f"%{customer_name}%"

#         synced_time = timeOfZone(datetime.now())

#         # Count query
#         count_query = """
#             SELECT
#                 COUNT(DISTINCT cus.name) AS total_count
#             FROM 
#                 `tabCustomer` cus 
#             INNER JOIN 
#                 `tabSales Team` st on st.parent = cus.name and st.sales_person in %(sales_persons)s
#             LEFT JOIN 
#                 `tabCustomer Credit Limit` ccl on ccl.parent = cus.name
#             WHERE 1=1 {conditions}
#             """.format(conditions=condition)

#         # Fetch total count
#         total_count = frappe.db.sql(count_query, parameters, as_dict=True)[0]['total_count']

#         # Main query
#         main_query = """
#             SELECT
#                 cus.name, cus.customer_name, cus.mobile_no, cus.territory, cus.customer_group,
#                 ccl.credit_limit as credit, group_concat(st.sales_person) as sales_team
#             FROM 
#                 `tabCustomer` cus 
#             INNER JOIN 
#                 `tabSales Team` st on st.parent = cus.name and st.sales_person in %(sales_persons)s
#             LEFT JOIN 
#                 `tabCustomer Credit Limit` ccl on ccl.parent = cus.name
#             WHERE 1=1 {conditions}
#             GROUP BY 
#                 cus.name, st.sales_person 
#             LIMIT 
#                 %(offset)s, %(page_length)s
#             """.format(conditions=condition)

#         customers = frappe.db.sql(main_query, parameters, as_dict=True)

#         create_response(200, "Customers list fetched successfully", {
#             "time": synced_time,
#             "total_count": total_count,
#             "data": customers
#         })
#     except Exception as ex:
#         create_response(422, "Something went wrong!", ex)
#         return



def get_address_transformer(address_of_customers):
    # Reduces/Transforms the list to desire key-value pair format
    def transform_customer_data(acc, data):
        if data.name not in acc:
            acc[data.name] = {}
            acc[data.name]["name"] = data.name
            acc[data.name]["customer_name"] = data.customer_name
            acc[data.name]["customer_group"] = data.customer_group
            acc[data.name]["credit"] = data.credit

        if "addresses" not in acc[data.name]:
            acc[data.name]["addresses"] = []     
        
        for address in list(filter(lambda x : x.customer == data.name, address_of_customers)):
            if address.address_name is not None:
                acc[data.name]["addresses"].append({
                    'name' : address.address_name,
                    'title': address.title, 
                    'address': address.address, 
                    'type': address.type,
                    'city' : address.city,
                    'state' : address.state,
                    'country' : address.country,
                    'pincode' : address.pincode,
                    'phone' : address.phone,
                    'location' : json.loads(address.location)["features"][0]["geometry"]["coordinates"] if address.location is not None else [],
                    # 'location' :data.location
                })

        return acc
    return transform_customer_data



@frappe.whitelist()
def item_groups():
    time = frappe.local.form_dict.time

    condition = ("")
    if time is not None and time != "":
         condition += "where modified > %(time)s"
    
    synced_time = timeOfZone(datetime.now())
    
    groups = frappe.db.sql("""
            SELECT name FROM `tabItem Group` {conditions}
        """.format(conditions = condition) , {
            "time" : time
        } ,as_dict = True)
    
    create_response(200, "Item Group fetched successfully" , {
        "time" : synced_time,
        "data" : groups
    })


#Item Sync Old Code
@frappe.whitelist()
def get_items():
    time = frappe.local.form_dict.time
    #Get allowed warehouse for user, So user can only see warehouse assigned to him.
    warehouse = frappe.db.get_list('Warehouse', pluck='name')
    condition = ("")
    if time is not None and time != "":
         condition += "where i.modified > %(time)s"
    synced_time = timeOfZone(datetime.now())
    try:
        items = frappe.db.sql("""
            SELECT
            i.item_name,
            i.name,
            i.item_code,
            i.item_group,
            IFNULL(i.custom_mrp,0) as mrp,
            IFNULL(sum(bn.actual_qty), 0) as total_qty
            FROM `tabItem` i left join `tabBin` bn on bn.item_code = i.name {conditions} and warehouse in %(warehouse)s
            group by i.name        
        """.format(conditions = condition), {
            "time" : time,
            "warehouse":warehouse
        },as_dict = True)
        create_response(200,"Item list successfully",{
            "time" : synced_time,
            "data" : items
        })
        return
    except Exception as ex:
        create_response(422,"Something went wrong!",ex)
        return


#Item Sync New Code
@frappe.whitelist()
def get_items_paginated():
    time = frappe.local.form_dict.get('time')
    item_search = frappe.local.form_dict.get('item_search')
    item_group = frappe.local.form_dict.get('item_group')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    in_stock = frappe.local.form_dict.get('in_stock')

    # warehouse
    warehouse = frappe.db.get_list('Warehouse', pluck='name')

    condition = ""
    parameters = {"warehouse": warehouse}
    
    if time:
        condition += " AND i.modified > %(time)s"
        parameters["time"] = time

    if item_search:
        condition += " AND (i.item_code LIKE %(item_search)s OR i.item_name LIKE %(item_search)s)"
        parameters["item_search"] = f"%{item_search}%"

    if item_group:
        condition += " AND i.item_group LIKE %(item_group)s"
        parameters["item_group"] = f"%{item_group}%"
        
    try:
        if in_stock:
            in_stock = int(in_stock)
            condition += " AND bn.actual_qty >= %(in_stock)s"
            parameters["in_stock"] = in_stock

        # query to get paginated items
        items = frappe.db.sql("""
            SELECT
                i.item_name,
                i.name,
                i.item_code,
                i.item_group,
                IFNULL(i.custom_mrp,0) as mrp,
                IFNULL(sum(bn.actual_qty), 0) as total_qty
            FROM 
                `tabItem` i
            LEFT JOIN 
                (SELECT item_code, SUM(actual_qty) as actual_qty
                FROM `tabBin`
                WHERE warehouse IN %(warehouse)s
                GROUP BY item_code) bn ON bn.item_code = i.name
            WHERE 
                1=1 {condition}
            GROUP BY 
                i.name
            LIMIT 
                %(start)s, %(page_length)s
        """.format(condition=condition), {
            **parameters,
            "start": (page - 1) * page_length,
            "page_length": page_length
        }, as_dict=True)

        # query to get total count
        total_count = frappe.db.sql("""
            SELECT
                COUNT(*) as count
            FROM 
                `tabItem` i
            LEFT JOIN 
                (SELECT item_code, SUM(actual_qty) as actual_qty
                FROM `tabBin`
                WHERE warehouse IN %(warehouse)s
                GROUP BY item_code) bn ON bn.item_code = i.name
            WHERE 
                1=1 {condition}
        """.format(condition=condition), parameters, as_dict=True)
        
        synced_time = timeOfZone(datetime.now())
        
        create_response(200, "Item list successfully", {
            "time": synced_time,
            "total_count": total_count[0]['count'] if total_count else 0,
            "data": items
        })
        return
    except Exception as ex:
        create_response(422, "Something went wrong!", str(ex))
        return

        


@frappe.whitelist()
def sales_order_report():
    time = frappe.local.form_dict.time
    cancelled = frappe.local.form_dict.cancelled or 1
    
    customers = get_allowed_customer(frappe.session.user)

    condition = ("")
    if time is not None and time != "":
         condition += "and modified > %(time)s"

    synced_time = timeOfZone(datetime.now())

    sales_order_data =  frappe.db.sql("""
		select name, customer_name, customer, transaction_date, delivery_date, company, grand_total, status, delivery_status, per_delivered, per_billed, billing_status, currency, base_grand_total, order_type
		from `tabSales Order`
		where docstatus = %(docstatus)s and customer in %(customers)s {conditions} order by transaction_date desc, name desc""".format(conditions = condition) , {
            "time" : time,
            "customers" : customers,
            "docstatus": cancelled
        } , as_dict=1)
    
    create_response(200 , "Sales Report fetched succcessfully", {
        "time" : synced_time,
        "data" : sales_order_data,
    })

#New Gereral Ledger
@frappe.whitelist()
def general_ledger_is_system_generated():
    time = frappe.local.form_dict.get('time')
    cancelled = frappe.local.form_dict.get('cancelled', 0)
    customers = frappe.local.form_dict.get('customer')
   
    if customers is None:
        return create_response(400, "No customers provided")

    if not isinstance(customers, list):
        customers = [customers]

    voucher_types = ["Sales Invoice", "Journal Entry", "Payment Entry"]
    
    condition = ""
    params = {
        "customers": customers,
        "cancelled": cancelled,
        "voucher_type": voucher_types
    }

    if time:
        condition += " AND gl.modified > %(time)s"
        params["time"] = time

    synced_time = timeOfZone(datetime.now())
    
    try:
        gl_data = frappe.db.sql("""
            SELECT gl.name, gl.posting_date, gl.due_date, gl.transaction_date, gl.party, gl.debit, gl.credit, gl.voucher_no, gl.voucher_type, gl.against_voucher_type, gl.against_voucher
            FROM `tabGL Entry` gl
            LEFT JOIN `tabJournal Entry` je ON gl.voucher_no = je.name
            WHERE (je.is_opening IS NULL OR je.is_system_generated = 0)
                AND gl.is_cancelled = %(cancelled)s 
                AND gl.party_type = "Customer" 
                AND gl.party IN %(customers)s 
                AND gl.voucher_type IN %(voucher_type)s
                {conditions} 
            ORDER BY gl.modified DESC""".format(conditions=condition), params, as_dict=1)
         
        return create_response(200, "GL fetched successfully", {
            "time": synced_time,
            "data": gl_data,
        })
    except Exception as e:
        return create_response(500, f"An error occurred: {str(e)}")
    
# Old Gereral Ledger
@frappe.whitelist()
def general_ledger():
    time = frappe.local.form_dict.time
    cancelled = frappe.local.form_dict.cancelled or 0
    customers = get_allowed_customer(frappe.session.user)

    voucher_types = ["Sales Invoice" , "Journal Entry" , "Payment Entry"]
    
    condition = ("")
    if time is not None and time != "":
         condition += "and gl.modified > %(time)s"

    synced_time = timeOfZone(datetime.now())
    
    gl_data  = frappe.db.sql("""
		select gl.name, gl.posting_date, gl.due_date, gl.transaction_date, gl.party, gl.debit, gl.credit, gl.voucher_no, gl.voucher_type,gl.against_voucher_type,gl.against_voucher
		from `tabGL Entry` gl where gl.is_cancelled = %(cancelled)s and gl.party_type = "Customer" and gl.party in %(customers)s and gl.voucher_type in %(voucher_type)s {conditions} order by gl.modified desc""".format(conditions = condition) , {
            "time" : time,
            "customers" : customers,
            "cancelled":cancelled,
            "voucher_type" : voucher_types
        } , as_dict=1)
         
    create_response(200 , "GL fetched succcessfully", {
        "time" : synced_time,
        "data" : gl_data,
    })



@frappe.whitelist()
def deleted_doc():
    time = frappe.local.form_dict.time

    condition = ("")
    deleted_doc_ref_condition = ("")
    if time is not None and time != "":
        condition += "and modified > %(time)s"
        deleted_doc_ref_condition += "and modified > %(time)s"


    deleted_data  = frappe.db.sql("""
		select deleted_name, deleted_doctype
		from `tabDeleted Document` where restored != 1 and deleted_doctype in ("Item", "Customer", "Customer Group", "Item Group") {conditions}""".format(conditions = condition) , {
            "time" : time
    } , as_dict=1)

    deleted_doc_references = frappe.db.sql("""
        select doc_type as deleted_doctype, doc_name as deleted_name from `tabDeleted Doc Reference` where doc_type in ("Item", "Customer", "Customer Group", "Item Group") {conditions}
    """.format(conditions = deleted_doc_ref_condition), {
        "time" : time
    } , as_dict = 1)

    data = deleted_data + deleted_doc_references   

    data = list(map(dict, set(tuple(sorted(d.items())) for d in data)))

    create_response(200 , "Deleted documents fetched successfully", {
        "time" : datetime.now(),
        "data" : data
    })       

@frappe.whitelist()
def common_data():
    meta_sales_order = frappe.get_meta('Sales Order')

    if meta_sales_order.has_field("naming_series"):
        series = meta_sales_order.get_field("naming_series").options.strip().replace("\n",",")
    else:
        series = ""

    if meta_sales_order.has_field("custom_series_name"):
        naming_series = meta_sales_order.get_field("custom_series_name").options.strip().replace("\n",",")
    else:
        naming_series = ""

    if meta_sales_order.has_field("status"):
        status = meta_sales_order.get_field("status").options.strip().replace("\n",",")
    else:
        status = ""    

    create_response(200, "Common Data fetched successfully" , {
        "series" : series,
        "naming_series" : naming_series,
        "status" : status
    })


#Sales Summary
@frappe.whitelist()
def get_sales_summary(customer=None, from_date=None, to_date=None):
    conditions_si = ""
    conditions_so = ""
    conditions_gle = ""
    values = {}

    if customer:
        conditions_si += " AND si.customer = %(customer)s"
        conditions_so += " AND so.customer = %(customer)s"
        conditions_gle += " AND gle.party = %(customer)s"
        values["customer"] = customer

    if from_date:
        conditions_si += " AND si.posting_date >= %(from_date)s"
        conditions_so += " AND so.transaction_date >= %(from_date)s"
        conditions_gle += " AND gle.posting_date >= %(from_date)s"
        values["from_date"] = getdate(from_date)

    if to_date:
        conditions_si += " AND si.posting_date <= %(to_date)s"
        conditions_so += " AND so.transaction_date <= %(to_date)s"
        conditions_gle += " AND gle.posting_date <= %(to_date)s"
        values["to_date"] = getdate(to_date)

    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
    current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")

    def get_salespersons(salesperson):
        salespersons = [salesperson]
        subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
        for subordinate in subordinates:
            salespersons.extend(get_salespersons(subordinate))
        return salespersons

    current_salesperson = frappe.db.get_value('Sales Person', {'name': current_user}, 'name')
    if current_salesperson:
        salespersons = get_salespersons(current_salesperson)
        conditions_si += " AND si_child.sales_person IN %(salespersons)s"
        conditions_so += " AND so_child.sales_person IN %(salespersons)s"
        conditions_gle += " AND si_child.sales_person IN %(salespersons)s"
        values["salespersons"] = salespersons
    else:
        create_response(200, "Sales Summary fetched successfully", {
            "sales_gross": 0.00,
            "sales_credit": 0.00,
            "receipts": 0.00,
            "outstanding": 0.00,
            "sales_order": 0.00
        })
        return

    sales_gross = frappe.db.sql(f"""
        SELECT SUM(si.grand_total)
        FROM `tabSales Invoice` si
        JOIN `tabSales Team` si_child ON si_child.parent = si.name
        WHERE si.docstatus = 1 {conditions_si}
    """, values)[0][0] or 0

    sales_credit = frappe.db.sql(f"""
        SELECT SUM(si.grand_total)
        FROM `tabSales Invoice` si
        JOIN `tabSales Team` si_child ON si_child.parent = si.name
        WHERE si.docstatus = 1 AND si.is_return = 1 {conditions_si}
    """, values)[0][0] or 0

    receipts = frappe.db.sql(f"""
                SELECT SUM(gle.credit)
        FROM `tabGL Entry` gle
        JOIN `tabSales Invoice` si ON si.name = gle.voucher_no
        JOIN `tabSales Team` si_child ON si_child.parent = si.name
        WHERE gle.voucher_type IN ('Payment Entry', 'Journal Entry') AND gle.docstatus = 1 
        {conditions_gle}
    """, values)[0][0] or 0

    outstanding = frappe.db.sql(f"""
        SELECT SUM(si.outstanding_amount)
        FROM `tabSales Invoice` si
        JOIN `tabSales Team` si_child ON si_child.parent = si.name
        WHERE si.docstatus = 1 {conditions_si}
    """, values)[0][0] or 0

    sales_order = frappe.db.sql(f"""
        SELECT SUM(so.rounded_total)
        FROM `tabSales Order` so
        JOIN `tabSales Team` so_child ON so_child.parent = so.name
        WHERE so.docstatus = 1 {conditions_so}
    """, values)[0][0] or 0

    create_response(200, "Sales Summary fetched successfully", {
        "sales_gross": flt(sales_gross),
        "sales_credit": flt(sales_credit),
        "receipts": flt(receipts),
        "outstanding": flt(outstanding),
        "sales_order": flt(sales_order)
    })
# @frappe.whitelist()
# def get_sales_summary(customer=None, from_date=None, to_date=None):
#     conditions = ""
#     values = {}

#     if customer:
#         conditions += " AND si.customer = %(customer)s"
#         values["customer"] = customer

#     if from_date:
#         conditions += " AND si.posting_date >= %(from_date)s"
#         values["from_date"] = getdate(from_date)

#     if to_date:
#         conditions += " AND si.posting_date <= %(to_date)s"
#         values["to_date"] = getdate(to_date)

#     # current_user = "Hidayta"
#     active_user = frappe.session.user
#     emp = frappe.db.get_value("Employee" , {"user_id" : active_user} , "name")
#     current_user = frappe.db.get_value("Sales Person" , {"employee" : emp} , "name")

#     # Function to get salesperson and subordinates
#     def get_salespersons(salesperson):
#         salespersons = [salesperson]
#         subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
#         for subordinate in subordinates:
#             salespersons.extend(get_salespersons(subordinate))
#         return salespersons

#     # Get salesperson linked to the current user
#     current_salesperson = frappe.db.get_value('Sales Person', {'name': current_user}, 'name')
#     if current_salesperson:
#         salespersons = get_salespersons(current_salesperson)
#         conditions += " AND si_child.sales_person IN %(salespersons)s"
#         values["salespersons"] = salespersons
#     else:
#         # If the current user is not linked to any salesperson, return an empty response
#         create_response(200, "Sales Summary fetched successfully", {
#             "sales_gross": 0.00,
#             "sales_credit": 0.00,
#             "receipts": 0.00,
#             "outstanding": 0.00,
#             "sales_order": 0.00
#         })
#         return

#     sales_gross = frappe.db.sql("""
#         SELECT SUM(si.grand_total)
#         FROM `tabSales Invoice` si
#         JOIN `tabSales Team` si_child ON si_child.parent = si.name
#         WHERE si.docstatus = 1 {conditions}
#     """.format(conditions=conditions), values)[0][0] or 0

#     sales_credit = frappe.db.sql("""
#         SELECT SUM(si.grand_total)
#         FROM `tabSales Invoice` si
#         JOIN `tabSales Team` si_child ON si_child.parent = si.name
#         WHERE si.docstatus = 1 AND si.is_return = 1 {conditions}
#     """.format(conditions=conditions), values)[0][0] or 0

#     receipts = frappe.db.sql("""
#         SELECT SUM(gle.credit)
#         FROM `tabGL Entry` gle
#         JOIN `tabSales Invoice` si ON si.name = gle.voucher_no
#         JOIN `tabSales Team` si_child ON si_child.parent = si.name
#         WHERE gle.voucher_type IN ('Payment Entry', 'Journal Entry') AND gle.docstatus = 1 {conditions}
#     """.format(conditions=conditions.replace("si.customer = %(customer)s", "gle.party = %(customer)s")), values)[0][0] or 0

#     outstanding = frappe.db.sql("""
#         SELECT SUM(si.outstanding_amount)
#         FROM `tabSales Invoice` si
#         JOIN `tabSales Team` si_child ON si_child.parent = si.name
#         WHERE si.docstatus = 1 {conditions}
#     """.format(conditions=conditions), values)[0][0] or 0

#     create_response(200, "Sales Summary fetched successfully", {
#         "sales_gross": flt(sales_gross),
#         "sales_credit": flt(sales_credit),
#         "receipts": flt(receipts),
#         "outstanding": flt(outstanding),
#         "sales_order": 0.00
#     })

#Customer Wise Sales Gross Summary
@frappe.whitelist()
def get_sales_gross_with_customers_paginated():
    
    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee" , {"user_id" : active_user} , "name")
    session_user = frappe.db.get_value("Sales Person" , {"employee" : emp} , "name")

    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
        
    conditions = []
    values = {}

    if from_date:
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if session_user:
        conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
        values["session_user"] = session_user

    # Constructing the WHERE clause for SQL query
    where_clause = " AND ".join(conditions)

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get customer-wise total sales
    sql_query = """
        SELECT si.customer, SUM(si.grand_total) AS total_amount
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st ON si.name = st.parent
        LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
        WHERE si.docstatus = 1 AND {where_clause}
        GROUP BY si.customer
    """.format(where_clause=where_clause)

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY total_amount DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY total_amount ASC"
    elif sort_by == 'name_a_z':
        sql_query += " ORDER BY customer ASC"
    elif sort_by == 'name_z_a':
        sql_query += " ORDER BY customer DESC"

    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    try:
        # Executing the SQL query to get customer-wise total sales
        customer_sales_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Constructing the SQL query to fetch total amount
        total_sql_query = """
            SELECT SUM(si.grand_total) AS total_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE si.docstatus = 1 AND {where_clause}
        """.format(where_clause=where_clause)

        # Executing the SQL query to fetch total amount
        total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
        total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

        # Generate a list of months within the specified date range
        start_date = datetime.strptime(from_date, "%Y-%m-%d").replace(day=1)
        end_date = datetime.strptime(to_date, "%Y-%m-%d").replace(day=1)
        months_list = [start_date + timedelta(days=31*i) for i in range((end_date - start_date).days // 31 + 2)]

        # Executing the SQL query to fetch month-wise sales sums
        month_wise_data = []
        for month in months_list:
            month_data = frappe.db.sql("""
                SELECT  
                    DATE_FORMAT(%(month)s, '%%Y-%%b') AS month_year, 
                    COALESCE(SUM(si.grand_total), 0) AS total_amount
                FROM
                    `tabSales Invoice` si
                LEFT JOIN 
                    `tabSales Team` st ON si.name = st.parent
                LEFT JOIN 
                    `tabSales Person` sp ON st.sales_person = sp.name
                WHERE 
                    si.docstatus = 1 AND DATE_FORMAT(si.posting_date, '%%Y-%%m') = DATE_FORMAT(%(month)s, '%%Y-%%m') AND {where_clause}
            """.format(where_clause=where_clause), {"month": month.strftime("%Y-%m-%d"), **values}, as_dict=True)
            month_wise_data.append(month_data[0] if month_data else {"month_year": month.strftime("%Y-%b"), "total_amount": 0})

        # Creating a response
        synced_time = timeOfZone(datetime.now())         
        create_response(200, "Customer Sales Gross Data fetched successfully", {
            "time": synced_time,
            "grand_total": total_amount,
            "month_wise_total": month_wise_data,
            "data": customer_sales_data
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Sales Gross  Data Fetching Failed")
        create_response(500, "An error occurred while fetching Customer Sales Gross  Data. Please try again later.", str(e))


#Customer Wise Sales Invoice Summary
@frappe.whitelist()
def get_sales_invoce_with_customers_paginated():
    
    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee" , {"user_id" : active_user} , "name")
    session_user = frappe.db.get_value("Sales Person" , {"employee" : emp} , "name")

    customer = frappe.local.form_dict.get('customer')
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
        
    conditions = []
    values = {}

    if from_date:
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if customer:
        conditions.append("si.customer = %(customer)s")
        values["customer"] = customer

    if session_user:
        conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
        values["session_user"] = session_user

    # Constructing the WHERE clause for SQL query
    where_clause = " AND ".join(conditions)

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get sales invoice data
    sql_query = """
        SELECT si.name, si.posting_date, si.customer, si.grand_total
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st ON si.name = st.parent
        LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
        WHERE si.docstatus = 1 AND {where_clause}
    """.format(where_clause=where_clause)

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY grand_total DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY grand_total ASC"
    elif sort_by == "date_recent":
        sql_query += " ORDER BY posting_date DESC"
    elif sort_by == "date_oldest":
        sql_query += " ORDER BY posting_date ASC"

    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    try:
        # Executing the SQL query to get sales invoice data
        sales_invoice_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Constructing the SQL query to fetch total amount
        total_sql_query = """
            SELECT SUM(si.grand_total) AS total_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE si.docstatus = 1 AND {where_clause}
        """.format(where_clause=where_clause)

        # Executing the SQL query to fetch total amount
        total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
        total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

        # Generate a list of months within the specified date range
        start_date = datetime.strptime(from_date, "%Y-%m-%d").replace(day=1)
        end_date = datetime.strptime(to_date, "%Y-%m-%d").replace(day=1)
        months_list = [start_date + timedelta(days=31*i) for i in range((end_date - start_date).days // 31 + 2)]

        # Executing the SQL query to fetch month-wise sales sums
        month_wise_data = []
        for month in months_list:
            month_data = frappe.db.sql("""
                SELECT  
                    DATE_FORMAT(%(month)s, '%%Y-%%b') AS month_year, 
                    COALESCE(SUM(si.grand_total), 0) AS total_amount
                FROM
                    `tabSales Invoice` si
                LEFT JOIN 
                    `tabSales Team` st ON si.name = st.parent
                LEFT JOIN 
                    `tabSales Person` sp ON st.sales_person = sp.name
                WHERE 
                    si.docstatus = 1 AND DATE_FORMAT(si.posting_date, '%%Y-%%m') = DATE_FORMAT(%(month)s, '%%Y-%%m') AND {where_clause}
            """.format(where_clause=where_clause), {"month": month.strftime("%Y-%m-%d"), **values}, as_dict=True)
            month_wise_data.append(month_data[0] if month_data else {"month_year": month.strftime("%Y-%b"), "total_amount": 0})

        # Creating a response
        synced_time = timeOfZone(datetime.now())         
        create_response(200, "Sales Invoice Data fetched successfully", {
            "time": synced_time,
            "grand_total": total_amount,
            "month_wise_total": month_wise_data,
            "data": sales_invoice_data
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Invoice Data Fetching Failed")
        create_response(500, "An error occurred while fetching Sales Invoice data. Please try again later.", str(e))


#Party Details
@frappe.whitelist()
def get_party_details():
    
    customer = frappe.local.form_dict.get('customer_name')
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')

    conditions = ""
    values = {}

    if from_date:
        conditions += " AND posting_date >= %(from_date)s"
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions += " AND posting_date <= %(to_date)s"
        values["to_date"] = frappe.utils.data.getdate(to_date)

    if customer:
        conditions += " AND customer = %(customer)s"
        values["customer"] = customer

    # Total amount query
    total_sql_query = """
        SELECT SUM(rounded_total) AS total_amount
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND status != "Return" {conditions}
    """.format(conditions=conditions)

    total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
    total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

    # Total count query
    count_sql_query = """
        SELECT COUNT(*) AS total_count
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND status != "Return" {conditions}
    """.format(conditions=conditions)

    total_count_data = frappe.db.sql(count_sql_query, values, as_dict=True)
    total_count = total_count_data[0]["total_count"] if total_count_data else 0

    # Calculate the average sales amount
    average_sales_amount = total_amount / total_count if total_count > 0 else 0

    # Month-wise sales totals query
    month_wise_query = """
        SELECT  
            DATE_FORMAT(months.month_date, '%%Y-%%b') AS month_year, 
            COALESCE(SUM(si.rounded_total), 0) AS total_amount
        FROM
            (
                SELECT 
                    DATE_ADD(DATE_FORMAT(%(from_date)s, '%%Y-%%m-01'), INTERVAL n MONTH) AS month_date
                FROM 
                    (
                        SELECT 
                            a.N + b.N * 10 AS n
                        FROM
                            (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) AS a
                            CROSS JOIN (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) AS b
                    ) AS numbers
                WHERE 
                    DATE_ADD(DATE_FORMAT(%(from_date)s, '%%Y-%%m-01'), INTERVAL n MONTH) <= DATE_FORMAT(%(to_date)s, '%%Y-%%m-01')
            ) AS months
            LEFT JOIN `tabSales Invoice` AS si 
                ON DATE_FORMAT(si.posting_date, '%%Y-%%m') = DATE_FORMAT(months.month_date, '%%Y-%%m')
                    AND si.docstatus = 1 AND si.status != "Return" {conditions}
        GROUP BY
            months.month_date
    """.format(conditions=conditions)

    month_wise_data = frappe.db.sql(month_wise_query, values, as_dict=True)

    # Month-wise return sales totals query
    month_wise_return_query = """
        SELECT  
            DATE_FORMAT(months.month_date, '%%Y-%%b') AS month_year, 
            COALESCE(SUM(si.rounded_total), 0) AS total_amount
        FROM
            (
                SELECT 
                    DATE_ADD(DATE_FORMAT(%(from_date)s, '%%Y-%%m-01'), INTERVAL n MONTH) AS month_date
                FROM 
                    (
                        SELECT 
                            a.N + b.N * 10 AS n
                        FROM
                            (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) AS a
                            CROSS JOIN (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) AS b
                    ) AS numbers
                WHERE 
                    DATE_ADD(DATE_FORMAT(%(from_date)s, '%%Y-%%m-01'), INTERVAL n MONTH) <= DATE_FORMAT(%(to_date)s, '%%Y-%%m-01')
            ) AS months
            LEFT JOIN `tabSales Invoice` AS si 
                ON DATE_FORMAT(si.posting_date, '%%Y-%%m') = DATE_FORMAT(months.month_date, '%%Y-%%m')
                    AND si.docstatus = 1 AND si.status = "Return" {conditions}
        GROUP BY
            months.month_date
    """.format(conditions=conditions)

    month_wise_return_data = frappe.db.sql(month_wise_return_query, values, as_dict=True)

    # Last sales date query
    last_sales_date_query = """
        SELECT MAX(posting_date) AS last_sales_date
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND status != "Return" {conditions}
    """.format(conditions=conditions)

    last_sales_date_data = frappe.db.sql(last_sales_date_query, values, as_dict=True)
    last_sales_date = last_sales_date_data[0]["last_sales_date"] if last_sales_date_data else None

    # Month-wise outstanding invoice totals query with aging buckets
    month_wise_outstanding_query = """
        SELECT  
            CASE
                WHEN DATEDIFF(CURDATE(), si.posting_date) BETWEEN 0 AND 29 THEN '0-29 days'
                WHEN DATEDIFF(CURDATE(), si.posting_date) BETWEEN 30 AND 59 THEN '30-59 days'
                WHEN DATEDIFF(CURDATE(), si.posting_date) BETWEEN 60 AND 89 THEN '60-89 days'
                WHEN DATEDIFF(CURDATE(), si.posting_date) BETWEEN 90 AND 119 THEN '90-119 days'
                ELSE '120+ days'
            END AS aging_bucket,
            COALESCE(SUM(si.outstanding_amount), 0) AS total_amount
        FROM `tabSales Invoice` AS si
        WHERE si.docstatus = 1 AND si.status != "Return" {conditions}
        GROUP BY aging_bucket
    """.format(conditions=conditions)

    month_wise_outstanding_data = frappe.db.sql(month_wise_outstanding_query, values, as_dict=True)

    # Process outstanding data into aging buckets
    outstanding_data = {
        "0-29 days": 0,
        "30-59 days": 0,
        "60-89 days": 0,
        "90-119 days": 0,
        "120+ days": 0
    }


    month_wise_receipt_query = """
        SELECT  
            DATE_FORMAT(months.month_date, '%%Y-%%b') AS month_year, 
            COALESCE(SUM(si.rounded_total), 0) AS total_amount
        FROM
            (
                SELECT 
                    DATE_ADD(DATE_FORMAT(%(from_date)s, '%%Y-%%m-01'), INTERVAL n MONTH) AS month_date
                FROM 
                    (
                        SELECT 
                            a.N + b.N * 10 AS n
                        FROM
                            (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) AS a
                            CROSS JOIN (SELECT 0 AS N UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) AS b
                    ) AS numbers
                WHERE 
                    DATE_ADD(DATE_FORMAT(%(from_date)s, '%%Y-%%m-01'), INTERVAL n MONTH) <= DATE_FORMAT(%(to_date)s, '%%Y-%%m-01')
            ) AS months
            LEFT JOIN `tabDelivery Note` AS si 
                ON DATE_FORMAT(si.posting_date, '%%Y-%%m') = DATE_FORMAT(months.month_date, '%%Y-%%m')
                AND si.docstatus = 1 AND si.status = 'To Bill' {conditions}
        GROUP BY
            months.month_date
    """.format(conditions=conditions)

    month_wise_receipt_data = frappe.db.sql(month_wise_receipt_query, values, as_dict=True)


    # Combine month-wise sales, return, receipt and outstanding data
    sales_data = {"month_wise_data": [], "total_amount": 0}
    sales_credit_data = {"month_wise_data": [], "total_amount": 0}
    # outstanding_data = {"month_wise_data": [], "total_amount": 0}
    receipt_data = {"month_wise_data": [], "total_amount": 0}

    for item in month_wise_data:
        sales_data["month_wise_data"].append({
            "month_year": item['month_year'],
            "amount": item['total_amount']
        })
        sales_data["total_amount"] += item['total_amount']

    for item in month_wise_return_data:
        sales_credit_data["month_wise_data"].append({
            "month_year": item['month_year'],
            "amount": item['total_amount']
        })
        sales_credit_data["total_amount"] += item['total_amount']

    for item in month_wise_outstanding_data:
        aging_bucket = item['aging_bucket']
        outstanding_data[aging_bucket] = item['total_amount']
    
    for item in month_wise_receipt_data:
        receipt_data["month_wise_data"].append({
            "month_year": item['month_year'],
            "amount": item['total_amount']
        })
        receipt_data["total_amount"] += item['total_amount']


    # Pending orders query
    pending_orders_query = """
        SELECT SUM(rounded_total) AS total_pending_amount
        FROM `tabSales Order`
        WHERE customer = %(customer)s 
            AND (status = "To Bill" OR status = "To Deliver and Bill")
    """
    pending_orders_data = frappe.db.sql(pending_orders_query, values, as_dict=True)
    pending_orders_amount = pending_orders_data[0]["total_pending_amount"] if pending_orders_data else 0


    # Create response
    synced_time = datetime.now().isoformat()
    create_response(200, "Party Details Data fetched successfully", {
    "time": synced_time,
    "last_sales_date": last_sales_date,
    "no_of_sales_invoice": total_count,
    "last_receipt_date": last_sales_date,  # Assuming the same as last sales date
    "average_sales_invoice_amount": average_sales_amount,
    "sales_data": sales_data,
    "sales_credit_data": sales_credit_data,
    "outstanding_data": outstanding_data,
    "receipt_data": receipt_data,
    "pending_orders_amount": pending_orders_amount
})

#Customer Wise Outstanding 
@frappe.whitelist()
def get_outstanding_with_customers_paginated():
    
    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
    session_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")

    # from_date = frappe.local.form_dict.get('from_date')
    # to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
        
    conditions = []
    values = {}

    # if from_date:
    #     conditions.append("si.posting_date >= %(from_date)s")
    #     values["from_date"] = frappe.utils.data.getdate(from_date)

    # if to_date:
    #     conditions.append("si.posting_date <= %(to_date)s")
    #     values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if session_user:
        conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
        values["session_user"] = session_user

    # Constructing the WHERE clause for SQL query
    where_clause = " AND ".join(conditions)

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get customer-wise total outstanding amount
    sql_query = """
        SELECT si.customer, SUM(si.outstanding_amount) AS total_amount
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st ON si.name = st.parent
        LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
        WHERE si.docstatus = 1 {where_clause}
        GROUP BY si.customer
        LIMIT %(page_length)s OFFSET %(offset)s
    """.format(where_clause=f" AND {where_clause}" if where_clause else "")

    values["page_length"] = page_length
    values["offset"] = offset

    try:
        # Executing the SQL query to get customer-wise total outstanding amount
        customer_sales_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Constructing the SQL query to fetch total outstanding amount
        total_sql_query = """
            SELECT SUM(si.outstanding_amount) AS total_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE si.docstatus = 1 {where_clause}
        """.format(where_clause=f" AND {where_clause}" if where_clause else "")

        # Executing the SQL query to fetch total outstanding amount
        grand_total_data= frappe.db.sql(total_sql_query, values, as_dict=True)
        grand_total = grand_total_data[0]["total_amount"] if grand_total_data else 0

        # Define the aging buckets
        aging_buckets = [
            {"label": "0-29 days", "condition": "DATEDIFF(CURDATE(), si.posting_date) BETWEEN 0 AND 29"},
            {"label": "30-59 days", "condition": "DATEDIFF(CURDATE(), si.posting_date) BETWEEN 30 AND 59"},
            {"label": "60-89 days", "condition": "DATEDIFF(CURDATE(), si.posting_date) BETWEEN 60 AND 89"},
            {"label": "90-119 days", "condition": "DATEDIFF(CURDATE(), si.posting_date) BETWEEN 90 AND 119"},
            {"label": "120+ days", "condition": "DATEDIFF(CURDATE(), si.posting_date) >= 120"}
        ]

        # Fetch the data for each aging bucket
        outstanding_data = {}
        for bucket in aging_buckets:
            aging_query = """
                SELECT SUM(si.outstanding_amount) AS total_amount
                FROM `tabSales Invoice` si
                LEFT JOIN `tabSales Team` st ON si.name = st.parent
                LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
                WHERE si.docstatus = 1 {where_clause} AND {aging_condition}
            """.format(where_clause=f" AND {where_clause}" if where_clause else "", aging_condition=bucket["condition"])

            bucket_data = frappe.db.sql(aging_query, values, as_dict=True)
            total_amount = bucket_data[0]["total_amount"] if bucket_data and bucket_data[0]["total_amount"] is not None else 0
            outstanding_data[bucket["label"]] = total_amount

        # Creating a response
        synced_time = timeOfZone(datetime.now())
        create_response(200, "Customer Outstanding Data fetched successfully", {
            "time": synced_time,
            "grand_total": grand_total,
            "outstanding_data": outstanding_data,
            "data": customer_sales_data if customer_sales_data else []
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Outstanding Data Fetching Failed")
        create_response(500, "An error occurred while fetching Customer Outstanding Data. Please try again later.", str(e))

#Customer Wise Sales Invoice Outstanding Summary
@frappe.whitelist()
def get_sales_invoice_outstanding_with_customers_paginated():
    try:
        # Get the current logged-in user
        active_user = frappe.session.user
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        session_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")

        # Extract parameters from request
        customer = frappe.local.form_dict.get('customer')
        from_date = frappe.local.form_dict.get('from_date')
        to_date = frappe.local.form_dict.get('to_date')
        page = int(frappe.local.form_dict.get('page', 1))
        page_length = int(frappe.local.form_dict.get('page_length', 20))
        sort_by = frappe.local.form_dict.get('sort_by', '')

        # Initialize conditions and values for SQL query
        conditions = ["si.docstatus = 1", "si.outstanding_amount != 0"]
        values = {}

        if from_date:
            conditions.append("si.posting_date >= %(from_date)s")
            values["from_date"] = frappe.utils.data.getdate(from_date)

        if to_date:
            conditions.append("si.posting_date <= %(to_date)s")
            values["to_date"] = frappe.utils.data.getdate(to_date)

        if customer:
            conditions.append("si.customer = %(customer)s")
            values["customer"] = customer

        if session_user:
            conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
            values["session_user"] = session_user

        # Construct the WHERE clause for SQL query
        where_clause = " AND ".join(conditions)

        # Calculate offset for pagination
        offset = (page - 1) * page_length

        # Construct the main SQL query to get sales invoice data
        sql_query = f"""
            SELECT si.name, si.posting_date, si.customer, si.outstanding_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE {where_clause}
        """

        # Add sorting to the SQL query
        if sort_by == 'amount_high_low':
            sql_query += " ORDER BY si.outstanding_amount DESC"
        elif sort_by == 'amount_low_high':
            sql_query += " ORDER BY si.outstanding_amount ASC"
        elif sort_by == "date_recent":
            sql_query += " ORDER BY si.posting_date DESC"
        elif sort_by == "date_oldest":
            sql_query += " ORDER BY si.posting_date ASC"

        # Add pagination to the SQL query
        sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

        values["page_length"] = page_length
        values["offset"] = offset

        # Execute the main SQL query to get sales invoice data
        sales_invoice_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Construct the SQL query to fetch total outstanding amount
        total_sql_query = f"""
            SELECT SUM(si.outstanding_amount) AS total_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE {where_clause}
        """

        # Execute the SQL query to fetch total outstanding amount
        total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
        total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

        # Generate a list of months within the specified date range
        start_date = datetime.strptime(from_date, "%Y-%m-%d").replace(day=1)
        end_date = datetime.strptime(to_date, "%Y-%m-%d").replace(day=1)
        months_list = [start_date + timedelta(days=31 * i) for i in range((end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1)]

        # Fetch month-wise outstanding amounts
        month_wise_data = []
        for month in months_list:
            month_data = frappe.db.sql(f"""
                SELECT
                    DATE_FORMAT(%(month)s, '%%Y-%%b') AS month_year,
                    COALESCE(SUM(si.outstanding_amount), 0) AS total_amount
                FROM `tabSales Invoice` si
                LEFT JOIN `tabSales Team` st ON si.name = st.parent
                LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
                WHERE si.docstatus = 1 AND si.outstanding_amount != 0 AND DATE_FORMAT(si.posting_date, '%%Y-%%m') = DATE_FORMAT(%(month)s, '%%Y-%%m') AND {where_clause}
            """, {"month": month.strftime("%Y-%m-%d"), **values}, as_dict=True)
            month_wise_data.append(month_data[0] if month_data else {"month_year": month.strftime("%Y-%b"), "total_amount": 0})

        # Creating the response
        synced_time = timeOfZone(datetime.now())
        create_response(200, "Sales Invoice Outstanding Data fetched successfully", {
            "time": synced_time,
            "grand_total": total_amount,
            "month_wise_total": month_wise_data,
            "data": sales_invoice_data
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Invoice Outstanding Data Fetching Failed")
        create_response(500, "An error occurred while fetching Sales Invoice Outstanding data. Please try again later.", str(e))


@frappe.whitelist()
def share_outstanding_with_customers_paginated():
    try:
        # Get the current logged-in user
        active_user = frappe.session.user
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        session_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")

        # Extract parameters from request
        customer = frappe.local.form_dict.get('customer')
        from_date = frappe.local.form_dict.get('from_date')
        to_date = frappe.local.form_dict.get('to_date')
        page = int(frappe.local.form_dict.get('page', 1))
        page_length = int(frappe.local.form_dict.get('page_length', 20))
        sort_by = frappe.local.form_dict.get('sort_by', '')

        # Initialize conditions and values for SQL query
        conditions = ["si.docstatus = 1", "si.outstanding_amount != 0"]
        values = {}

        if from_date:
            conditions.append("si.posting_date >= %(from_date)s")
            values["from_date"] = frappe.utils.data.getdate(from_date)

        if to_date:
            conditions.append("si.posting_date <= %(to_date)s")
            values["to_date"] = frappe.utils.data.getdate(to_date)

        if customer:
            conditions.append("si.customer = %(customer)s")
            values["customer"] = customer

        if session_user:
            conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
            values["session_user"] = session_user

        # Construct the WHERE clause for SQL query
        where_clause = " AND ".join(conditions)

        # Calculate offset for pagination
        offset = (page - 1) * page_length

        # Construct the main SQL query to get sales invoice data
        sql_query = f"""
            SELECT si.customer, si.name, si.posting_date, si.due_date, si.outstanding_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE {where_clause}
        """

        # Add sorting to the SQL query
        if sort_by == 'amount_high_low':
            sql_query += " ORDER BY si.outstanding_amount DESC"
        elif sort_by == 'amount_low_high':
            sql_query += " ORDER BY si.outstanding_amount ASC"
        elif sort_by == "date_recent":
            sql_query += " ORDER BY si.posting_date DESC"
        elif sort_by == "date_oldest":
            sql_query += " ORDER BY si.posting_date ASC"

        # Add pagination to the SQL query
        sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

        values["page_length"] = page_length
        values["offset"] = offset

        # Execute the main SQL query to get sales invoice data
        sales_invoice_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Construct the SQL query to fetch total outstanding amount
        total_sql_query = f"""
            SELECT SUM(si.outstanding_amount) AS total_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE {where_clause}
        """

        # Execute the SQL query to fetch total outstanding amount
        total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
        total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

        # Creating the response
        synced_time = timeOfZone(datetime.now())
        create_response(200, "Sales Invoice Outstanding Data fetched successfully", {
            "time": synced_time,
            "grand_total": total_amount,
            "data": sales_invoice_data
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Invoice Outstanding Data Fetching Failed")
        create_response(500, "An error occurred while fetching Sales Invoice Outstanding data. Please try again later.", str(e))


# Sales Credit Note (Gross)
@frappe.whitelist()
def get_sales_credit_with_customers_paginated():
    
    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee" , {"user_id" : active_user} , "name")
    session_user = frappe.db.get_value("Sales Person" , {"employee" : emp} , "name")

    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
        
    conditions = []
    values = {}

    if from_date:
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if session_user:
        conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
        values["session_user"] = session_user

    # Constructing the WHERE clause for SQL query
    where_clause = " AND ".join(conditions)

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get customer-wise total sales
    sql_query = """
        SELECT si.customer, SUM(si.rounded_total) AS total_amount
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st ON si.name = st.parent
        LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
        WHERE si.docstatus = 1 AND si.is_return = 1 AND {where_clause}
        GROUP BY si.customer
    """.format(where_clause=where_clause)

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY total_amount DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY total_amount ASC"
    elif sort_by == 'name_a_z':
        sql_query += " ORDER BY customer ASC"
    elif sort_by == 'name_z_a':
        sql_query += " ORDER BY customer DESC"

    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    try:
        # Executing the SQL query to get customer-wise total sales
        customer_sales_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Constructing the SQL query to fetch total amount
        total_sql_query = """
            SELECT SUM(si.rounded_total) AS total_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE si.docstatus = 1 AND si.is_return = 1 AND {where_clause}
        """.format(where_clause=where_clause)

        # Executing the SQL query to fetch total amount
        total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
        total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

        # Generate a list of months within the specified date range
        start_date = datetime.strptime(from_date, "%Y-%m-%d").replace(day=1)
        end_date = datetime.strptime(to_date, "%Y-%m-%d").replace(day=1)
        months_list = [start_date + timedelta(days=31*i) for i in range((end_date - start_date).days // 31 + 2)]

        # Executing the SQL query to fetch month-wise sales sums
        month_wise_data = []
        for month in months_list:
            month_data = frappe.db.sql("""
                SELECT  
                    DATE_FORMAT(%(month)s, '%%Y-%%b') AS month_year, 
                    COALESCE(SUM(si.rounded_total), 0) AS total_amount
                FROM
                    `tabSales Invoice` si
                LEFT JOIN 
                    `tabSales Team` st ON si.name = st.parent
                LEFT JOIN 
                    `tabSales Person` sp ON st.sales_person = sp.name
                WHERE 
                    si.docstatus = 1 AND si.is_return = 1 AND DATE_FORMAT(si.posting_date, '%%Y-%%m') = DATE_FORMAT(%(month)s, '%%Y-%%m') AND {where_clause}
            """.format(where_clause=where_clause), {"month": month.strftime("%Y-%m-%d"), **values}, as_dict=True)
            month_wise_data.append(month_data[0] if month_data else {"month_year": month.strftime("%Y-%b"), "total_amount": 0})

        # Creating a response
        synced_time = timeOfZone(datetime.now())         
        create_response(200, "Customer Sales Credit (Gross) Data fetched successfully", {
            "time": synced_time,
            "grand_total": total_amount,
            "month_wise_total": month_wise_data,
            "data": customer_sales_data
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Sales Credit (Gross)  Data Fetching Failed")
        create_response(500, "An error occurred while fetching Customer Sales Credit (Gross)  Data. Please try again later.", str(e))


# Sales Credit Note (Gross) - Customer Wise Sales Invoice Return
@frappe.whitelist()
def get_sales_invoce_credit_with_customers_paginated():
    
    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee" , {"user_id" : active_user} , "name")
    session_user = frappe.db.get_value("Sales Person" , {"employee" : emp} , "name")

    customer = frappe.local.form_dict.get('customer')
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
        
    conditions = []
    values = {}

    if from_date:
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if customer:
        conditions.append("si.customer = %(customer)s")
        values["customer"] = customer

    if session_user:
        conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
        values["session_user"] = session_user

    # Constructing the WHERE clause for SQL query
    where_clause = " AND ".join(conditions)

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get sales invoice data
    sql_query = """
        SELECT si.name, si.posting_date, si.customer, si.rounded_total
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st ON si.name = st.parent
        LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
        WHERE si.docstatus = 1 AND si.is_return = 1 AND {where_clause}
    """.format(where_clause=where_clause)

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY rounded_total ASC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY rounded_total DESC"
    elif sort_by == "date_recent":
        sql_query += " ORDER BY posting_date DESC"
    elif sort_by == "date_oldest":
        sql_query += " ORDER BY posting_date ASC"

    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    try:
        # Executing the SQL query to get sales invoice data
        sales_invoice_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Constructing the SQL query to fetch total amount
        total_sql_query = """
            SELECT SUM(si.rounded_total) AS total_amount
            FROM `tabSales Invoice` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE si.docstatus = 1 AND si.is_return = 1 AND {where_clause}
        """.format(where_clause=where_clause)

        # Executing the SQL query to fetch total amount
        total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
        total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

        # Generate a list of months within the specified date range
        start_date = datetime.strptime(from_date, "%Y-%m-%d").replace(day=1)
        end_date = datetime.strptime(to_date, "%Y-%m-%d").replace(day=1)
        months_list = [start_date + timedelta(days=31*i) for i in range((end_date - start_date).days // 31 + 2)]

        # Executing the SQL query to fetch month-wise sales sums
        month_wise_data = []
        for month in months_list:
            month_data = frappe.db.sql("""
                SELECT  
                    DATE_FORMAT(%(month)s, '%%Y-%%b') AS month_year, 
                    COALESCE(SUM(si.rounded_total), 0) AS total_amount
                FROM
                    `tabSales Invoice` si
                LEFT JOIN 
                    `tabSales Team` st ON si.name = st.parent
                LEFT JOIN 
                    `tabSales Person` sp ON st.sales_person = sp.name
                WHERE 
                    si.docstatus = 1 AND si.is_return = 1 AND DATE_FORMAT(si.posting_date, '%%Y-%%m') = DATE_FORMAT(%(month)s, '%%Y-%%m') AND {where_clause}
            """.format(where_clause=where_clause), {"month": month.strftime("%Y-%m-%d"), **values}, as_dict=True)
            month_wise_data.append(month_data[0] if month_data else {"month_year": month.strftime("%Y-%b"), "total_amount": 0})

        # Creating a response
        synced_time = timeOfZone(datetime.now())         
        create_response(200, "Sales Invoice Credit Data fetched successfully", {
            "time": synced_time,
            "grand_total": total_amount,
            "month_wise_total": month_wise_data,
            "data": sales_invoice_data
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Invoice Credit Data Fetching Failed")
        create_response(500, "An error occurred while fetching Sales Invoice Credit Data . Please try again later.", str(e))


# Sales Order
#Sales Order With Customer
@frappe.whitelist()
def get_sales_order_with_customers_paginated():
    
    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee" , {"user_id" : active_user} , "name")
    session_user = frappe.db.get_value("Sales Person" , {"employee" : emp} , "name")

    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
        
    conditions = []
    values = {}

    if from_date:
        conditions.append("si.transaction_date >= %(from_date)s")
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions.append("si.transaction_date <= %(to_date)s")
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if session_user:
        conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
        values["session_user"] = session_user

    # Constructing the WHERE clause for SQL query
    where_clause = " AND ".join(conditions)

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get customer-wise total sales
    sql_query = """
        SELECT si.customer, SUM(si.rounded_total) AS total_amount
        FROM `tabSales Order` si
        LEFT JOIN `tabSales Team` st ON si.name = st.parent
        LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
        WHERE si.docstatus = 1 AND {where_clause}
        GROUP BY si.customer
    """.format(where_clause=where_clause)

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY total_amount DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY total_amount ASC"
    elif sort_by == 'name_a_z':
        sql_query += " ORDER BY customer ASC"
    elif sort_by == 'name_z_a':
        sql_query += " ORDER BY customer DESC"

    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    try:
        # Executing the SQL query to get customer-wise total sales
        customer_sales_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Constructing the SQL query to fetch total amount
        total_sql_query = """
            SELECT SUM(si.rounded_total) AS total_amount
            FROM `tabSales Order` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE si.docstatus = 1 AND {where_clause}
        """.format(where_clause=where_clause)

        # Executing the SQL query to fetch total amount
        total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
        total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

        # Generate a list of months within the specified date range
        start_date = datetime.strptime(from_date, "%Y-%m-%d").replace(day=1)
        end_date = datetime.strptime(to_date, "%Y-%m-%d").replace(day=1)
        months_list = [start_date + timedelta(days=31*i) for i in range((end_date - start_date).days // 31 + 2)]

        # Executing the SQL query to fetch month-wise sales sums
        month_wise_data = []
        for month in months_list:
            month_data = frappe.db.sql("""
                SELECT  
                    DATE_FORMAT(%(month)s, '%%Y-%%b') AS month_year, 
                    COALESCE(SUM(si.rounded_total), 0) AS total_amount
                FROM
                    `tabSales Order` si
                LEFT JOIN 
                    `tabSales Team` st ON si.name = st.parent
                LEFT JOIN 
                    `tabSales Person` sp ON st.sales_person = sp.name
                WHERE 
                    si.docstatus = 1 AND DATE_FORMAT(si.transaction_date, '%%Y-%%m') = DATE_FORMAT(%(month)s, '%%Y-%%m') AND {where_clause}
            """.format(where_clause=where_clause), {"month": month.strftime("%Y-%m-%d"), **values}, as_dict=True)
            month_wise_data.append(month_data[0] if month_data else {"month_year": month.strftime("%Y-%b"), "total_amount": 0})

        # Creating a response
        synced_time = timeOfZone(datetime.now())         
        create_response(200, "Customer Sales Order Data fetched successfully", {
            "time": synced_time,
            "grand_total": total_amount,
            "month_wise_total": month_wise_data,
            "data": customer_sales_data
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Sales Order  Data Fetching Failed")
        create_response(500, "An error occurred while fetching Customer Sales Order  Data. Please try again later.", str(e))


# Sales Order - Customer Wise Sales Order
@frappe.whitelist()
def get_sales_order_list_with_customers_paginated():
    # Get the current logged-in user
    active_user = frappe.session.user
    emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
    session_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")

    customer = frappe.local.form_dict.get('customer')
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
    order_type = frappe.local.form_dict.get('order_type', '')

    # Add order_type Empty
    if not order_type:
        order_type = 'All'
        
    conditions = []
    values = {}

    if from_date:
        conditions.append("si.transaction_date >= %(from_date)s")
        values["from_date"] = getdate(from_date)

    if to_date:
        conditions.append("si.transaction_date <= %(to_date)s")
        values["to_date"] = getdate(to_date)

    if customer:
        conditions.append("si.customer = %(customer)s")
        values["customer"] = customer

    if session_user:
        conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
        values["session_user"] = session_user

    # Add condition for order_type
    valid_order_types = {
        "Draft": "Draft",
        "On Hold": "On Hold",
        "To Deliver and Bill": "To Deliver and Bill",
        "To Bill": "To Bill",
        "To Deliver": "To Deliver",
        "Completed": "Completed",
        "Cancelled": "Cancelled",
        "Closed": "Closed"
    }

    if order_type in valid_order_types:
        conditions.append("si.status = %(order_type)s")
        values["order_type"] = valid_order_types[order_type]
    elif order_type != "All":
        return {
            "status_code": 400,
            "message": f"Invalid order_type: {order_type}. Valid values are: All, Draft, On Hold, To Deliver and Bill, To Bill, To Deliver, Completed, Cancelled, Closed."
        }

    where_clause = " AND ".join(conditions)
    offset = (page - 1) * page_length

    sql_query = f"""
        SELECT si.name, si.transaction_date, si.status, si.customer, si.rounded_total
        FROM `tabSales Order` si
        LEFT JOIN `tabSales Team` st ON si.name = st.parent
        LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
        WHERE {where_clause}
    """

    sort_options = {
        'amount_high_low': " ORDER BY rounded_total DESC",
        'amount_low_high': " ORDER BY rounded_total ASC",
        'date_recent': " ORDER BY transaction_date DESC",
        'date_oldest': " ORDER BY transaction_date ASC"
    }
    sql_query += sort_options.get(sort_by, "")
    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    try:
        sales_invoice_data = frappe.db.sql(sql_query, values, as_dict=True)

        total_sql_query = f"""
            SELECT SUM(si.rounded_total) AS total_amount
            FROM `tabSales Order` si
            LEFT JOIN `tabSales Team` st ON si.name = st.parent
            LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
            WHERE {where_clause}
        """

        total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
        total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

        start_date = getdate(from_date).replace(day=1)
        end_date = getdate(to_date).replace(day=1)
        months_list = [start_date + timedelta(days=31*i) for i in range((end_date - start_date).days // 31 + 2)]

        month_wise_data = []
        for month in months_list:
            month_data = frappe.db.sql(f"""
                SELECT  
                    DATE_FORMAT(%(month)s, '%%Y-%%b') AS month_year, 
                    COALESCE(SUM(si.rounded_total), 0) AS total_amount
                FROM
                    `tabSales Order` si
                LEFT JOIN 
                    `tabSales Team` st ON si.name = st.parent
                LEFT JOIN 
                    `tabSales Person` sp ON st.sales_person = sp.name
                WHERE 
                    {where_clause} AND DATE_FORMAT(si.transaction_date, '%%Y-%%m') = DATE_FORMAT(%(month)s, '%%Y-%%m')
            """, {"month": month.strftime("%Y-%m-%d"), **values}, as_dict=True)
            month_wise_data.append(month_data[0] if month_data else {"month_year": month.strftime("%Y-%b"), "total_amount": 0})

        # Creating a response
        synced_time = timeOfZone(datetime.now())         
        create_response(200, "Customer Sales Order List Data fetched successfully", {
            "time": synced_time,
            "grand_total": total_amount,
            "month_wise_total": month_wise_data,
            "data": sales_invoice_data
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sales Order Data Fetching Failed")
        return {
            "status_code": 500,
            "message": "An error occurred while fetching Sales Order Data. Please try again later.",
            "error": str(e)
        }
# @frappe.whitelist()
# def get_sales_order_list_with_customers_paginated():
    
#     # Get the current logged-in user
#     active_user = frappe.session.user
#     emp = frappe.db.get_value("Employee" , {"user_id" : active_user} , "name")
#     session_user = frappe.db.get_value("Sales Person" , {"employee" : emp} , "name")

#     customer = frappe.local.form_dict.get('customer')
#     from_date = frappe.local.form_dict.get('from_date')
#     to_date = frappe.local.form_dict.get('to_date')
#     page = int(frappe.local.form_dict.get('page', 1))
#     page_length = int(frappe.local.form_dict.get('page_length', 20))
#     sort_by = frappe.local.form_dict.get('sort_by', '')
        
#     conditions = []
#     values = {}

#     if from_date:
#         conditions.append("si.transaction_date >= %(from_date)s")
#         values["from_date"] = frappe.utils.data.getdate(from_date)

#     if to_date:
#         conditions.append("si.transaction_date <= %(to_date)s")
#         values["to_date"] = frappe.utils.data.getdate(to_date)
    
#     if customer:
#         conditions.append("si.customer = %(customer)s")
#         values["customer"] = customer

#     if session_user:
#         conditions.append("(sp.name = %(session_user)s OR sp.parent_sales_person = %(session_user)s)")
#         values["session_user"] = session_user

#     # Constructing the WHERE clause for SQL query
#     where_clause = " AND ".join(conditions)

#     # Calculate offset based on page number and page size
#     offset = (page - 1) * page_length

#     # Constructing the SQL query to get sales invoice data
#     sql_query = """
#         SELECT si.name, si.transaction_date, si.status, si.customer, si.rounded_total
#         FROM `tabSales Order` si
#         LEFT JOIN `tabSales Team` st ON si.name = st.parent
#         LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
#         WHERE si.docstatus = 1 AND {where_clause}
#     """.format(where_clause=where_clause)

#     if sort_by == 'amount_high_low':
#         sql_query += " ORDER BY rounded_total DESC"
#     elif sort_by == 'amount_low_high':
#         sql_query += " ORDER BY rounded_total ASC"
#     elif sort_by == "date_recent":
#         sql_query += " ORDER BY transaction_date DESC"
#     elif sort_by == "date_oldest":
#         sql_query += " ORDER BY transaction_date ASC"

#     sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

#     values["page_length"] = page_length
#     values["offset"] = offset

#     try:
#         # Executing the SQL query to get sales invoice data
#         sales_invoice_data = frappe.db.sql(sql_query, values, as_dict=True)

#         # Constructing the SQL query to fetch total amount
#         total_sql_query = """
#             SELECT SUM(si.rounded_total) AS total_amount
#             FROM `tabSales Order` si
#             LEFT JOIN `tabSales Team` st ON si.name = st.parent
#             LEFT JOIN `tabSales Person` sp ON st.sales_person = sp.name
#             WHERE si.docstatus = 1 AND {where_clause}
#         """.format(where_clause=where_clause)

#         # Executing the SQL query to fetch total amount
#         total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
#         total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

#         # Generate a list of months within the specified date range
#         start_date = datetime.strptime(from_date, "%Y-%m-%d").replace(day=1)
#         end_date = datetime.strptime(to_date, "%Y-%m-%d").replace(day=1)
#         months_list = [start_date + timedelta(days=31*i) for i in range((end_date - start_date).days // 31 + 2)]

#         # Executing the SQL query to fetch month-wise sales sums
#         month_wise_data = []
#         for month in months_list:
#             month_data = frappe.db.sql("""
#                 SELECT  
#                     DATE_FORMAT(%(month)s, '%%Y-%%b') AS month_year, 
#                     COALESCE(SUM(si.rounded_total), 0) AS total_amount
#                 FROM
#                     `tabSales Order` si
#                 LEFT JOIN 
#                     `tabSales Team` st ON si.name = st.parent
#                 LEFT JOIN 
#                     `tabSales Person` sp ON st.sales_person = sp.name
#                 WHERE 
#                     si.docstatus = 1 AND DATE_FORMAT(si.transaction_date, '%%Y-%%m') = DATE_FORMAT(%(month)s, '%%Y-%%m') AND {where_clause}
#             """.format(where_clause=where_clause), {"month": month.strftime("%Y-%m-%d"), **values}, as_dict=True)
#             month_wise_data.append(month_data[0] if month_data else {"month_year": month.strftime("%Y-%b"), "total_amount": 0})

#         # Creating a response
#         synced_time = timeOfZone(datetime.now())         
#         create_response(200, "Sales Order Data fetched successfully", {
#             "time": synced_time,
#             "grand_total": total_amount,
#             "month_wise_total": month_wise_data,
#             "data": sales_invoice_data
#         })
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "Sales Order Data Fetching Failed")
#         create_response(500, "An error occurred while fetching Sales Order Data . Please try again later.", str(e))


#Outstanding PDF
@frappe.whitelist()
def download_outstanding_pdf(customer, from_date, to_date):
    synced_time = timeOfZone(datetime.now())    
    check_name = f"AC-{customer}-{synced_time}"
    base_url = frappe.utils.get_url()
    company = "ABK Imports Pvt Ltd"
    if not frappe.db.exists("Process Statement Of Accounts", check_name):
        try:
            # Create a new document
            psa = frappe.new_doc("Process Statement Of Accounts")
            psa.append("customers", {
                'customer': customer
            })
            psa.__newname = check_name
            psa.report = "Accounts Receivable"
            psa.company = company
            psa.from_date = from_date
            psa.to_date = to_date
            psa.primary_mandatory = 0
            psa.pdf_name = check_name
            psa.orientation = "Portrait"
            psa.letter_head = "ABK Inward"
            psa.insert(ignore_permissions=True)
            
            # Generate URL for downloading the document
            name = psa.name
            url = f"{base_url}/api/method/erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.download_statements?document_name={name}"
            return url
            
        except Exception as e:
            # Log the error for debugging purposes
            frappe.log_error(f"Error in creating Process Statement Of Accounts: {e}")
            return "Error: Document creation failed. Please check the server logs for details."
        
    else:
        # Document already exists, return URL for downloading
        url = f"{base_url}/api/method/erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.download_statements?document_name={check_name}"
        return url

#GL Report PDF Download
@frappe.whitelist()
def download_ledger_pdf(customer, from_date, to_date):
    check_name = f"GL-{customer}-{from_date}/{to_date}"
    base_url = frappe.utils.get_url()
    company = "ABK Imports Pvt Ltd"
    if not frappe.db.exists("Process Statement Of Accounts", check_name):
        try:
            # Create a new document
            psa = frappe.new_doc("Process Statement Of Accounts")
            psa.append("customers", {
                'customer': customer
            })
            psa.__newname = check_name
            psa.report = "General Ledger"
            psa.company = company
            psa.from_date = from_date
            psa.to_date = to_date
            psa.primary_mandatory = 0
            psa.pdf_name = check_name
            psa.orientation = "Portrait"
            psa.letter_head = "ABK Inward"
            psa.insert(ignore_permissions=True)
            
            # Generate URL for downloading the document
            name = psa.name
            url = f"{base_url}/api/method/erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.download_statements?document_name={name}"
            return url
            
        except Exception as e:
            # Log the error for debugging purposes
            frappe.log_error(f"Error in creating Process Statement Of Accounts: {e}")
            return "Error: Document creation failed. Please check the server logs for details."
        
    else:
        # Document already exists, return URL for downloading
        url = f"{base_url}/api/method/erpnext.accounts.doctype.process_statement_of_accounts.process_statement_of_accounts.download_statements?document_name={check_name}"
        return url