import frappe
from datetime import datetime, timedelta
from sales_application_plugin.api.utils import create_response, timeOfZone
from functools import reduce
from frappe.utils import nowdate
import time
from frappe.utils.pdf import get_pdf
from frappe.utils.file_manager import save_file
import json

# Customer Wise Check In - Check Out
@frappe.whitelist()
def check_in_check_out():
    # Retrieve parameters from the request
    time = frappe.local.form_dict.get('time')
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    customer_name = frappe.local.form_dict.get('customer_name')
    sales_person_input = frappe.local.form_dict.get('sales_person')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    offset = (page - 1) * page_length

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")

    try:
        # Prepare the condition and parameters for the SQL queries
        condition = ""
        parameters = {
            "company": frappe.db.get_single_value('Global Defaults', 'default_company'),
            "sales_persons": tuple(salespersons),
            "offset": offset,
            "page_length": page_length
        }

        if time:
            condition += " AND cico.modified > %(time)s"
            parameters["time"] = time
        
        if from_date:
            condition += " AND cico.in_datetime >= %(from_date)s"
            parameters["from_date"] = frappe.utils.data.getdate(from_date)

        if to_date:
            condition += " AND cico.in_datetime <= %(to_date)s"
            parameters["to_date"] = frappe.utils.data.getdate(to_date)
            
        if customer_name:
            condition += " AND cico.customer LIKE %(customer_name)s"
            parameters["customer_name"] = f"%{customer_name}%"
        
        if sales_person_input:
            condition += " AND cico.sales_person LIKE %(sales_person_input)s"
            parameters["sales_person_input"] = f"%{sales_person_input}%"

        # Synced time for the response
        synced_time = datetime.now()

        # Count query to get the total number of matching customers
        count_query = f"""
            SELECT COUNT(DISTINCT cico.name) AS total_count
            FROM `tabCheckIn-Out` cico
            WHERE 1=1 AND sales_person IN %(sales_persons)s {condition}
        """

        total_count = frappe.db.sql(count_query, parameters, as_dict=True)[0]['total_count']

        # Main query to fetch the paginated list of customers
        main_query = f"""
            SELECT
                cico.name, cico.customer, cico.sales_person, cico.in_datetime, cico.out_datetime,cico.checkin_address
            FROM `tabCheckIn-Out` cico
            WHERE 1=1 AND sales_person IN %(sales_persons)s {condition}
            GROUP BY cico.name
            ORDER BY cico.in_datetime DESC
            LIMIT %(offset)s, %(page_length)s
        """

        customers = frappe.db.sql(main_query, parameters, as_dict=True)

        # Return the response
        create_response(200, "Check In - Check Out fetched successfully", {
            "time": synced_time,
            "total_count": total_count,
            "data": customers
        })
    except Exception as ex:
        create_response(422, "Something went wrong!", str(ex))


#Check In Check Out PDF
@frappe.whitelist()
def check_in_check_out_pdf():
    # Retrieve parameters from the request
    time = frappe.local.form_dict.get('time')
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    customer_name = frappe.local.form_dict.get('customer_name')
    sales_person_input = frappe.local.form_dict.get('sales_person')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    offset = (page - 1) * page_length

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")

    try:
        # Prepare the condition and parameters for the SQL queries
        condition = ""
        parameters = {
            "company": frappe.db.get_single_value('Global Defaults', 'default_company'),
            "sales_persons": tuple(salespersons),
            "offset": offset,
            "page_length": page_length
        }

        if time:
            condition += " AND cico.modified > %(time)s"
            parameters["time"] = time
        
        if from_date:
            condition += " AND cico.in_datetime >= %(from_date)s"
            parameters["from_date"] = frappe.utils.data.getdate(from_date)

        if to_date:
            condition += " AND cico.in_datetime <= %(to_date)s"
            parameters["to_date"] = frappe.utils.data.getdate(to_date)
            
        if customer_name:
            condition += " AND cico.customer LIKE %(customer_name)s"
            parameters["customer_name"] = f"%{customer_name}%"
        
        if sales_person_input:
            condition += " AND cico.sales_person LIKE %(sales_person_input)s"
            parameters["sales_person_input"] = f"%{sales_person_input}%"

        # Synced time for the response
        synced_time = datetime.now()

        # Count query to get the total number of matching customers
        count_query = f"""
            SELECT COUNT(DISTINCT cico.name) AS total_count
            FROM `tabCheckIn-Out` cico
            WHERE 1=1 AND sales_person IN %(sales_persons)s {condition}
        """

        total_count = frappe.db.sql(count_query, parameters, as_dict=True)[0]['total_count']

        # Main query to fetch the paginated list of customers
        main_query = f"""
            SELECT
                cico.name, cico.customer, cico.sales_person, cico.in_datetime, cico.out_datetime, cico.checkin_address
            FROM `tabCheckIn-Out` cico
            WHERE 1=1 AND sales_person IN %(sales_persons)s {condition}
            GROUP BY cico.name
            ORDER BY cico.in_datetime DESC
            LIMIT %(offset)s, %(page_length)s
        """

        customers = frappe.db.sql(main_query, parameters, as_dict=True)

        # Generate PDF
        html = frappe.render_template('templates/checkin_out_report.html', {'data': customers})
        pdf_content = get_pdf(html)

        # Save PDF file
        pdf_file = save_file(
            f"CheckInOut_Report_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf", 
            pdf_content, 
            dt=None, # Specify the DocType if you want to attach the file to a document
            dn=None, # Specify the document name if you want to attach the file to a document
            folder=None, 
            is_private=0
        )
        pdf_url = pdf_file.file_url

        # Return the response
        create_response(200, "Check In - Check Out PDF Create successfully", {
            "time": synced_time,
            "pdf_url": pdf_url
        })
    except Exception as ex:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch check-in/out data")
        create_response(422, "Something went wrong!", str(ex))


# Top Customer
@frappe.whitelist()
def get_top_customer():
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
    
    top_customer = frappe.local.form_dict.get('top_customer')
    try:
        top_customer = int(top_customer) if top_customer else None
    except ValueError:
        top_customer = None
    
    customer_name = frappe.local.form_dict.get('customer_name', '')

    conditions = ""
    values = {}

    if from_date:
        conditions += " AND si.posting_date >= %(from_date)s"
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions += " AND si.posting_date <= %(to_date)s"
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if customer_name:
        conditions += " AND si.customer LIKE %(customer_name)s"
        values["customer_name"] = f"%{customer_name}%"

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get customer-wise total sales
    sql_query = """
        SELECT si.customer, SUM(si.rounded_total) AS total_amount
        FROM `tabSales Invoice` si
        JOIN `tabSales Team` cst ON cst.parent = si.customer
        WHERE si.docstatus = 1 AND si.status NOT IN ('Credit Note Issued', 'Return') {conditions} {salespersons_condition}
        GROUP BY si.customer
    """.format(conditions=conditions, salespersons_condition=salespersons_condition)

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY total_amount DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY total_amount ASC"
    elif sort_by == 'name_a_z':
        sql_query += " ORDER BY si.customer ASC"
    elif sort_by == 'name_z_a':
        sql_query += " ORDER BY si.customer DESC"

    # Apply top_customer limit if provided
    if top_customer:
        sql_query += " LIMIT %(top_customer)s"

    sql_query += " OFFSET %(offset)s"

    values["top_customer"] = top_customer
    values["page_length"] = page_length
    values["offset"] = offset

    # Executing the SQL query to get customer-wise sales data
    customer_data = frappe.db.sql(sql_query, values, as_dict=True)

    # Constructing the SQL query to fetch the total sum of all customers' grand total amounts
    total_sql_query = """
        SELECT SUM(si.rounded_total) AS total_amount
        FROM `tabSales Invoice` si
        JOIN `tabSales Team` cst ON cst.parent = si.customer
        WHERE si.docstatus = 1 AND si.status NOT IN ('Credit Note Issued', 'Return') {conditions} {salespersons_condition}
    """.format(conditions=conditions, salespersons_condition=salespersons_condition)

    # Executing the SQL query to fetch the total sum securely
    total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
    total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

    # Creating a response
    synced_time = timeOfZone(datetime.now())
    return create_response(200, "Top Customer Data fetched successfully", {
        "time": synced_time,
        "rounded_total": total_amount,
        "top_customer_data": customer_data
    })



#Top Item
@frappe.whitelist()
def get_top_items():
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
    item_code = frappe.local.form_dict.get('item_code')
    top_item = frappe.local.form_dict.get('top_item')
    
    try:
        top_item = int(top_item) if top_item else None
    except ValueError:
        top_item = None

    conditions = ""
    values = {}

    if from_date:
        conditions += " AND si.posting_date >= %(from_date)s"
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions += " AND si.posting_date <= %(to_date)s"
        values["to_date"] = frappe.utils.data.getdate(to_date)

    if item_code:
        # Adjusting item_code filter to use wildcard in the value itself
        
        conditions += " AND (sii.item_code LIKE %(item_code)s OR sii.item_name LIKE %(item_code)s)"
        values["item_code"] = f"%{item_code}%"

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get item-wise total sales
    sql_query = """
        SELECT sii.item_code, sii.item_name, SUM(sii.amount) AS total_amount
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        JOIN `tabSales Team` cst ON cst.parent = si.customer
        WHERE si.docstatus = 1 AND si.status NOT IN ('Credit Note Issued', 'Return') {conditions} {salespersons_condition}
        GROUP BY sii.item_code, sii.item_name
    """.format(conditions=conditions, salespersons_condition=salespersons_condition)

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY total_amount DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY total_amount ASC"
    elif sort_by == 'name_a_z':
        sql_query += " ORDER BY sii.item_code ASC"
    elif sort_by == 'name_z_a':
        sql_query += " ORDER BY sii.item_code DESC"

    # Apply top_item limit if provided
    if top_item:
        sql_query += " LIMIT %(top_item)s"

    sql_query += " OFFSET %(offset)s"

    values["top_item"] = top_item
    values["page_length"] = page_length
    values["offset"] = offset
        
    # Executing the SQL query to get item-wise sales data
    item_data = frappe.db.sql(sql_query, values, as_dict=True)

    # Constructing the SQL query to fetch the total sum of all items' grand total amounts
    total_sql_query = """
        SELECT SUM(sii.amount) AS total_amount
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        JOIN `tabSales Team` cst ON cst.parent = si.customer
        WHERE si.docstatus = 1 AND si.status NOT IN ('Credit Note Issued', 'Return') {conditions} {salespersons_condition}
    """.format(conditions=conditions, salespersons_condition=salespersons_condition)

    # Executing the SQL query to fetch the total sum securely
    total_amount_data = frappe.db.sql(total_sql_query, values, as_dict=True)
    total_amount = total_amount_data[0]["total_amount"] if total_amount_data else 0

    # Creating a response
    synced_time = timeOfZone(datetime.now())
    return create_response(200, "Top Item Sales Gross Data fetched successfully", {
        "time": synced_time,
        "rounded_total": total_amount,
        "top_item_data": item_data
    })



#Inactive Customer
@frappe.whitelist()
def get_inactive_customers():
    inactive_days = frappe.local.form_dict.get('inactive_days')
    customer_filter = frappe.local.form_dict.get('customer')
    sort_by = frappe.local.form_dict.get('sort_by')  
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    from_date = frappe.local.form_dict.get('from_date') 
    to_date = frappe.local.form_dict.get('to_date') 

    try:
        inactive_days = int(inactive_days) if inactive_days else None
    except ValueError:
        inactive_days = None

    if not inactive_days:
        return create_response(400, "inactive_days parameter is required")

    values = {}

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    # Calculate the inactive date
    inactive_date = frappe.utils.data.add_days(frappe.utils.data.today(), -inactive_days)
    values["inactive_date"] = inactive_date

    customer_filter_condition = ""
    if customer_filter:
        customer_filter_condition = " AND si.customer LIKE %(customer_filter)s"
        values["customer_filter"] = f"%{customer_filter}%"

    date_range_condition = ""
    if from_date and to_date:
        date_range_condition = " AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s"
        values["from_date"] = from_date
        values["to_date"] = to_date

    sort_order_clause = ""
    if sort_by == 'name_a_z':
        sort_order_clause = " ORDER BY si.customer ASC"
    elif sort_by == 'name_z_a':
        sort_order_clause = " ORDER BY si.customer DESC"

    # Calculate the offset for pagination
    offset = (page - 1) * page_length
    pagination_clause = " LIMIT {} OFFSET {}".format(page_length, offset)

    #Fetch inactive customers with last sales invoice details
    inactive_customers_query = """
        SELECT DISTINCT si.customer,
            cst.sales_person,
            MAX(si.name) AS last_invoice_name,
            MAX(si.posting_date) AS last_invoice_date,
            MAX(si.rounded_total) AS last_invoice_amount
  
        FROM `tabSales Invoice` si
        JOIN `tabSales Team` cst ON cst.parent = si.customer
        WHERE si.docstatus = 1 AND si.status NOT IN ('Credit Note Issued', 'Return')
        AND si.posting_date < %(inactive_date)s
        {salespersons_condition}
        {customer_filter_condition}
        {date_range_condition}
        AND si.customer NOT IN (
            SELECT si2.customer
            FROM `tabSales Invoice` si2
            WHERE si2.posting_date >= %(inactive_date)s
            AND si2.docstatus = 1 AND si2.status NOT IN ('Credit Note Issued', 'Return')
        )
        GROUP BY si.customer
        {sort_order_clause}
        {pagination_clause}
    """.format(salespersons_condition=salespersons_condition,
               customer_filter_condition=customer_filter_condition,
               date_range_condition=date_range_condition,
               sort_order_clause=sort_order_clause,
               pagination_clause=pagination_clause)

    inactive_customers_data = frappe.db.sql(inactive_customers_query, values, as_dict=True)
    
    # Creating a response
    synced_time = timeOfZone(datetime.now())
    return create_response(200, "Inactive Customers fetched successfully", {
        "time": synced_time,
        "inactive_customers": inactive_customers_data
    })


#Inactive Items
@frappe.whitelist()
def get_inactive_items():
    import datetime
    
    # Fetching the input values
    inactive_days = frappe.local.form_dict.get('inactive_days')
    sort_by = frappe.local.form_dict.get('sort_by')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    from_date = frappe.local.form_dict.get('from_date') 
    to_date = frappe.local.form_dict.get('to_date')
    item_code = frappe.local.form_dict.get('item_code')

    try:
        # Convert inactive_days to integer
        inactive_days = int(inactive_days) if inactive_days else None
    except ValueError:
        inactive_days = None

    # Validate required parameters
    if not inactive_days:
        return create_response(400, "inactive_days parameter is required")

    # Initialize values dictionary for SQL parameters
    values = {}

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    # Function to recursively fetch salespersons hierarchy
    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    # Construct condition for filtering by salespersons
    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    # Calculate the inactive date
    inactive_date = frappe.utils.data.add_days(nowdate(), -inactive_days)
    values["inactive_date"] = inactive_date

    # Modify date range condition
    date_range_condition = ""
    if from_date and to_date:
        try:
            datetime.datetime.strptime(from_date, '%Y-%m-%d')
            datetime.datetime.strptime(to_date, '%Y-%m-%d')
        except ValueError:
            return create_response(400, "Invalid date format. Please use YYYY-MM-DD.")
        
        date_range_condition = " AND si_item.creation BETWEEN %(from_date)s AND %(to_date)s"
        values["from_date"] = from_date
        values["to_date"] = to_date

    # Construct item_code filter condition
    item_code_condition = ""
    if item_code:
        item_code_condition = " AND (si_item.item_code LIKE %(item_code)s OR si_item.item_name LIKE %(item_code)s)"
        values["item_code"] = f"%{item_code}%"

    # Construct sorting order clause
    sort_order_clause = ""
    if sort_by == 'name_a_z':
        sort_order_clause = " ORDER BY si_item.item_code ASC"
    elif sort_by == 'name_z_a':
        sort_order_clause = " ORDER BY si_item.item_code DESC"

    # Calculate the offset for pagination
    offset = (page - 1) * page_length
    pagination_clause = " LIMIT {} OFFSET {}".format(page_length, offset)

    # Construct the SQL query
    inactive_items_query = """
        SELECT 
            si_item.parent,
            cst.sales_person,
            si_item.creation,
            si_item.item_code,
            si_item.item_name,
            si_item.uom,
            COALESCE(SUM(bin.actual_qty), 0) AS stock
        FROM `tabSales Invoice` si
        JOIN `tabSales Team` cst ON cst.parent = si.customer
        JOIN `tabSales Invoice Item` si_item ON si.name = si_item.parent
        LEFT JOIN `tabBin` bin ON si_item.item_code = bin.item_code
        WHERE si.docstatus = 1 
            AND si.status NOT IN ('Credit Note Issued', 'Return')
            AND si.posting_date < %(inactive_date)s
            {salespersons_condition}
            {date_range_condition}
            {item_code_condition}
            AND si.customer NOT IN (
                SELECT si2.customer
                FROM `tabSales Invoice` si2
                WHERE si2.posting_date >= %(inactive_date)s
                    AND si2.docstatus = 1 
                    AND si2.status NOT IN ('Credit Note Issued', 'Return')
            )
        GROUP BY si_item.item_code
        {sort_order_clause}
        {pagination_clause}
    """.format(salespersons_condition=salespersons_condition,
               date_range_condition=date_range_condition,
               item_code_condition=item_code_condition,
               sort_order_clause=sort_order_clause,
               pagination_clause=pagination_clause)

    # Fetch inactive items data
    try:
        inactive_items_data = frappe.db.sql(inactive_items_query, values, as_dict=True)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch inactive items")
        return create_response(500, "Failed to fetch inactive items")

    # Creating a response
    synced_time = datetime.datetime.now()
    return create_response(200, "Inactive Items fetched successfully", {
        "time": synced_time,
        "inactive_data": inactive_items_data
    })




#Bounce Order
@frappe.whitelist()
def get_bounce_order():
    customer_filter = frappe.local.form_dict.get('customer')
    sort_by = frappe.local.form_dict.get('sort_by')  
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    from_date = frappe.local.form_dict.get('from_date') 
    to_date = frappe.local.form_dict.get('to_date') 

    values = {}

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    customer_filter_condition = ""
    if customer_filter:
        customer_filter_condition = " AND so.customer LIKE %(customer_filter)s"
        values["customer_filter"] = f"%{customer_filter}%"

    date_range_condition = ""
    if from_date and to_date:
        date_range_condition = " AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s"
        values["from_date"] = from_date
        values["to_date"] = to_date

    sort_order_clause = ""
    if sort_by == 'name_a_z':
        sort_order_clause = " ORDER BY customer ASC"
    elif sort_by == 'name_z_a':
        sort_order_clause = " ORDER BY customer DESC"

    # Calculate the offset for pagination
    offset = (page - 1) * page_length
    pagination_clause = " LIMIT {} OFFSET {}".format(page_length, offset)

    # Fetch inactive customers with last sales order details
    bounce_order_query = """
        SELECT 
            customer,
            MAX(order_name) AS order_name,
            SUM(total_qty) AS total_qty,
            SUM(delivered_qty) AS delivered_qty,
            SUM(bounce_qty) AS bounce_qty
        FROM (
            SELECT 
                so.customer,
                so.name AS order_name,           
                so.total_qty AS total_qty,
                SUM(item.delivered_qty) AS delivered_qty,
                so.total_qty - SUM(item.delivered_qty) AS bounce_qty
            FROM `tabSales Order` so
            JOIN `tabSales Team` cst ON cst.parent = so.name
            LEFT JOIN `tabSales Order Item` item ON item.parent = so.name
            WHERE so.docstatus = 1
            AND so.status = 'To Deliver and Bill'
            {salespersons_condition}
            {customer_filter_condition}
            {date_range_condition}
            GROUP BY so.name
        ) subquery
        GROUP BY order_name
        {sort_order_clause}
        {pagination_clause}
    """.format(
        salespersons_condition=salespersons_condition,
        customer_filter_condition=customer_filter_condition,
        date_range_condition=date_range_condition,
        sort_order_clause=sort_order_clause,
        pagination_clause=pagination_clause
    )


    bounce_order = frappe.db.sql(bounce_order_query, values, as_dict=True)
    
    # Creating a response
    synced_time = timeOfZone(datetime.now())
    return create_response(200, "Bounce Order fetched successfully", {
        "time": synced_time,
        "bounce_order_data": bounce_order
    })


#Bounce Order Details
@frappe.whitelist()
def get_bounce_order_details():
    order_filter = frappe.local.form_dict.get('order_name')

    values = {}

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    order_filter_condition = ""
    if order_filter:
        order_filter_condition = " AND so.name LIKE %(order_filter)s"
        values["order_filter"] = f"%{order_filter}%"

    # Fetch inactive customers with last sales order details
    bounce_order_details_query = """
        SELECT
        so.name,
        so.rounded_total as total_amount,
        so.status,
        so.transaction_date as invoice_date,
        so.delivery_date as due_date,
        so.customer,
        so.per_delivered,
        so.delivery_status,
        so.per_billed,
        so.billing_status

        FROM `tabSales Order` so
        JOIN `tabSales Team` cst ON cst.parent = so.customer
        WHERE so.docstatus = 1
        {salespersons_condition}
        {order_filter_condition}
        GROUP BY so.name
    """.format(
        salespersons_condition=salespersons_condition,
        order_filter_condition=order_filter_condition)
    
    bounce_order_details = frappe.db.sql(bounce_order_details_query, values, as_dict=True)
    
    # Fetch additional item details
    item_parent_names = [row.get('name') for row in bounce_order_details]
    bounce_order_details_items_query = """
        SELECT item_code, amount, qty
        FROM `tabSales Order Item`
        WHERE parent IN %(item_parent_names)s
    """
    bounce_order_details_items = frappe.db.sql(bounce_order_details_items_query, {"item_parent_names": item_parent_names}, as_dict=True)

    # Fetch additional Bounce Qty details
    qty_details_query = """
        SELECT
            item.item_code,
            SUM(item.qty) AS total_qty,
            SUM(item.delivered_qty) AS delivered_qty,
            SUM(item.qty - item.delivered_qty) AS bounce_qty
    
        FROM `tabSales Order` so
        JOIN `tabSales Team` cst ON cst.parent = so.customer
        LEFT JOIN `tabSales Order Item` item ON item.parent = so.name
        WHERE so.docstatus = 1
        AND so.status = 'To Deliver and Bill'
        {order_filter_condition}
        GROUP BY item.item_code
    """.format(
        order_filter_condition=order_filter_condition)
    
    qty_details_details = frappe.db.sql(qty_details_query, values, as_dict=True)

    # Creating a response
    synced_time = timeOfZone(datetime.now())
    return create_response(200, "Bounce Order Details fetched successfully", {
        "time": synced_time,
        "details_data": bounce_order_details,
        "items_details_data": bounce_order_details_items,
        "qty_details_data": qty_details_details
    })



# Top Customer
@frappe.whitelist()
def get_customer_wise_max_disc():
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
    
    customer_name = frappe.local.form_dict.get('customer_name', '')

    conditions = ""
    values = {}

    if from_date:
        conditions += " AND si.posting_date >= %(from_date)s"
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions += " AND si.posting_date <= %(to_date)s"
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if customer_name:
        conditions += " AND si.customer LIKE %(customer_name)s"
        values["customer_name"] = f"%{customer_name}%"

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get customer-wise total sales
    sql_query = f"""
        SELECT 
            si.customer, 

            SUM(ABS(item.discount_amount * item.qty)) AS discount_amount,
            ROUND(SUM(ABS(item.discount_amount * item.qty)) / SUM(ABS(item.price_list_rate * item.qty)) * 100, 2) AS discount_percentage
        FROM 
            `tabSales Invoice` si
        JOIN 
            `tabSales Team` cst ON cst.parent = si.name
        LEFT JOIN 
            `tabSales Invoice Item` item ON item.parent = si.name
        WHERE 
            si.docstatus = 1 
            AND si.status NOT IN ('Credit Note Issued', 'Return') 
            {conditions} 
            {salespersons_condition}
        GROUP BY 
            si.customer
    """

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY discount_amount DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY discount_amount ASC"
    elif sort_by == 'name_a_z':
        sql_query += " ORDER BY si.customer ASC"
    elif sort_by == 'name_z_a':
        sql_query += " ORDER BY si.customer DESC"

    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    # Executing the SQL query to get customer-wise sales data
    customer_data = frappe.db.sql(sql_query, values, as_dict=True)

    # Creating a response
    synced_time = timeOfZone(datetime.now())
    return create_response(200, "Customer Wise Disc fetched successfully", {
        "time": synced_time,
        "customer_data": customer_data
    })


#Item Wise Max Disc
@frappe.whitelist()
def get_item_wise_max_disc():
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')
    item_code = frappe.local.form_dict.get('item_code', '')

    conditions = ""
    values = {}

    if from_date:
        conditions += " AND si.posting_date >= %(from_date)s"
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions += " AND si.posting_date <= %(to_date)s"
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if item_code:
        conditions += " AND (item.item_code LIKE %(item_code)s OR item.item_name LIKE %(item_code)s)"
        values["item_code"] = f"%{item_code}%"

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get item-wise total sales
    sql_query = f"""
        SELECT 
            item.item_code, item.item_name,
            SUM(ABS(item.discount_amount * item.qty)) AS discount_amount,
            ROUND(SUM(ABS(item.discount_amount * item.qty)) / SUM(ABS(item.price_list_rate * item.qty))* 100, 2) AS discount_percentage
        FROM 
            `tabSales Invoice` si
        JOIN 
            `tabSales Team` cst ON cst.parent = si.name
        LEFT JOIN 
            `tabSales Invoice Item` item ON item.parent = si.name
        WHERE 
            si.docstatus = 1 
            AND si.status NOT IN ('Credit Note Issued', 'Return') 
            {conditions} 
            {salespersons_condition}
        GROUP BY 
            item.item_code
    """

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY discount_amount DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY discount_amount ASC"
    elif sort_by == 'name_a_z':
        sql_query += " ORDER BY item.item_code ASC"
    elif sort_by == 'name_z_a':
        sql_query += " ORDER BY item.item_code DESC"

    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    # Executing the SQL query to get item-wise sales data
    try:
        item_data = frappe.db.sql(sql_query, values, as_dict=True)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch item data")
        return create_response(500, "Internal Server Error")

    # Creating a response
    synced_time = timeOfZone(datetime.now())
    create_response(200, "Item Wise Disc fetched successfully", {
        "time": synced_time,
        "item_data": item_data
    })



#Item Wise Sales Report
@frappe.whitelist()
def get_item_wsie_sales():
    from_date = frappe.local.form_dict.get('from_date')
    to_date = frappe.local.form_dict.get('to_date')
    page = int(frappe.local.form_dict.get('page', 1))
    page_length = int(frappe.local.form_dict.get('page_length', 20))
    sort_by = frappe.local.form_dict.get('sort_by', '')

    item_code = frappe.local.form_dict.get('item_code', '')

    conditions = ""
    values = {}

    if from_date:
        conditions += " AND si.posting_date >= %(from_date)s"
        values["from_date"] = frappe.utils.data.getdate(from_date)

    if to_date:
        conditions += " AND si.posting_date <= %(to_date)s"
        values["to_date"] = frappe.utils.data.getdate(to_date)
    
    if item_code:
        conditions = " AND (item.item_code LIKE %(item_code)s OR item.item_name LIKE %(item_code)s)"
        values["item_code"] = f"%{item_code}%"

    # Retrieve the active user and associated employee
    active_user = frappe.session.user
    try:
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch employee or sales person")
        return create_response(500, "Internal Server Error")

    def get_salespersons(salesperson):
        try:
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Failed to fetch subordinates")
            return []

    salespersons_condition = ""
    if current_user:
        salespersons = get_salespersons(current_user)
        if not salespersons:
            return create_response(404, "No salespersons found")
        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

    # Calculate offset based on page number and page size
    offset = (page - 1) * page_length

    # Constructing the SQL query to get item-wise total sales
    sql_query = f"""
        SELECT 
            item.item_code, item.item_name, item.item_group, item.uom, itm.brand,
            SUM(item.amount) AS total_amount
        FROM 
            `tabSales Invoice` si
        JOIN 
            `tabSales Team` cst ON cst.parent = si.name
        LEFT JOIN 
            `tabSales Invoice Item` item ON item.parent = si.name
        JOIN 
            `tabItem` itm ON itm.name = item.item_code
        WHERE 
            si.docstatus = 1 
            AND si.status NOT IN ('Credit Note Issued', 'Return') 
            {conditions} 
            {salespersons_condition}
        GROUP BY 
            item.item_code
    """

    if sort_by == 'amount_high_low':
        sql_query += " ORDER BY total_amount DESC"
    elif sort_by == 'amount_low_high':
        sql_query += " ORDER BY total_amount ASC"
    elif sort_by == 'name_a_z':
        sql_query += " ORDER BY item.item_code ASC"
    elif sort_by == 'name_z_a':
        sql_query += " ORDER BY item.item_code DESC"

    sql_query += " LIMIT %(page_length)s OFFSET %(offset)s"

    values["page_length"] = page_length
    values["offset"] = offset

    # Executing the SQL query to get item-wise sales data
    item_data = frappe.db.sql(sql_query, values, as_dict=True)

    # Creating a response
    synced_time = timeOfZone(datetime.now())
    return create_response(200, "Item Wise Sales fetched successfully", {
        "time": synced_time,
        "item_data": item_data
    })


#Item Group and Brand Wise Sales Report
@frappe.whitelist()
def get_item_brand_group_wise_sales():
    try:
        # Retrieve parameters from the form data
        sort_by = frappe.local.form_dict.get('sort_by', '')
        brand = frappe.local.form_dict.get('brand', '')
        from_date = frappe.local.form_dict.get('from_date', '')
        to_date = frappe.local.form_dict.get('to_date', '')
        page_length = int(frappe.local.form_dict.get('page_length', 500))
        page = int(frappe.local.form_dict.get('page', 1))

        offset = (page - 1) * page_length

        # Retrieve the active user and associated employee
        active_user = frappe.session.user
        emp = frappe.db.get_value("Employee", {"user_id": active_user}, "name")
        current_user = frappe.db.get_value("Sales Person", {"employee": emp}, "name")

        if not current_user:
            return create_response(404, "No salespersons found for the current user")

        # Recursive function to get all subordinates
        def get_salespersons(salesperson):
            salespersons = [salesperson]
            subordinates = frappe.get_all('Sales Person', filters={'parent_sales_person': salesperson}, pluck='name')
            for subordinate in subordinates:
                salespersons.extend(get_salespersons(subordinate))
            return salespersons

        # Get list of all salespersons including subordinates
        salespersons = get_salespersons(current_user)

        # Construct SQL conditions and values
        conditions = []
        values = {}

        if brand:
            conditions.append("itm.brand = %(brand)s")
            values['brand'] = brand

        if from_date:
            conditions.append("si.posting_date >= %(from_date)s")
            values['from_date'] = from_date

        if to_date:
            conditions.append("si.posting_date <= %(to_date)s")
            values['to_date'] = to_date

        salespersons_condition = " AND cst.sales_person IN ({})".format(", ".join(["%({})s".format(sp) for sp in salespersons]))
        for sp in salespersons:
            values[sp] = sp

        conditions_str = " AND " + " AND ".join(conditions) if conditions else ""

        # Construct SQL query
        sql_query = f"""
            SELECT 
                itm.brand,
                itm.item_group,
                SUM(item.amount) AS total_amount
            FROM 
                `tabSales Invoice` si
            JOIN 
                `tabSales Team` cst ON cst.parent = si.name
            LEFT JOIN 
                `tabSales Invoice Item` item ON item.parent = si.name
            JOIN 
                `tabItem` itm ON itm.name = item.item_code
            WHERE 
                si.docstatus = 1 
                AND si.status NOT IN ('Credit Note Issued', 'Return')
                {conditions_str}
                {salespersons_condition}
            GROUP BY 
                itm.brand, itm.item_group
        """

        # Apply sorting based on the sort_by parameter
        if sort_by == 'amount_high_low':
            sql_query += " ORDER BY total_amount DESC"
        elif sort_by == 'amount_low_high':
            sql_query += " ORDER BY total_amount ASC"
        elif sort_by == 'name_a_z':
            sql_query += " ORDER BY itm.brand ASC"
        elif sort_by == 'name_z_a':
            sql_query += " ORDER BY itm.brand DESC"

        # Add pagination
        sql_query += f" LIMIT {page_length} OFFSET {offset}"

        # Execute SQL query
        brand_data = frappe.db.sql(sql_query, values, as_dict=True)

        # Format the response
        formatted_brand_data = {}
        brand_totals = {}
        for data in brand_data:
            brand_name = data['brand']
            item_group_name = data['item_group']
            total_amount = data['total_amount']

            if brand_name not in formatted_brand_data:
                formatted_brand_data[brand_name] = {}
                brand_totals[brand_name] = 0

            if item_group_name not in formatted_brand_data[brand_name]:
                formatted_brand_data[brand_name][item_group_name] = total_amount
            else:
                formatted_brand_data[brand_name][item_group_name] += total_amount

            brand_totals[brand_name] += total_amount

        # Add total amounts to the formatted brand data
        for brand_name in formatted_brand_data:
            formatted_brand_data[brand_name]['total'] = brand_totals[brand_name]

        # Create response
        synced_time = timeOfZone(datetime.now())
        create_response(200, "Brand Wise Sales fetched successfully", {
            "time": synced_time,
            "brand_data": formatted_brand_data
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to fetch brand-wise sales data")
        create_response(500, "Internal Server Error")

