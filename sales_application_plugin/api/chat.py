import frappe
from sales_application_plugin.api.utils import create_response

@frappe.whitelist()
def get_chats():
    user = frappe.local.form_dict.user
    chats = frappe.db.sql("""
                SELECT
                name,
                name as id,
                name as chat_id,                          
                name as user_id,          
                members,
                last_message as message,
                is_read,
                type,
                modified as time FROM `tabChat Room` where members like %(user)s                              
            """, {  
                "user" : "%{}%".format(user)
            }, as_dict = True)
    

    create_response(200,"Customers list fetched successfully",chats)