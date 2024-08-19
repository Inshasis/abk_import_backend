## Sales Application Plugin

Sales Application backend developed and managed in Frappe ERPNext.

## Must Have Configurations

- Check-in/out functionality.
    - `Address` doctype must have geolocation details data.

- Customer Data visibility to sales persons.
    - `Customer` doctype must have atleast one sales person in sales team child table.

- Sales Person Mapping.
    - `Sales Person` doctype must be linked with `Employee` and that `Employee` is further linked with `User`.
    
- Items Visibility
    - `Item` must have price details mapped to `Item Price`.

- Creation of User 
    - After creating a new user, generate API access key pair and set following permissions.
        - Customer
        - Employee
        - Sales Manager
        - Sales User
        - Sales Person

#### License

MIT 