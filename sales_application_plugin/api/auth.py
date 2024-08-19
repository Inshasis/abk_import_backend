import frappe

from frappe.utils import escape_html
from frappe.utils import escape_html
from frappe import throw, msgprint, _
import base64
from sales_application_plugin.api.utils import create_response


@frappe.whitelist(allow_guest=True)
def login(usr,pwd,device_id=None):
    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=usr,pwd=pwd)
        login_manager.post_login()
        set_device_id(usr,device_id)
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        frappe.local.response.http_status_code = 422
        frappe.local.response["message"] =  "Invalid Email or Password"
        return
    # frappe.errprint(frappe.session)
    
    user = frappe.get_doc('User',frappe.session.user)

    api_generate=generate_keys(user)
       
    token_string = str(api_generate['api_key']) +":"+ str(api_generate['api_secret'])

    default_company = frappe.db.get_single_value('Global Defaults','default_company')
    if default_company:
        default_company_doc = frappe.get_doc("Company" , default_company)

    employee = frappe.db.get_value("Employee",{"user_id" : user.email} ,"name")
    sales_person = None
    sales_manager = 0
    if employee:
        sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
        sales_manager = frappe.db.get_value("Sales Person" , {"employee" : employee} , "is_group")

    if not sales_person  or not employee:
        create_response(422 ,"Sales Person Employee mapping is not correctly done for your user, Kindly contact admin!")
        return 

    frappe.response["user"] =   {
        "first_name": escape_html(user.first_name or ""),
        "last_name": escape_html(user.last_name or ""),
        "gender": escape_html(user.gender or "") or "",
        "birth_date": user.birth_date or "",       
        "mobile_no": user.mobile_no or "",
        "username":user.username or "",
        "full_name":user.full_name or "",
        "email":user.email or "",
        "sales_id" : sales_person if sales_person is not None else "",
        "sales_manager" : sales_manager == 1,
        "company" : {
            "name" : default_company_doc.name or "",
            "email" : default_company_doc.email or "",
            "website" : default_company_doc.website or ""
        }
    }
    frappe.response["token"] =  base64.b64encode(token_string.encode("ascii")).decode("utf-8")

    return
    


def set_device_id(user,device_id):
    pass
    # frappe.db.set_value("User Device",{"user":user},"device_id",device_id)

def generate_keys(user):
    api_secret = api_key = ''
    if not user.api_key and not user.api_secret:
        api_secret = frappe.generate_hash(length=15)
        # if api key is not set generate api key
        api_key = frappe.generate_hash(length=15)
        user.api_key = api_key
        user.api_secret = api_secret
        user.save(ignore_permissions=True)
    else:
        api_secret = user.get_password('api_secret')
        api_key = user.get('api_key')
    return {"api_secret": api_secret, "api_key": api_key}

@frappe.whitelist(allow_guest=True)
def forgot_password(usr):
    email = frappe.db.get("User", {"email": usr})
    if email:
        frappe.response["message"] = "We have sent password reset link to your mail id, Please check your mail."
    else:
        frappe.response["message"] = "User does not exist"

