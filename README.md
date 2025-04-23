# InvoiceMaker
**Invoice Generator Application:**

A desktop application for creating, managing, and tracking invoices with authentication, inventory management, and document generation.

**Features:**

User authentication and account management
Product/service inventory management
Invoice creation with customer details and line items
Tax calculation and automatic totals
Word document exports
Invoice search and history tracking
Modern UI with customtkinter

**Installation:**

Install required packages:

pip install customtkinter docxtpl pillow

Create a template Word document named pyinvoice.docx in the same directory
Run the application:

bashpython invoice_app.py

**Usage:**

* Register a new admin account or login
* Add products/services in the Items Management tab
* Create invoices in the New Invoice tab:
  1. Enter customer information
  2. Add line items (manually or from your inventory)
  3. Set tax rate if applicable
  4. Generate and save the invoice
* View past invoices in the Invoice History tab

**Requirements:**

Python 3.6+
sqlite3 (included with Python)
Word document template for invoice generation

**Troubleshooting:**

Ensure all dependencies are installed
Verify template file exists in correct location
Check directory permissions for database and generated files
