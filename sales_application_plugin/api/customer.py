import frappe # type: ignore
from sales_application_plugin.api.utils import create_response, get_allowed_customer # type: ignore
from datetime import datetime
import json
from frappe.utils import now # type: ignore

@frappe.whitelist()
def check_in():

    customer = frappe.local.form_dict.customer
    sales_person = frappe.local.form_dict.sales_person
    address = frappe.local.form_dict.address
    sales_person_location = frappe.local.form_dict.sales_person_location
    latitude = frappe.local.form_dict.latitude
    longitude = frappe.local.form_dict.longitude
    checkin_address = frappe.local.form_dict.checkin_address

    checkin_doc= frappe.get_doc({
        "doctype"  : "CheckIn-Out",
        "customer" : customer,
        "customer_location" : address,
        "sales_person" : sales_person,
        "in_datetime" : now(),
        "sales_person_location" : sales_person_location,
        "latitude":latitude,
        "longitude":longitude,
        "checkin_address":checkin_address

    })
    try:
        res = checkin_doc.insert(ignore_permissions = True) 
        create_response(200,"Checkin successfully",res)
    except Exception as e:
        frappe.log_error(title= "Creation Checkin" , message= e)
        create_response(406,"Checkin Error", e)
    

@frappe.whitelist()
def check_out():

    name = frappe.local.form_dict.name
    audio_note = frappe.local.form_dict.audio_note
    notes = frappe.local.form_dict.notes
    
    checkin_doc= frappe.get_doc("CheckIn-Out", name)

    if checkin_doc:
        checkin_doc.audio_note = audio_note
        checkin_doc.out_datetime = now()
        checkin_doc.notes = notes
        try:
            res = checkin_doc.save(ignore_permissions = True) 
            create_response(200,"Checkout successfully",{})
        except Exception as e:
            frappe.log_error(title= "Update Checkout" , message= e)
            create_response(406,"Checkout Error", e)
    else:
        create_response(200,"Checkout successfully",{})

@frappe.whitelist()
def get_addresses():
    customer = frappe.local.form_dict.customer
    
    try:
        address_of_customers = frappe.db.sql("""
                select a.name , a.address_title as title, a.address_line1 as address , a.address_type as type, a.city, a.state, a.country, a.pincode,a.phone, a.geolocation_details as location, dl.link_name as customer 
                FROM `tabAddress` a LEFT JOIN `tabDynamic Link` dl on dl.parent = a.name and dl.link_doctype = 'Customer' where dl.link_name = %(customer)s
            """, {
                "customer" : customer
            },as_dict = True)

        address_of_customers = list(map(map_address, address_of_customers))

        create_response(200,"Addresses fethced successfully", address_of_customers or [])
    except Exception as e:
        frappe.log_error(title= "Fetch Customer Address" , message= e)
        create_response(406,"Fetch Customer Address Error", e)    

def map_address(data):
    data["location"] = json.loads(data["location"])["features"][0]["geometry"]["coordinates"] if data["location"] is not None else []
    return data

@frappe.whitelist()
def get_allowed_customer_list():
    customers = get_allowed_customer(user= frappe.local.form_dict.user)
    create_response(200,"Addresses fethced successfully", customers or [])