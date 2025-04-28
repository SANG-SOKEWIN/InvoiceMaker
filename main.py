import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from docxtpl import DocxTemplate
import datetime
import os
import json
from collections import deque
import re
from typing import List, Dict, Any
import customtkinter as ctk
from PIL import Image, ImageTk
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Queue for invoice history
invoice_history = deque(maxlen=10)

# Settings file path
SETTINGS_FILE = "invoice_settings.json"

def load_settings() -> Dict[str, Any]:
    """Load application settings from JSON file"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading settings: {e}")
    return {
        "theme": "dark",
        "template_path": "pyinvoice.docx",
        "default_tax_rate": 0.0,
        "company_name": "Your Company",
        "company_address": "123 Business St",
        "company_phone": "123-456-7890"
    }

def save_settings(settings: Dict[str, Any]) -> None:
    """Save application settings to JSON file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

def binary_search_invoices(invoices: List[Dict], target_name: str) -> List[Dict]:
    """Binary search implementation for finding invoices by customer name"""
    sorted_invoices = sorted(invoices, key=lambda x: x['name'].lower())
    left, right = 0, len(sorted_invoices) - 1
    results = []
    
    while left <= right:
        mid = (left + right) // 2
        current_name = sorted_invoices[mid]['name'].lower()
        
        if target_name.lower() in current_name:
            # Found a match, collect all matches
            results.append(sorted_invoices[mid])
            # Check left side
            i = mid - 1
            while i >= 0 and target_name.lower() in sorted_invoices[i]['name'].lower():
                results.append(sorted_invoices[i])
                i -= 1
            # Check right side
            i = mid + 1
            while i < len(sorted_invoices) and target_name.lower() in sorted_invoices[i]['name'].lower():
                results.append(sorted_invoices[i])
                i += 1
            break
        elif target_name.lower() < current_name:
            right = mid - 1
        else:
            left = mid + 1
    
    return results

def validate_phone(phone: str) -> bool:
    """Simple phone number validation"""
    # For now, accept any non-empty input
    return bool(phone.strip())

def validate_email(email: str) -> bool:
    """Simple email validation"""
    # For now, accept any non-empty input
    return bool(email.strip())

def apply_azure_theme(window):
    # Configure customtkinter appearance
    ctk.set_appearance_mode("dark")  # Set to dark mode for modern look
    ctk.set_default_color_theme("blue")  # Use blue theme
    
    # Configure ttk style for treeview
    style = ttk.Style(window)
    style.configure("Treeview",
                   background="#2b2b2b",
                   foreground="white",
                   rowheight=30,
                   fieldbackground="#2b2b2b",
                   borderwidth=0)
    style.configure("Treeview.Heading",
                   background="#1e1e1e",
                   foreground="white",
                   font=('Aptos Black', 10, 'bold'),
                   borderwidth=0)
    style.map('Treeview', 
              background=[('selected', '#0078D7')],
              foreground=[('selected', 'white')])
    
    # Configure alternating row colors
    style.map('Treeview',
              background=[('selected', '#0078D7'),
                         ('alternate', '#2b2b2b')],
              foreground=[('selected', 'white'),
                         ('!selected', 'white')])
    
    # Configure custom styles for better visual hierarchy
    style.configure("Custom.TFrame",
                   background="#1e1e1e")
    style.configure("Custom.TLabel",
                   background="#1e1e1e",
                   foreground="white",
                   font=('Aptos', 10))
    style.configure("Custom.TButton",
                   background="#0078D7",
                   foreground="white",
                   font=('Aptos', 10, 'bold'))

# --- Database Setup ---
def setup_database():
    """Setup database with proper error handling and security measures"""
    try:
        conn = sqlite3.connect("admin_accounts.db")
        cursor = conn.cursor()
        
        # Create admins table with additional security fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE,
                last_login TIMESTAMP,
                failed_attempts INTEGER DEFAULT 0,
                account_locked BOOLEAN DEFAULT 0
            )
        """)
        
        # Create items table for storing predefined items/services
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                unit_price REAL NOT NULL,
                category TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, created_by)
            )
        """)
        
        # Create invoices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                customer_phone TEXT,
                total_amount REAL NOT NULL,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT NOT NULL,
                status TEXT DEFAULT 'Draft'
            )
        """)
        
        # Add new columns for tax information if they don't exist
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN tax_rate REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN tax_amount REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN subtotal REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create invoice_items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                description TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices (id)
            )
        """)
        
        conn.commit()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Error setting up database: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

setup_database()

# --- Dynamic Form Switching ---
def load_login_form():
    clear_window(login_window)
    
    # Create main frame for login with gradient background
    login_frame = ctk.CTkFrame(login_window, fg_color="transparent")
    login_frame.pack(pady=50, padx=50, fill="both", expand=True)
    
    # Add logo or title at the top
    title_frame = ctk.CTkFrame(login_frame, fg_color="transparent")
    title_frame.pack(pady=(20, 30))
    
    ctk.CTkLabel(title_frame, 
                text="Invoice Generator", 
                font=('Aptos Black', 32),
                text_color="#0078D7").pack()
    ctk.CTkLabel(title_frame, 
                text="Admin Portal", 
                font=('Aptos', 16),
                text_color="#ffffff").pack(pady=5)
    
    # Create form container with modern styling
    form_container = ctk.CTkFrame(login_frame, 
                                fg_color="#2b2b2b",
                                corner_radius=15)
    form_container.pack(pady=20, padx=20, fill="x")
    
    # Add form elements with modern styling
    ctk.CTkLabel(form_container, 
                text="Username", 
                font=('Aptos', 14),
                text_color="#ffffff").pack(pady=(20, 5))
    
    global login_username_entry
    login_username_entry = ctk.CTkEntry(form_container, 
                                      width=300,
                                      height=40,
                                      font=('Aptos', 14),
                                      corner_radius=10,
                                      placeholder_text="Enter your username")
    login_username_entry.pack(pady=5)

    ctk.CTkLabel(form_container, 
                text="Password", 
                font=('Aptos', 14),
                text_color="#ffffff").pack(pady=(20, 5))
    
    global login_password_entry
    login_password_entry = ctk.CTkEntry(form_container, 
                                      show="*",
                                      width=300,
                                      height=40,
                                      font=('Aptos', 14),
                                      corner_radius=10,
                                      placeholder_text="Enter your password")
    login_password_entry.pack(pady=5)   

    # Add buttons with modern styling
    button_frame = ctk.CTkFrame(form_container, fg_color="transparent")
    button_frame.pack(pady=30)
    
    login_btn = ctk.CTkButton(button_frame, 
                            text="Login", 
                            font=('Aptos Black', 14),
                            command=login,
                            width=140,
                            height=40,
                            corner_radius=10,
                            fg_color="#0078D7",
                            hover_color="#005a9e")
    login_btn.pack(side="left", padx=10)
    
    register_btn = ctk.CTkButton(button_frame, 
                               text="Register", 
                               font=('Aptos Black', 14),
                               command=register,
                               width=140,
                               height=40,
                               corner_radius=10,
                               fg_color="#2b2b2b",
                               border_color="#0078D7",
                               border_width=2,
                               hover_color="#3b3b3b")
    register_btn.pack(side="left", padx=10)

def clear_window(window):
    for widget in window.winfo_children():
        widget.destroy()

# --- Registration Form ---
def register():
    def register_user():
        username = reg_username_entry.get().strip()
        password = reg_password_entry.get()
        confirm_password = reg_confirm_password_entry.get()
        
        if not username or not password or not confirm_password:
            messagebox.showerror("Error", "All fields are required.")
            return
            
        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match.")
            return

        try:
            conn = sqlite3.connect("admin_accounts.db")
            cursor = conn.cursor()
            
            # Check if username already exists
            cursor.execute("SELECT * FROM admins WHERE username = ?", (username,))
            if cursor.fetchone():
                messagebox.showerror("Error", "Username already exists.")
                return
                
            cursor.execute("""
                INSERT INTO admins (username, password, last_login)
                VALUES (?, ?, datetime('now'))
            """, (username, password))
            
            conn.commit()
            messagebox.showinfo("Success", "Registration successful! Please log in.")
            load_login_form()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error during registration: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()

    clear_window(login_window)
    
    # Create registration form with modern styling
    reg_frame = ctk.CTkFrame(login_window)
    reg_frame.pack(pady=50, padx=50, fill="both", expand=True)
    
    ctk.CTkLabel(reg_frame, 
                text="Register Admin", 
                font=('Aptos Black', 25)).pack(pady=(20, 30))
    
    # Username field
    ctk.CTkLabel(reg_frame, 
                text="Username", 
                font=('Aptos Black', 14)).pack()
    reg_username_entry = ctk.CTkEntry(reg_frame, 
                                    width=200, 
                                    font=('Aptos Black', 12))
    reg_username_entry.pack(pady=5)

    # Password field
    ctk.CTkLabel(reg_frame, 
                text="Password", 
                font=('Aptos Black', 14)).pack()
    reg_password_entry = ctk.CTkEntry(reg_frame, 
                                    show="*", 
                                    width=200, 
                                    font=('Aptos Black', 12))
    reg_password_entry.pack(pady=5)
    
    # Confirm Password field
    ctk.CTkLabel(reg_frame, 
                text="Confirm Password", 
                font=('Aptos Black', 14)).pack()
    reg_confirm_password_entry = ctk.CTkEntry(reg_frame, 
                                            show="*", 
                                            width=200, 
                                            font=('Aptos Black', 12))
    reg_confirm_password_entry.pack(pady=5)

    # Buttons
    ctk.CTkButton(reg_frame, 
                 text="Register", 
                 font=('Aptos Black', 12),
                 command=register_user, 
                 width=120, 
                 height=32).pack(pady=10)
    
    ctk.CTkButton(reg_frame, 
                 text="Back to Login", 
                 font=('Aptos Black', 12),
                 command=load_login_form, 
                 width=120, 
                 height=32).pack(pady=5)

# --- Login Verification ---
def login():
    """Enhanced login with security features"""
    username = login_username_entry.get().strip()
    password = login_password_entry.get()
    
    if not username or not password:
        messagebox.showerror("Error", "Username and password are required.")
        return
        
    try:
        conn = sqlite3.connect("admin_accounts.db")
        cursor = conn.cursor()
        
        # First check if the username exists
        cursor.execute("SELECT * FROM admins WHERE username = ?", (username,))
        account = cursor.fetchone()
        
        if not account:
            messagebox.showerror("Error", "Invalid username or password.")
            return
            
        # Check if account is locked
        if account[6]:  # account_locked field
            messagebox.showerror("Error", "Account is locked. Please contact administrator.")
            return
            
        # Now verify the password
        cursor.execute("""
            SELECT * FROM admins 
            WHERE username = ? AND password = ? AND account_locked = 0
        """, (username, password))
        
        login_successful = cursor.fetchone() is not None
        
        if login_successful:
            # Reset failed attempts and update last login
            cursor.execute("""
                UPDATE admins 
                SET failed_attempts = 0, last_login = datetime('now')
                WHERE username = ?
            """, (username,))
            conn.commit()
            
            global logged_in_admin
            logged_in_admin = username
            login_window.destroy()
            launch_main_app()
        else:
            # Increment failed attempts
            cursor.execute("""
                UPDATE admins 
                SET failed_attempts = failed_attempts + 1
                WHERE username = ?
            """, (username,))
            
            # Check if account should be locked
            cursor.execute("SELECT failed_attempts FROM admins WHERE username = ?", (username,))
            attempts = cursor.fetchone()[0]
            
            if attempts >= 3:
                cursor.execute("UPDATE admins SET account_locked = 1 WHERE username = ?", (username,))
                messagebox.showerror("Error", "Too many failed attempts. Account locked.")
            else:
                messagebox.showerror("Error", f"Invalid username or password. {3-attempts} attempts remaining.")
                
            conn.commit()
            
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Error during login: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

# --- Main Invoice Application ---
def launch_main_app():
    """Launch the main invoice application with enhanced features"""
    invoice_list = []
    
    # Create main window with modern styling
    main_window = ctk.CTk()
    main_window.state("zoomed")
    main_window.title("Invoice Generator")
    
    # Create main frame with modern styling
    main_frame = ctk.CTkFrame(main_window, fg_color="transparent")
    main_frame.pack(padx=20, pady=20, fill="both", expand=True)
    
    # Create header frame
    header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    header_frame.pack(fill="x", pady=(0, 20))
    
    # Add title and user info
    title_label = ctk.CTkLabel(header_frame,
                              text="Invoice Generator",
                              font=('Aptos Black', 24),
                              text_color="#0078D7")
    title_label.pack(side="left")
    
    user_label = ctk.CTkLabel(header_frame,
                             text=f"Welcome, {logged_in_admin}",
                             font=('Aptos', 14),
                             text_color="#ffffff")
    user_label.pack(side="right")
    
    # Create tabs with modern styling
    tabview = ctk.CTkTabview(main_frame,
                            fg_color="#2b2b2b",
                            border_color="#0078D7",
                            border_width=2,
                            corner_radius=15)
    tabview.pack(padx=20, pady=20, fill="both", expand=True)
    
    # Add tabs with custom styling
    new_invoice_tab = tabview.add("New Invoice")
    items_tab = tabview.add("Items Management")
    search_tab = tabview.add("Invoice History & Search")
    
    # Configure tab styling
    tabview.tab("New Invoice").grid_columnconfigure(0, weight=1)
    tabview.tab("Items Management").grid_columnconfigure(0, weight=1)
    tabview.tab("Invoice History & Search").grid_columnconfigure(0, weight=1)
    
    # Style the tab buttons
    tabview._segmented_button.configure(font=('Aptos Black', 14),
                                      selected_color="#0078D7",
                                      unselected_color="#2b2b2b",
                                      text_color=("white", "white"))
    
    def add_new_item():
        """Add a new item/service to the database"""
        try:
            name = new_item_name.get().strip()
            description = new_item_desc.get().strip()
            price = float(new_item_price.get().strip() or 0)
            category = new_item_category.get().strip()
            
            if not name:
                raise ValueError("Item name is required")
            if price < 0:
                raise ValueError("Price cannot be negative")
            
            conn = sqlite3.connect("admin_accounts.db")
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO items (name, description, unit_price, category, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (name, description, price, category, logged_in_admin))
            
            conn.commit()
            conn.close()
            
            # Clear fields
            new_item_name.delete(0, tk.END)
            new_item_desc.delete(0, tk.END)
            new_item_price.delete(0, tk.END)
            new_item_category.delete(0, tk.END)
            
            # Refresh items list
            load_items()
            messagebox.showinfo("Success", "Item added successfully!")
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "An item with this name already exists")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def load_items():
        """Load items from database into the treeview"""
        # Clear existing items
        for item in items_tree.get_children():
            items_tree.delete(item)
        
        try:
            conn = sqlite3.connect("admin_accounts.db")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, description, unit_price, category
                FROM items
                WHERE created_by = ?
                ORDER BY category, name
            """, (logged_in_admin,))
            
            for i, (name, description, price, category) in enumerate(cursor.fetchall()):
                items_tree.insert('', 'end', values=(name, description, f"${price:.2f}", category),
                                tags=('evenrow' if i % 2 == 0 else 'oddrow'))
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading items: {str(e)}")

    def delete_item():
        """Delete selected item from database"""
        selected = items_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an item to delete")
            return
            
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this item?"):
            try:
                conn = sqlite3.connect("admin_accounts.db")
                cursor = conn.cursor()
                
                item_name = items_tree.item(selected[0])['values'][0]
                cursor.execute("DELETE FROM items WHERE name = ? AND created_by = ?",
                             (item_name, logged_in_admin))
                
                conn.commit()
                conn.close()
                
                load_items()
                messagebox.showinfo("Success", "Item deleted successfully!")
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Error deleting item: {str(e)}")

    def add_item_to_invoice():
        """Add selected item from items list to current invoice"""
        selected = items_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an item to add")
            return
            
        item_values = items_tree.item(selected[0])['values']
        qty_spinbox.delete(0, tk.END)
        qty_spinbox.insert(0, "1")
        desc_entry.delete(0, tk.END)
        desc_entry.insert(0, item_values[0])  # Just use the item name without description
        price_spinbox.delete(0, tk.END)
        price_spinbox.insert(0, item_values[2].replace('$', ''))
        
        # Switch to invoice tab
        tabview.set("New Invoice")
        
    def clear_item():
        qty_spinbox.delete(0, tk.END)
        qty_spinbox.insert(0, "1")
        desc_entry.delete(0, tk.END)
        price_spinbox.delete(0, tk.END)
        price_spinbox.insert(0, "0.0")

    def add_item():
        try:
            qty = int(qty_spinbox.get())
            desc = desc_entry.get().strip()
            price = float(price_spinbox.get())
            
            if not desc:
                raise ValueError("Description cannot be empty")
            if qty <= 0:
                raise ValueError("Quantity must be greater than 0")
            if price < 0:
                raise ValueError("Price cannot be negative")
                
            line_total = round(qty * price, 2)
            invoice_item = [qty, desc, price, line_total]
            tree.insert('', 0, values=invoice_item)
            clear_item()
            invoice_list.append(invoice_item)
            
            # Update totals
            update_totals()
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))

    def update_totals():
        """Update subtotal, tax, and total amounts"""
        subtotal = sum(item[3] for item in invoice_list)
        tax_rate = float(tax_rate_entry.get() or 0) / 100
        tax = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax, 2)
    
        
        subtotal_label.configure(text=f"Subtotal: ${subtotal:.2f}")
        tax_label.configure(text=f"Tax: ${tax:.2f}")
        total_label.configure(text=f"Total: ${total:.2f}")

    def new_invoice():
        """Clear all fields and start a new invoice"""
        first_name_entry.delete(0, tk.END)
        last_name_entry.delete(0, tk.END)
        phone_entry.delete(0, tk.END)
        email_entry.delete(0, tk.END)
        tax_rate_entry.delete(0, tk.END)
        tax_rate_entry.insert(0, "0")
        clear_item()
        tree.delete(*tree.get_children())
        invoice_list.clear()
        update_totals()

    def update_invoice_display():
        """Update the invoice display with recent invoices and search results"""
        # Clear existing items
        for item in search_tree.get_children():
            search_tree.delete(item)
        
        try:
            conn = sqlite3.connect("admin_accounts.db")
            cursor = conn.cursor()
            search_term = search_entry.get().strip()
            
            if search_term:
                # If there's a search term, search in database
                cursor.execute("""
                    SELECT invoice_number, customer_name, date_created, total_amount
                    FROM invoices
                    WHERE customer_name LIKE ?
                    ORDER BY date_created DESC
                """, (f"%{search_term}%",))
                results_label.configure(text=f"Search Results for '{search_term}'")
            else:
                # If no search term, show recent invoices
                cursor.execute("""
                    SELECT invoice_number, customer_name, date_created, total_amount
                    FROM invoices
                    ORDER BY date_created DESC
                    LIMIT 10
                """)
                results_label.configure(text="Recent Invoices")
            
            results = cursor.fetchall()
            conn.close()
            
            # Display results with alternating colors
            for i, result in enumerate(results):
                formatted_result = list(result)
                formatted_result[3] = f"${result[3]:.2f}"  # Format total as currency
                
                if i % 2 == 0:
                    search_tree.insert('', 'end', values=formatted_result, tags=('evenrow',))
                else:
                    search_tree.insert('', 'end', values=formatted_result, tags=('oddrow',))
                    
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error retrieving invoices: {str(e)}")

    def clear_invoice_history():
        """Clear the invoice history display"""
        for item in search_tree.get_children():
            search_tree.delete(item)
        search_entry.delete(0, tk.END)
        results_label.configure(text="Recent Invoices")
        update_invoice_display()

    def search_invoices():
        """Trigger search and update display"""
        update_invoice_display()

    def generate_invoice():
        """Generate and save invoice with validation"""
        try:
            # Validate required fields
            first_name = first_name_entry.get().strip()
            last_name = last_name_entry.get().strip()
            phone = phone_entry.get().strip()
            email = email_entry.get().strip()
            
            if not first_name or not last_name:
                raise ValueError("First name and last name are required")
            if not phone and not email:
                raise ValueError("Either phone or email is required")
            if not invoice_list:
                raise ValueError("Invoice must have at least one item")
                
            # Generate invoice number
            invoice_number = f"INV-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Format customer name for filename (remove special characters)
            customer_name = f"{first_name}_{last_name}"
            customer_name = "".join(c for c in customer_name if c.isalnum() or c == '_')
            
            # Calculate totals
            subtotal = sum(item[3] for item in invoice_list)
            tax_rate = float(tax_rate_entry.get() or 0)
            tax_amount = round(subtotal * (tax_rate / 100), 2)
            total = round(subtotal + tax_amount, 2)
            
            # Save to database
            conn = sqlite3.connect("admin_accounts.db")
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_number, customer_name, customer_email, customer_phone,
                    total_amount, tax_rate, tax_amount, subtotal,
                    created_by, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice_number,
                f"{first_name} {last_name}",
                email,
                phone,
                total,
                tax_rate,
                tax_amount,
                subtotal,
                logged_in_admin,
                "Paid"
            ))
            
            invoice_id = cursor.lastrowid
            
            # Save invoice items
            for item in invoice_list:
                cursor.execute("""
                    INSERT INTO invoice_items (
                        invoice_id, description, quantity, unit_price, total_price
                    ) VALUES (?, ?, ?, ?, ?)
                """, (invoice_id, item[1], item[0], item[2], item[3]))
            
            conn.commit()
            conn.close()
            
            # Generate document
            doc = DocxTemplate("pyinvoice.docx")
            doc.render({
                "admin_name": logged_in_admin,
                "company_name": "Your Company",
                "company_address": "123 Business St",
                "company_phone": "123-456-7890",
                "invoice_number": invoice_number,
                "name": f"{first_name} {last_name}",
                "phone": phone,
                "email": email,
                "invoice_list": invoice_list,
                "subtotal": subtotal,
                "tax": tax_amount,
                "tax_rate": tax_rate,
                "total": total,
                "date": datetime.datetime.now().strftime("%Y-%m-%d")
            })
            
            # Save document with new naming format
            doc_name = f"INV_{invoice_number}_{customer_name}.docx"
            doc.save(doc_name)
            
            # Update display
            update_invoice_display()
            
            messagebox.showinfo("Success", f"Invoice {invoice_number} has been generated and saved as {doc_name}")
            new_invoice()
            
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def view_invoice_details(event):
        """Display invoice details in a new window when double-clicking an invoice"""
        try:
            # Get selected item
            selected_item = search_tree.selection()
            if not selected_item:
                return
                
            # Get invoice number from selected item
            invoice_number = search_tree.item(selected_item[0])['values'][0]
            
            # Connect to database
            conn = sqlite3.connect("admin_accounts.db")
            cursor = conn.cursor()
            
            # Get invoice details including tax information
            cursor.execute("""
                SELECT i.invoice_number, i.customer_name, i.customer_email, i.customer_phone,
                       i.date_created, i.total_amount, i.tax_rate, i.tax_amount, i.subtotal
                FROM invoices i
                WHERE i.invoice_number = ?
            """, (invoice_number,))
            
            invoice_data = cursor.fetchone()
            if not invoice_data:
                messagebox.showerror("Error", "Invoice not found")
                return
            
            # Get invoice items
            cursor.execute("""
                SELECT description, quantity, unit_price, total_price
                FROM invoice_items
                WHERE invoice_id = (SELECT id FROM invoices WHERE invoice_number = ?)
                ORDER BY id
            """, (invoice_number,))
            
            items = cursor.fetchall()
            conn.close()
            
            # Create new window for invoice details
            details_window = ctk.CTkToplevel()
            details_window.title(f"Invoice Details - {invoice_number}")
            details_window.geometry("800x600")
            
            # Main frame
            main_frame = ctk.CTkFrame(details_window)
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Header frame
            header_frame = ctk.CTkFrame(main_frame)
            header_frame.pack(fill="x", padx=10, pady=10)
            
            # Invoice details
            ctk.CTkLabel(header_frame, text=f"Invoice Number: {invoice_data[0]}", 
                        font=('Aptos Black', 16)).pack(pady=5)
            ctk.CTkLabel(header_frame, text=f"Customer: {invoice_data[1]}", 
                        font=('Aptos Black', 14)).pack(pady=2)
            ctk.CTkLabel(header_frame, text=f"Email: {invoice_data[2]}", 
                        font=('Aptos Black', 14)).pack(pady=2)
            ctk.CTkLabel(header_frame, text=f"Phone: {invoice_data[3]}", 
                        font=('Aptos Black', 14)).pack(pady=2)
            ctk.CTkLabel(header_frame, text=f"Date: {invoice_data[4]}", 
                        font=('Aptos Black', 14)).pack(pady=2)
            
            # Items frame
            items_frame = ctk.CTkFrame(main_frame)
            items_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create treeview for items
            columns = ('description', 'quantity', 'price', 'total')
            items_tree = ttk.Treeview(items_frame, columns=columns, show="headings", height=10)
            
            # Configure columns
            items_tree.heading('description', text='Description', anchor='w')
            items_tree.heading('quantity', text='Quantity', anchor='center')
            items_tree.heading('price', text='Unit Price', anchor='e')
            items_tree.heading('total', text='Total', anchor='e')
            
            items_tree.column('description', width=400, anchor='w')
            items_tree.column('quantity', width=100, anchor='center')
            items_tree.column('price', width=150, anchor='e')
            items_tree.column('total', width=150, anchor='e')
            
            # Add scrollbars
            v_scrollbar = ttk.Scrollbar(items_frame, orient="vertical", command=items_tree.yview)
            h_scrollbar = ttk.Scrollbar(items_frame, orient="horizontal", command=items_tree.xview)
            items_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # Pack tree and scrollbars
            items_tree.pack(side="left", fill="both", expand=True)
            v_scrollbar.pack(side="right", fill="y")
            h_scrollbar.pack(side="bottom", fill="x")
            
            # Add items to treeview
            for item in items:
                items_tree.insert('', 'end', values=(
                    item[0],  # description
                    item[1],  # quantity
                    f"${item[2]:.2f}",  # unit price
                    f"${item[3]:.2f}"   # total
                ))
            
            # Totals Frame with tax information
            totals_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            totals_frame.pack(fill="x", pady=10, padx=10)
            
            # Add tax information and totals
            subtotal = invoice_data[8] if invoice_data[8] is not None else 0
            tax_rate = invoice_data[6] if invoice_data[6] is not None else 0
            tax_amount = invoice_data[7] if invoice_data[7] is not None else 0
            total = invoice_data[5] if invoice_data[5] is not None else 0
            
            ctk.CTkLabel(totals_frame, 
                        text=f"Subtotal: ${subtotal:.2f}",
                        font=('Aptos', 14),
                        text_color="#ffffff").pack(side="left", padx=10)
            
            ctk.CTkLabel(totals_frame, 
                        text=f"Tax Rate: {tax_rate}%",
                        font=('Aptos', 14),
                        text_color="#ffffff").pack(side="left", padx=10)
            
            ctk.CTkLabel(totals_frame, 
                        text=f"Tax Amount: ${tax_amount:.2f}",
                        font=('Aptos', 14),
                        text_color="#ffffff").pack(side="left", padx=10)
            
            ctk.CTkLabel(totals_frame, 
                        text=f"Total: ${total:.2f}",
                        font=('Aptos Black', 16),
                        text_color="#0078D7").pack(side="left", padx=10)
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error viewing invoice: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    # New Invoice Form
    customer_frame = ctk.CTkFrame(new_invoice_tab,
                                fg_color="#2b2b2b",
                                corner_radius=15)
    customer_frame.pack(padx=20, pady=20, fill="x")
    
    # Customer Information Header
    ctk.CTkLabel(customer_frame, 
                text="Customer Information", 
                font=('Aptos Black', 18),
                text_color="#0078D7").pack(pady=(20, 10))
    
    # Create a grid for customer information
    info_grid = ctk.CTkFrame(customer_frame, fg_color="transparent")
    info_grid.pack(padx=20, pady=10, fill="x")
    
    # First Name
    ctk.CTkLabel(info_grid, 
                text="First Name", 
                font=('Aptos', 12),
                text_color="#ffffff").grid(row=0, column=0, padx=10, pady=5, sticky="w")
    first_name_entry = ctk.CTkEntry(info_grid,
                                   width=200,
                                   height=35,
                                   font=('Aptos', 12),
                                   corner_radius=8)
    first_name_entry.grid(row=1, column=0, padx=10, pady=5)
    
    # Last Name
    ctk.CTkLabel(info_grid, 
                text="Last Name", 
                font=('Aptos', 12),
                text_color="#ffffff").grid(row=0, column=1, padx=10, pady=5, sticky="w")
    last_name_entry = ctk.CTkEntry(info_grid,
                                  width=200,
                                  height=35,
                                  font=('Aptos', 12),
                                  corner_radius=8)
    last_name_entry.grid(row=1, column=1, padx=10, pady=5)
    
    # Phone
    ctk.CTkLabel(info_grid, 
                text="Phone", 
                font=('Aptos', 12),
                text_color="#ffffff").grid(row=2, column=0, padx=10, pady=5, sticky="w")
    phone_entry = ctk.CTkEntry(info_grid,
                              width=200,
                              height=35,
                              font=('Aptos', 12),
                              corner_radius=8)
    phone_entry.grid(row=3, column=0, padx=10, pady=5)

    # Add phone number validation
    def validate_phone_input(event=None):
        value = phone_entry.get()
        # Remove any non-digit characters
        new_value = ''.join(filter(str.isdigit, value))
        # If the value changed (had non-digits), update the entry
        if new_value != value:
            phone_entry.delete(0, tk.END)
            phone_entry.insert(0, new_value)
    
    # Bind validation to key events
    phone_entry.bind('<KeyRelease>', validate_phone_input)
    
    # Email
    ctk.CTkLabel(info_grid, 
                text="Email", 
                font=('Aptos', 12),
                text_color="#ffffff").grid(row=2, column=1, padx=10, pady=5, sticky="w")
    email_entry = ctk.CTkEntry(info_grid,
                              width=200,
                              height=35,
                              font=('Aptos', 12),
                              corner_radius=8)
    email_entry.grid(row=3, column=1, padx=10, pady=5)
    
    # Tax Rate
    ctk.CTkLabel(info_grid, 
                text="Tax Rate (%)", 
                font=('Aptos', 12),
                text_color="#ffffff").grid(row=4, column=0, padx=10, pady=5, sticky="w")
    tax_rate_entry = ctk.CTkEntry(info_grid,
                                 width=200,
                                 height=35,
                                 font=('Aptos', 12),
                                 corner_radius=8)
    tax_rate_entry.insert(0, "0")
    tax_rate_entry.grid(row=5, column=0, padx=10, pady=5)
    
    # Create a container frame for items
    items_container = ctk.CTkFrame(new_invoice_tab)
    items_container.pack(padx=20, pady=20, fill="both", expand=True)
    
    # Items Frame
    items_frame = ctk.CTkFrame(items_container)
    items_frame.pack(padx=0, pady=(0, 10), fill="both", expand=True)
    
    ctk.CTkLabel(items_frame, text="Invoice Items", font=('Aptos Black', 16)).pack(pady=10)
    
    # Item Entry Fields
    entry_frame = ctk.CTkFrame(items_frame)
    entry_frame.pack(fill="x", pady=10)
    
    # Quantity
    ctk.CTkLabel(entry_frame, text="Qty").pack(side="left", padx=5)
    qty_spinbox = ctk.CTkEntry(entry_frame, width=50)
    qty_spinbox.insert(0, "1")
    qty_spinbox.pack(side="left", padx=5)
    
    # Description
    ctk.CTkLabel(entry_frame, text="Description").pack(side="left", padx=5)
    desc_entry = ctk.CTkEntry(entry_frame)
    desc_entry.pack(side="left", fill="x", expand=True, padx=5)
    
    # Price
    ctk.CTkLabel(entry_frame, text="Price").pack(side="left", padx=5)
    price_spinbox = ctk.CTkEntry(entry_frame, width=100)
    price_spinbox.insert(0, "0.0")
    price_spinbox.pack(side="left", padx=5)
    
    # Add Item Button
    add_item_btn = ctk.CTkButton(entry_frame, text="Add Item", command=add_item)
    add_item_btn.pack(side="left", padx=5)
    
    # Clear Button
    clear_btn = ctk.CTkButton(entry_frame, text="Clear", command=clear_item)
    clear_btn.pack(side="left", padx=5)
    
    # Create Treeview for items
    tree_frame = ctk.CTkFrame(items_frame)
    tree_frame.pack(fill="both", expand=True, pady=10)
    
    columns = ('qty', 'desc', 'price', 'total')
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
    
    # Configure columns
    tree.heading('qty', text='Quantity')
    tree.heading('desc', text='Description')
    tree.heading('price', text='Unit Price')
    tree.heading('total', text='Total')
    
    tree.column('qty', width=100)
    tree.column('desc', width=400)
    tree.column('price', width=150)
    tree.column('total', width=150)
    
    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Pack the treeview and scrollbars
    tree.pack(side="left", fill="both", expand=True)
    v_scrollbar.pack(side="right", fill="y")
    h_scrollbar.pack(side="bottom", fill="x")
    
    # Totals Frame
    totals_frame = ctk.CTkFrame(items_frame, fg_color="transparent")
    totals_frame.pack(fill="x", pady=10)
    
    subtotal_label = ctk.CTkLabel(totals_frame, 
                                 text="Subtotal: $0.00",
                                 font=('Aptos', 14),
                                 text_color="#ffffff")
    subtotal_label.pack(side="left", padx=10)
    
    tax_label = ctk.CTkLabel(totals_frame, 
                            text="Tax: $0.00",
                            font=('Aptos', 14),
                            text_color="#ffffff")
    tax_label.pack(side="left", padx=10)
    
    total_label = ctk.CTkLabel(totals_frame, 
                              text="Total: $0.00",
                              font=('Aptos Black', 16),
                              text_color="#0078D7")
    total_label.pack(side="left", padx=10)
    
    # Add Generate Invoice Button directly in the items_frame
    generate_invoice_btn = ctk.CTkButton(
        items_frame,
        text="Generate Invoice",
        command=generate_invoice,
        width=120,  # Match other button widths
        height=32,  # Match other button heights
        font=('Aptos Black', 12),  # Match other button fonts
        corner_radius=8,  # Match other button corner radius
        fg_color="#0078D7",
        hover_color="#005a9e"
    )
    generate_invoice_btn.pack(pady=10, padx=20, anchor="w")  # Anchor west (left) and add padding

    def on_enter(e):
        generate_invoice_btn.configure(fg_color="#005a9e")
    
    def on_leave(e):
        generate_invoice_btn.configure(fg_color="#0078D7")
    
    generate_invoice_btn.bind("<Enter>", on_enter)
    generate_invoice_btn.bind("<Leave>", on_leave)
    
    # Search and History Tab
    search_frame = ctk.CTkFrame(search_tab,
                               fg_color="#2b2b2b",
                               corner_radius=15)
    search_frame.pack(padx=20, pady=20, fill="both", expand=True)
    
    # Search Section with modern styling
    search_section = ctk.CTkFrame(search_frame, fg_color="transparent")
    search_section.pack(fill="x", padx=20, pady=(20, 10))
    
    # Search Entry and Button in same row with modern styling
    ctk.CTkLabel(search_section, 
                text="Search Invoices", 
                font=('Aptos Black', 16),
                text_color="#0078D7").pack(side="left", padx=(0, 10))
    
    search_entry = ctk.CTkEntry(search_section, 
                               placeholder_text="Search by customer name",
                               width=300,
                               height=35,
                               font=('Aptos', 12),
                               corner_radius=8)
    search_entry.pack(side="left", padx=10)
    search_entry.bind('<Return>', lambda event: search_invoices())
    
    # Search Button with modern styling
    search_btn = ctk.CTkButton(search_section, 
                              text="Search", 
                              font=('Aptos Black', 12),
                              command=search_invoices,
                              width=100,
                              height=35,
                              corner_radius=8,
                              fg_color="#0078D7",
                              hover_color="#005a9e")
    search_btn.pack(side="left", padx=10)
    
    # Clear History Button with modern styling
    clear_history_btn = ctk.CTkButton(search_section, 
                                     text="Clear History", 
                                     font=('Aptos Black', 12),
                                     command=clear_invoice_history,
                                     width=120,
                                     height=35,
                                     corner_radius=8,
                                     fg_color="#dc3545",
                                     hover_color="#c82333")
    clear_history_btn.pack(side="right", padx=10)
    
    # Results Section with modern styling
    results_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
    results_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
    # Results Label with modern styling
    results_label = ctk.CTkLabel(results_frame, 
                               text="Recent Invoices", 
                               font=('Aptos Black', 16),
                               text_color="#0078D7")
    results_label.pack(pady=(0, 10))
    
    # Treeview for results with modern styling
    tree_frame = ctk.CTkFrame(results_frame,
                             fg_color="#2b2b2b",
                             corner_radius=15)
    tree_frame.pack(fill="both", expand=True)
    
    search_tree = ttk.Treeview(tree_frame, 
                              columns=('number', 'customer', 'date', 'total'), 
                              show="headings", 
                              style="Custom.Treeview")
    
    # Configure column headings and widths with modern styling
    search_tree.heading('number', text='Invoice Number', anchor='center')
    search_tree.heading('customer', text='Customer', anchor='center')
    search_tree.heading('date', text='Date', anchor='center')
    search_tree.heading('total', text='Total ($)', anchor='e')
    
    search_tree.column('number', width=200, anchor='center', stretch=False)
    search_tree.column('customer', width=400, anchor='center', stretch=True)
    search_tree.column('date', width=200, anchor='center', stretch=False)
    search_tree.column('total', width=150, anchor='e', stretch=False)
    
    # Add scrollbars with modern styling
    v_scrollbar = ttk.Scrollbar(tree_frame, 
                               orient="vertical", 
                               command=search_tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, 
                               orient="horizontal", 
                               command=search_tree.xview)
    search_tree.configure(yscrollcommand=v_scrollbar.set, 
                         xscrollcommand=h_scrollbar.set)
    
    # Pack the treeview and scrollbars
    search_tree.pack(side="left", fill="both", expand=True)
    v_scrollbar.pack(side="right", fill="y")
    h_scrollbar.pack(side="bottom", fill="x")
    
    # Configure row colors for better visibility
    search_tree.tag_configure('oddrow', background='#2b2b2b', foreground='white')
    search_tree.tag_configure('evenrow', background='#1e1e1e', foreground='white')

    # Bind double-click event to search tree
    search_tree.bind('<Double-1>', view_invoice_details)

    # Items Management Tab
    items_frame = ctk.CTkFrame(items_tab,
                              fg_color="#2b2b2b",
                              corner_radius=15)
    items_frame.pack(padx=20, pady=20, fill="both", expand=True)
    
    # New Item Form Header
    ctk.CTkLabel(items_frame, 
                text="Add New Item/Service", 
                font=('Aptos Black', 18),
                text_color="#0078D7").pack(pady=(20, 10))
    
    # Create a more compact form layout
    form_frame = ctk.CTkFrame(items_frame, fg_color="transparent")
    form_frame.pack(fill="x", padx=20, pady=5)
    
    # Create two columns for the form
    left_form = ctk.CTkFrame(form_frame, fg_color="transparent")
    left_form.pack(side="left", fill="x", expand=True, padx=(0,10))
    right_form = ctk.CTkFrame(form_frame, fg_color="transparent")
    right_form.pack(side="left", fill="x", expand=True, padx=(10,0))
    
    # Left column - Name and Price
    name_frame = ctk.CTkFrame(left_form, fg_color="transparent")
    name_frame.pack(fill="x", pady=2)
    ctk.CTkLabel(name_frame, 
                text="Name:", 
                font=('Aptos', 12),
                text_color="#ffffff",
                width=60).pack(side="left", padx=5)
    new_item_name = ctk.CTkEntry(name_frame, 
                                height=35,
                                font=('Aptos', 12),
                                corner_radius=8)
    new_item_name.pack(side="left", fill="x", expand=True, padx=5)
    
    price_frame = ctk.CTkFrame(left_form, fg_color="transparent")
    price_frame.pack(fill="x", pady=2)
    ctk.CTkLabel(price_frame, 
                text="Price:", 
                font=('Aptos', 12),
                text_color="#ffffff",
                width=60).pack(side="left", padx=5)
    new_item_price = ctk.CTkEntry(price_frame, 
                                 height=35,
                                 font=('Aptos', 12),
                                 corner_radius=8)
    new_item_price.pack(side="left", fill="x", expand=True, padx=5)
    
    # Right column - Description and Category
    desc_frame = ctk.CTkFrame(right_form, fg_color="transparent")
    desc_frame.pack(fill="x", pady=2)
    ctk.CTkLabel(desc_frame, 
                text="Desc:", 
                font=('Aptos', 12),
                text_color="#ffffff",
                width=60).pack(side="left", padx=5)
    new_item_desc = ctk.CTkEntry(desc_frame, 
                                height=35,
                                font=('Aptos', 12),
                                corner_radius=8)
    new_item_desc.pack(side="left", fill="x", expand=True, padx=5)
    
    category_frame = ctk.CTkFrame(right_form, fg_color="transparent")
    category_frame.pack(fill="x", pady=2)
    ctk.CTkLabel(category_frame, 
                text="Category:", 
                font=('Aptos', 12),
                text_color="#ffffff",
                width=60).pack(side="left", padx=5)
    new_item_category = ctk.CTkEntry(category_frame, 
                                    height=35,
                                    font=('Aptos', 12),
                                    corner_radius=8)
    new_item_category.pack(side="left", fill="x", expand=True, padx=5)
    
    # Add Button with modern styling
    button_frame = ctk.CTkFrame(items_frame, fg_color="transparent")
    button_frame.pack(fill="x", padx=20, pady=10)
    
    # Add Item Button
    add_item_button = ctk.CTkButton(button_frame, 
                                   text="Add Item", 
                                   font=('Aptos Black', 14),
                                   command=add_new_item,
                                   width=150,
                                   height=40,
                                   corner_radius=10,
                                   fg_color="#0078D7",
                                   hover_color="#005a9e")
    add_item_button.pack(side="left", padx=5)
    
    # Add to Invoice Button
    add_to_invoice_btn = ctk.CTkButton(button_frame, 
                                      text="Add to Invoice", 
                                      font=('Aptos Black', 14),
                                      command=add_item_to_invoice,
                                      width=150,
                                      height=40,
                                      corner_radius=10,
                                      fg_color="#0078D7",
                                      hover_color="#005a9e")
    add_to_invoice_btn.pack(side="left", padx=5)
    
    # Delete Item Button
    delete_item_btn = ctk.CTkButton(button_frame, 
                                   text="Delete Item", 
                                   font=('Aptos Black', 14),
                                   command=delete_item,
                                   width=150,
                                   height=40,
                                   corner_radius=10,
                                   fg_color="#dc3545",
                                   hover_color="#c82333")
    delete_item_btn.pack(side="left", padx=5)
    
    # Add hover effects
    def on_enter_add_item(e):
        add_item_button.configure(fg_color="#005a9e")
    
    def on_leave_add_item(e):
        add_item_button.configure(fg_color="#0078D7")
    
    def on_enter_add_to_invoice(e):
        add_to_invoice_btn.configure(fg_color="#005a9e")
    
    def on_leave_add_to_invoice(e):
        add_to_invoice_btn.configure(fg_color="#0078D7")
    
    def on_enter_delete(e):
        delete_item_btn.configure(fg_color="#c82333")
    
    def on_leave_delete(e):
        delete_item_btn.configure(fg_color="#dc3545")
    
    add_item_button.bind("<Enter>", on_enter_add_item)
    add_item_button.bind("<Leave>", on_leave_add_item)
    add_to_invoice_btn.bind("<Enter>", on_enter_add_to_invoice)
    add_to_invoice_btn.bind("<Leave>", on_leave_add_to_invoice)
    delete_item_btn.bind("<Enter>", on_enter_delete)
    delete_item_btn.bind("<Leave>", on_leave_delete)
    
    # Items List with modern styling
    list_frame = ctk.CTkFrame(items_frame,
                             fg_color="#2b2b2b",
                             corner_radius=15)
    list_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
    # Create Treeview with modern styling
    items_tree = ttk.Treeview(list_frame, 
                             columns=('name', 'description', 'price', 'category'),
                             show="headings", 
                             style="Treeview")
    
    # Configure alternating row colors for items tree
    items_tree.tag_configure('oddrow', background='#2b2b2b', foreground='white')
    items_tree.tag_configure('evenrow', background='#1e1e1e', foreground='white')
    
    # Configure columns with modern styling
    items_tree.heading('name', text='Name', anchor='w')
    items_tree.heading('description', text='Description', anchor='w')
    items_tree.heading('price', text='Price', anchor='e')
    items_tree.heading('category', text='Category', anchor='e')
    
    items_tree.column('name', width=200, anchor='w')
    items_tree.column('description', width=400, anchor='w')
    items_tree.column('price', width=100, anchor='e')
    items_tree.column('category', width=150, anchor='e')
    
    # Add scrollbars with modern styling
    v_scrollbar = ttk.Scrollbar(list_frame, 
                               orient="vertical", 
                               command=items_tree.yview)
    h_scrollbar = ttk.Scrollbar(list_frame, 
                               orient="horizontal", 
                               command=items_tree.xview)
    items_tree.configure(yscrollcommand=v_scrollbar.set, 
                        xscrollcommand=h_scrollbar.set)
    
    # Pack the treeview and scrollbars
    items_tree.pack(side="left", fill="both", expand=True)
    v_scrollbar.pack(side="right", fill="y")
    h_scrollbar.pack(side="bottom", fill="x")
    
    # Load existing items
    load_items()

    # Initialize the invoice display
    update_invoice_display()

    main_window.mainloop()

# --- Login UI ---
logged_in_admin = None  # Variable to store the logged-in admin's username
login_window = ctk.CTk()
login_window.state('zoomed')
login_window.title("Admin Login")
apply_azure_theme(login_window)
load_login_form()
login_window.mainloop()


