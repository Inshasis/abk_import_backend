import frappe

def handle_doc_trash(self, method):

    doc = frappe.new_doc("Deleted Doc Reference")
    doc = frappe.get_doc({
            'doctype': "Deleted Doc Reference",
            'doc_name' : self.name,
            'doc_type' : self.doctype
        })
    doc.insert(ignore_permissions=True)
    
def on_user_update(self,method):
    employee = frappe.db.get_value("Employee",{"user_id" : self.email} ,"name")
    if employee:
        sales_person = frappe.db.get_value("Sales Person" , {"employee" : employee} , "name")
        if sales_person:
            frappe.db.set_value("Sales Person", sales_person , {
                "enabled" : self.enabled
            })
            frappe.db.commit()