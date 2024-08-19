import frappe
from frappe.utils.print_format import download_pdf
from pytz import timezone

def create_response(status,message,data=None):
    frappe.local.response.http_status_code = status
    frappe.local.response.message = message
    if data is not None:
        frappe.local.response.data = data

def get_sales_persons(sales_person):
    label =parent = sales_person
    doctype = "Sales Person"

    data = get_all_nodes(doctype , label, parent)        

    sales_team = set([])
    for parent in data:
       sales_team.add(parent["parent"])
       for child in parent["data"]:
           sales_team.add(child["value"])
    return list(sales_team)

def get_item_groups(parent_item_group):
    label = parent = parent_item_group
    doctype = "Item Group"

    data = get_all_nodes(doctype , label, parent)        

    sales_team = set([])
    for parent in data:
       sales_team.add(parent["parent"])
       for child in parent["data"]:
           sales_team.add(child["value"])
    return list(sales_team) 

def get_all_nodes(doctype, label, parent):
	"""Recursively gets all data from tree nodes"""
        
	data = get_children(doctype, parent)
	out = [dict(parent=label, data=data)]

	to_check = [d.get("value") for d in data if d.get("expandable")]

	while to_check:
		parent = to_check.pop()
		data = get_children(doctype, parent)
		out.append(dict(parent=parent, data=data))
		for d in data:
			if d.get("expandable"):
				to_check.append(d.get("value"))

	return out   

def get_child(children , doctype , data):
    for d in data:
       if d.get("expandable"):    
           c_data = get_children(doctype, d.get("value")) 
           child = get_child([] , doctype , c_data)
           children.append(dict(name= d.get("value") , children = child))                        
       else:
           children.append(dict(name= d.get("value") , children = []))                

    return children  

def get_children(doctype, parent=""):
	return _get_children(doctype, parent)

def _get_children(doctype, parent="", ignore_permissions=True):
	parent_field = "parent_" + doctype.lower().replace(" ", "_")
	filters = [[f"ifnull(`{parent_field}`,'')", "=", parent], ["docstatus", "<", 2] , ["enabled","=","1"]]

	meta = frappe.get_meta(doctype)

	return frappe.get_list(
		doctype,
		fields=[
			"name as value",
			"{} as title".format(meta.get("title_field") or "name"),
			"is_group as expandable",
		],
		filters=filters,
		order_by="name",
		ignore_permissions=ignore_permissions,
	)     

def get_url_for_pdf(doctype, name):
    from frappe.utils.data import quoted
    doc = frappe.get_doc(doctype, name)
    return "{url}/api/method/sales_application_plugin.api.utils.pdf?doctype={doctype}&name={name}&key={key}".format(
        url=frappe.utils.get_url(),
        doctype=quoted(doctype),
        name=quoted(name),
        key=doc.get_signature()
    )


@frappe.whitelist(allow_guest=True)
def pdf(doctype, name, key):
    doc = frappe.get_doc(doctype, name)
    if not key == doc.get_signature():
        return 403
    download_pdf(doctype, name, format=None, doc=doc, no_letterhead=0)

@frappe.whitelist()
def get_allowed_customer(user,return_sales_person=0):
    employee = frappe.db.get_value("Employee",{"user_id":user},"name")
    if not employee:
        create_response(401 ,"Employee User mapping is not correctly done for your user, Kindly contact admin!")
        return 
    sales_person = frappe.db.get_value("Sales Person",{"employee":employee},"name")

    if not sales_person:
        if not employee:
            create_response(401 ,"Sales Person Employee mapping is not correctly done for your user, Kindly contact admin!")
            return 
    
    list_of_sales_person = get_sales_persons(sales_person)

    if return_sales_person:
        return list_of_sales_person
    
    # assigned_customer = frappe.db.sql("""
    # select cs.name from `tabCustomer` cs inner join `tabSales Team` st on cs.name = st.parent and st.parenttype = 'Customer' where st.sales_person in %(sales_persons)s 
    # """,{
    #     "sales_persons" : list_of_sales_person
    # },as_dict = 1)

    # customer_list = [item["name"] for item in assigned_customer]

    # create_response(200 ,"Employee User mapping is not correctly done for your user, Kindly contact admin!",customer_list)
    return get_assigned_customers_from_sales_person(list_of_sales_person)

def get_assigned_customers_from_sales_person(list_of_sales_person):
    # and cs.disabled = 0
    assigned_customer = frappe.db.sql("""
        select cs.name from `tabCustomer` cs inner join `tabSales Team` st on cs.name = st.parent and st.parenttype = 'Customer' where st.sales_person in %(sales_persons)s
        """,{
            "sales_persons" : list_of_sales_person
        },as_dict = 1)

    customer_list = [item["name"] for item in assigned_customer]

    # create_response(200 ,"Employee User mapping is not correctly done for your user, Kindly contact admin!",customer_list)
    return customer_list

@frappe.whitelist()
def get_allowed_price_list(user):
    list_of_sales_person = get_allowed_customer(user,return_sales_person=1)

    assigned_customer_group = frappe.db.sql("""
    select distinct cs.customer_group from `tabCustomer` cs inner join `tabSales Team` st on cs.name = st.parent and st.parenttype = 'Customer' where st.sales_person in %(sales_persons)s 
    """,{
        "sales_persons" : list_of_sales_person
    },as_dict = 1)

    customer_group_list = [item["customer_group"] for item in assigned_customer_group]

    price_lists = frappe.db.sql("""
    select default_price_list from `tabCustomer Group` where name in %(customer_group)s""",{
        "customer_group" : customer_group_list
    },as_dict = 1)

    price_lists_list = [item["default_price_list"] for item in price_lists]

    return price_lists_list

@frappe.whitelist()
def create_user_permission_for_customer(sales_person,employee):
    list_of_sales_person = get_sales_persons(sales_person)
    customer_list = get_assigned_customers_from_sales_person(list_of_sales_person)
    user_id = frappe.db.get_value("Employee",employee,"user_id")
    try:
        for customer in customer_list:
            up=frappe.get_doc({
                "doctype":"User Permission",
                "user":user_id,
                "allow":"Customer",
                "for_value":customer,
                "apply_to_all_document_type":1
            })
            up.save(ignore_permissions=1)
            frappe.msgprint("permission created for customer {}".format(customer))
    except Exception as e:
        pass
         

def timeOfZone(time):
    utc_time =  time.astimezone(timezone('Asia/Kolkata'))         
    return utc_time.strftime("%Y-%m-%d %H:%M:%S.%f")
         
         
    
     

     
