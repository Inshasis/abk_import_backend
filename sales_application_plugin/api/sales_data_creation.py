import frappe
import random
from datetime import datetime, timedelta

def get_items_and_customers():

    items = frappe.db.get_all("Item Price" , fields = ['item_code'] , page_length = 50)
    customers = frappe.db.get_all("Customer" , fields = ['name'], page_length = 15)
    sales_persons = frappe.db.get_all("Sales Person" , fields = ['sales_person_name'] ,  filters = {
        'is_group' : 0
    }, page_length= 15)

    return {
        "items":[item['item_code'] for item in items],
        "customer":[item['name'] for item in customers],
        "sales_person":[item['sales_person_name'] for item in sales_persons]
    }

def generate_random_date(start_date, end_date):
    time_diff = end_date - start_date
    random_days = random.randint(0, time_diff.days)
    random_date = start_date + timedelta(days=random_days)
    return random_date.strftime('%Y-%m-%d')

def generate_order_data(num_orders=1):

    erp_data = get_items_and_customers()

    item_code = erp_data["items"]
    customer = erp_data["customer"]
    sales_person = erp_data["sales_person"]

    orders = []
    for _ in range(num_orders):
        transaction_date_str = generate_random_date(datetime(2021, 1, 1), datetime(2023, 8, 5))
        transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d')
        delivery_date_str = generate_random_date(transaction_date, datetime(2023, 8, 5))

        items_count = random.randint(1, 5)
        items = [{"item_code": random.choice(item_code), "qty": random.randint(1, 5), "rate": round(random.uniform(100.0, 5000.0),2)} for _ in range(items_count)]

        order = {
            "customer": random.choice(customer),
            "transaction_date": transaction_date_str,
            "delivery_date": delivery_date_str,
            "sales_team": [{
                "sales_person": random.choice(sales_person),
                "allocated_percentage": "100"
            }],
            "items": items
        }
        orders.append(order)

    return orders




def create_sales_orders():

    # Test
    num_orders = 500  # Change the value as per your requirement
    orders = generate_order_data(num_orders)
    print(orders)

    try:
        for order in orders:
            so = frappe.get_doc({
                'doctype':"Sales Order",
                'customer' : order['customer'],
                'transaction_date' : order['transaction_date'],
                'delivery_date' : order['delivery_date'],
                'sales_team' : order['sales_team'],
                'items':order['items']
            })
            res = so.save(ignore_permissions=True) 
            res.submit()
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(title = "Sales Order Creation form Sale bot",message=frappe.get_traceback())


def create_sales_invoices():
    num_invoices = 500  # Change the value as per your requirement
    invoices = generate_invoice_data(num_invoices)
    print(invoices)

    try:
        for invoice in invoices:
            so = frappe.get_doc({
                'doctype':"Sales Invoice",
                'customer' : invoice['customer'],
                'posting_date' : invoice['posting_date'],
                'due_date' : invoice['due_date'],
                'items':invoice['items']
            })
            res = so.save(ignore_permissions=True) 
            res.submit()
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(title = "Sales Invoice Creation form Sale bot",message=frappe.get_traceback())


def item_corr(item):
    item["sales_order"] = item["parent"]
    del item["parent"]
    return item 

def generate_invoice_data(num_invoices=1):

    
    # item_code = erp_data["items"]
    # customer = erp_data["customer"]
    sales_orders = frappe.db.get_all("Sales Order" , fields = ['name' , 'customer'])
    sales_order_items = frappe.db.get_all("Sales Order Item" , fields = ['item_code' , 'qty' , 'rate' , 'parent'])

    sales_order_items = list(map(item_corr, sales_order_items))

    invoices = []
    for _ in range(num_invoices):

        so = random.choice(sales_orders)
        transaction_date_str = generate_random_date(datetime(2021, 1, 1), datetime(2023, 8, 5))
        transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d')
        random_date = transaction_date + timedelta(days= 5)
        delivery_date_str = random_date.strftime('%Y-%m-%d')
        items = list(filter(lambda i : i["sales_order"] == so["name"], sales_order_items))

        invoice = {
            "customer": so["customer"],
            "posting_date": transaction_date_str,
            "due_date": delivery_date_str,
            "items": items
        }
        invoices.append(invoice)

    return invoices


# {
#     "customer": "Vivek",
#     "transaction_date": "2023-08-01",
#     "delivery_date": "2023-08-02",
#     "order_type": "Sales",
#     "items": [
#         {
#             "item_code": "0130-0000",
#             "qty": 1.0,
#             "rate": 900.0,
#         },
#         {
#             "item_code": "0162-0000",
#             "qty": 1.0,
#             "rate": 2000.0,
#         },
#         {
#             "item_code": "0161-0000",
#             "qty": 1.0,
#             "rate": 3000.0,
#         },
#     ],
# }


