import frappe
from sales_application_plugin.api.utils import create_response, get_sales_persons,get_allowed_customer

@frappe.whitelist()
def check_debugging_enable(sales_person):
    debugging = frappe.db.get_value("Debugging Access Sales Person",{'sales_person':sales_person},"debugging")
    return True if debugging else False


@frappe.whitelist()
def get_total_counts():
    sales_person = frappe.local.form_dict.sales_person
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return

    customers = get_allowed_customer(frappe.session.user)
    gl_data  = frappe.db.sql("""
		select count(gl.name) as gl_count from `tabGL Entry` gl where gl.is_cancelled = 0 and gl.party_type = "Customer" and gl.party in %(customers)s and gl.voucher_type in %(voucher_types)s""", {
            "customers" : customers,
            "voucher_types" : ["Sales Invoice", "Payment Entry" , "Journal Entry"]
        } , as_dict=1)

    sales_order_data =  frappe.db.sql("""
		select count(name) as sales_order_count
		from `tabSales Order`
		where docstatus = 1 and customer in %(customers)s""" , {
            "customers" : customers
        } , as_dict=1)
    
    warehouse = frappe.db.get_list('Warehouse', pluck='name')
    try:
        items = frappe.db.sql("""
            SELECT
            count(i.name) as item_count
            FROM `tabItem` i""", {
            "warehouse":warehouse
        },as_dict = True)
    
        sales_persons = get_sales_persons(sales_person=sales_person)
    
        customers_data = frappe.db.sql("""
                SELECT
                count(cus.name) as party_count
                FROM `tabCustomer` cus 
                INNER JOIN `tabSales Team` st on st.parent = cus.name and st.sales_person in %(sales_persons)s
                LEFT JOIN `tabCustomer Credit Limit` ccl on ccl.parent = cus.name 
            """ , {
               
                "sales_persons" : sales_persons
            }, as_dict = True)

     
        create_response(200,"Customers list fetched successfully", {
            "gl_count" : gl_data[0].gl_count if len(gl_data) > 0 else 0,
            "orders_count" : sales_order_data[0].sales_order_count if len(sales_order_data) > 0 else 0,
            "party_count" : customers_data[0].party_count if len(customers_data) > 0 else 0,
            "item_count" : items[0].item_count if len(items) > 0 else 0
        })
    except Exception as ex:
        create_response(422,"Something went wrong!",ex)
        return
#total Number of gl entries of all parties

@frappe.whitelist()
def total_number_of_gl():
    customers = get_allowed_customer(frappe.session.user)
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    gl_data  = frappe.db.sql("""
		select count(gl.name) as gl_count from `tabGL Entry` gl where gl.is_cancelled = 0 and gl.party_type = "Customer" and gl.party in %(customers)s and gl.voucher_type in %(voucher_types)s""", {
            "customers" : customers,
            "voucher_types" : ["Sales Invoice", "Payment Entry" , "Journal Entry"]
        } , as_dict=1)
    create_response(200 , "GL Count fetched succcessfully", {
        "data" : gl_data,
    })

#total Number of gl entries party wise.
@frappe.whitelist()
def partywise_number_of_gl():
    customers = get_allowed_customer(frappe.session.user)
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    gl_data  = frappe.db.sql("""
		select count(gl.name) as gl_count,gl.party from `tabGL Entry` gl where gl.is_cancelled = 0 and gl.party_type = "Customer" and gl.party in %(customers)s and gl.voucher_type in %(voucher_types)s group by gl.party""", {
            "customers" : customers,
            "voucher_types" : ["Sales Invoice", "Payment Entry" , "Journal Entry"]
        } , as_dict=1)
    create_response(200 , "GL Count fetched succcessfully", {
        "data" : gl_data,
    })

#total sales.
@frappe.whitelist()
def total_sales():
    customers = get_allowed_customer(frappe.session.user)
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    gl_data  = frappe.db.sql("""
		select sum(gl.debit) as total_sales from `tabGL Entry` gl where gl.is_cancelled = 0 and gl.party_type = "Customer" and gl.party in %(customers)s and gl.voucher_type in %(voucher_types)s""", {
            "customers" : customers,
            "voucher_types" : ["Sales Invoice","Journal Entry"]
        } , as_dict=1)
    create_response(200 , "GL Count fetched succcessfully", {
        "data" : gl_data,
    })

#sales party wise.
@frappe.whitelist()
def party_wise_sales():
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    customers = get_allowed_customer(frappe.session.user)
    voucher_no = 'ACC-OPE'
    gl_data = frappe.db.sql("""
    select sum(debit) as payment, party from `tabGL Entry` where party_type ="Customer" and is_cancelled = 0 and ((voucher_type = 'Sales Invoice') or (voucher_type = 'Journal Entry' and voucher_no like %(voucher_no)s))  and credit = 0 and party in %(customers)s group by party
    """,{
            "customers" : customers,
            "voucher_no" : "%" + voucher_no + "%"
            
        } ,as_dict = 1)
    # gl_data  = frappe.db.sql("""
	# 	select sum(gl.debit) as payment,gl.party from `tabGL Entry` gl where gl.is_cancelled = 0 and gl.party_type = "Customer" and gl.party in %(customers)s and gl.voucher_type in %(voucher_types)s group by gl.party""", {
    #         "customers" : customers,
    #         "voucher_types" : ["Sales Invoice" , "Journal Entry"]
    #     } , as_dict=1)
    create_response(200 , "GL Count fetched succcessfully", gl_data)

#payment_wise_payments.
@frappe.whitelist()
def payment_wise_payments():
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    customers = get_allowed_customer(frappe.session.user)
    voucher_no = 'ACC-OPE'
    gl_data = frappe.db.sql("""
    select (sum(credit) - sum(debit)) as payment, party from `tabGL Entry` where party_type ="Customer" and is_cancelled = 0 and voucher_type in ('Payment Entry' , 'Journal Entry') and voucher_no not like %(voucher_no)s and party in %(customers)s group by party
    """, {
            "customers" : customers,
            "voucher_no" : voucher_no
        } , as_dict=1)
    # gl_data  = frappe.db.sql("""
	# 	select sum(gl.credit) as payment,gl.party from `tabGL Entry` gl where gl.is_cancelled = 0 and gl.party_type = "Customer" and gl.party in %(customers)s and gl.voucher_type in %(voucher_types)s group by gl.party""", {
    #         "customers" : customers,
    #         "voucher_types" : ["Payment Entry" , "Journal Entry"]
    #     } , as_dict=1)
    create_response(200 , "GL Count fetched succcessfully", gl_data)

#payment_wise_payments.
@frappe.whitelist()
def party_wise_credit():
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    customers = get_allowed_customer(frappe.session.user)

    gl_data  = frappe.db.sql("""
    select sum(credit) as payment, party from `tabGL Entry` where party_type ="Customer" and is_cancelled = 0 and voucher_type in ('Sales Invoice') and debit = 0 and party in %(customers)s group by party
    """,{
            "customers" : customers,
            
        } , as_dict=1)
    # gl_data  = frappe.db.sql("""
	# 	select sum(gl.credit) as payment,gl.party from `tabGL Entry` gl where gl.is_cancelled = 0 and gl.party_type = "Customer" and gl.party in %(customers)s and gl.voucher_type in %(voucher_types)s group by gl.party having payment > 0""", {
    #         "customers" : customers,
    #         "voucher_types" : ["Sales Invoice"]
    #     } , as_dict=1)
    create_response(200 , "GL Count fetched succcessfully", gl_data)

#number of sales order
@frappe.whitelist()
def total_sales_order_count():
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    customers = get_allowed_customer(frappe.session.user)
    sales_order_data =  frappe.db.sql("""
		select count(name) as sales_order_count
		from `tabSales Order`
		where docstatus = 1 and customer in %(customers)s""" , {
            "customers" : customers
        } , as_dict=1)
    
    create_response(200 , "Sales Report fetched succcessfully", {
        "data" : sales_order_data,
    })

@frappe.whitelist()
def party_count():
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    sales_person = frappe.local.form_dict.sales_person
    try:
        sales_persons = get_sales_persons(sales_person=sales_person)
    
        customers = frappe.db.sql("""
                SELECT
                count(cus.name) as party_count
                FROM `tabCustomer` cus 
                INNER JOIN `tabSales Team` st on st.parent = cus.name and st.sales_person in %(sales_persons)s
                LEFT JOIN `tabCustomer Credit Limit` ccl on ccl.parent = cus.name 
            """ , {
               
                "sales_persons" : sales_persons
            }, as_dict = True)

     
        create_response(200,"Customers list fetched successfully",{
           
            "data" : customers
        })
    except Exception as ex:
        create_response(422,"Something went wrong!",ex)
        return
    

#total item count
@frappe.whitelist()
def item_count():
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    warehouse = frappe.db.get_list('Warehouse', pluck='name')
    try:
        items = frappe.db.sql("""
            SELECT
            count(i.name) as item_count
            FROM `tabItem` i left join `tabBin` bn on bn.item_code = i.name and warehouse in %(warehouse)s""", {
            "warehouse":warehouse
        },as_dict = True)
        create_response(200,"Item list successfully",{
            "data" : items
        })
        return
    except Exception as ex:
        create_response(422,"Something went wrong!",ex)
        return

#warehousewise item stock
@frappe.whitelist()
def itemwise_stock():
    employee = frappe.db.get_value("Employee",{"user_id" : frappe.session.user} ,"name")
    sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
    if not check_debugging_enable(sales_person):
        create_response(406,"You are not allowed to this feature, kindly contact your Admin")
        return
    time = frappe.local.form_dict.time
    #Get allowed warehouse for user, So user can only see warehouse assigned to him.
    warehouse = frappe.db.get_list('Warehouse', pluck='name')
    try:
        items = frappe.db.sql("""
            SELECT
            i.name,
            IFNULL(sum(bn.actual_qty), 0) as total_qty
            FROM `tabItem` i left join `tabBin` bn on bn.item_code = i.name and warehouse in %(warehouse)s
            group by i.name 
        """,{
            "time" : time,
            "warehouse":warehouse
        },as_dict = True)
        create_response(200,"Item list successfully",{
            "data" : items
        })
        return
    except Exception as ex:
        create_response(422,"Something went wrong!",ex)
        return

