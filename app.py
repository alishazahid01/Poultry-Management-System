import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from database import PoultryDatabase
import sqlite3
from dotenv import load_dotenv
load_dotenv()

# Initialize database
db = PoultryDatabase()

# Create default admin user if no users exist
def create_default_admin():
    try:
        conn = sqlite3.connect(os.path.join("secure", "poultry_management.db"))
        cursor = conn.cursor()
        
        # Wait until the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]

            if user_count == 0 and st.secrets["DEFAULT_ADMIN_PASS"]:
                db.add_user("admin", st.secrets["DEFAULT_ADMIN_PASS"], "admin")

        conn.close()
    except Exception as e:
        print("Admin creation failed:", e)


create_default_admin()

# Function to format currency values
def format_currency(value):
    """Format a number as Indian Rupees."""
    return f"PKR {value:,.2f}"

# Set page configuration
st.set_page_config(
    page_title="Haji Poultry Management",
    page_icon="🐔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject full modern CSS theme
st.markdown("""
<style>
    :root {
        --primary-bg: #0f172a;
        --secondary-bg: #1e293b;
        --accent-color: #3b82f6;
        --accent-hover: #2563eb;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --error-color: #ef4444;
        --success-color: #22c55e;
    }
    body {
        background-color: var(--primary-bg);
        color: var(--text-primary);
        font-family: 'Inter', sans-serif;
    }
    .login-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        padding: 1rem;
        background: linear-gradient(135deg, var(--primary-bg) 0%, var(--secondary-bg) 100%);
    }
    .login-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 2.5rem;
        width: 100%;
        max-width: 420px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    }
    .login-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    .login-header h1 {
        font-size: 2rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
    }
    .login-header p {
        color: var(--text-secondary);
        font-size: 1rem;
    }
    .stTextInput > div > div > input {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        font-size: 1rem !important;
        padding: 0.75rem 1rem !important;
        transition: all 0.2s ease !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: var(--accent-color) !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
    }
    .stTextInput > div > div > input::placeholder {
        color: var(--text-secondary) !important;
    }
    .stButton > button {
        background: var(--accent-color) !important;
        border: none !important;
        border-radius: 8px !important;
        color: white !important;
        font-size: 1rem !important;
        font-weight: 500 !important;
        padding: 0.75rem !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        background: var(--accent-hover) !important;
        transform: translateY(-1px);
    }
    .stAlert {
        background-color: rgba(239, 68, 68, 0.1) !important;
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
        border-radius: 8px !important;
        color: var(--error-color) !important;
        padding: 1rem !important;
    }
    header[data-testid="stHeader"], footer, .stDeployButton, 
    .brand-logo {
        width: 80px;
        height: 80px;
        margin-bottom: 1.5rem;
    }
    .login-decoration {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: -1;
        opacity: 0.5;
        background:
            radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
            radial-gradient(circle at 100% 100%, rgba(59, 130, 246, 0.1) 0%, transparent 50%);
    }
</style>
""", unsafe_allow_html=True)

def get_navigation_options(user_role):
    """Get navigation options based on user role."""
    if user_role == "admin":
        # Admin gets full access to all features
        return [
            "📊 Main Dashboard", 
            "👥 Farmers", 
            "🛒 Buy Chicken", 
            "💰 Sell Chicken", 
            "💵 Money Management",
            "👤 User Management"
        ]
    else:
        # Regular users only get access to money management
        return ["💵 Money Management"]

def login_page():
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown("""
        <div class="login-header">
            <h1>🐔 Haji Poultry</h1>
            <p>Welcome back! Please login to continue.</p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login = st.form_submit_button("Login")

    if login:
        user = db.authenticate_user(username, password)
        if user:
            st.session_state.user = user
            st.session_state.is_admin = user["role"] == "admin"
            st.session_state.username = username
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.markdown('</div>', unsafe_allow_html=True)

def user_management_page():
    st.markdown('<h2 class="sub-header">User Management</h2>', unsafe_allow_html=True)
    
    # Tabs for Add User and View Users
    tab1, tab2 = st.tabs(["➕ Add New User", "👁️ View All Users"])
    
    # Add User tab
    with tab1:
        with st.form("add_user_form", clear_on_submit=True):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["admin", "user"])
            submit = st.form_submit_button("Add User")
            
            if submit:
                if username and password:
                    user_id = db.add_user(username, password, role)
                    if user_id:
                        st.success(f"User '{username}' added successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to add user. Please try again.")
                else:
                    st.error("Username and password are required!")
    
    # List all users
    with tab2:
        st.subheader("All Users")
        users = db.get_all_users()
        
        if users:
            # Convert to DataFrame for better display
            users_df = pd.DataFrame(users, columns=['ID', 'Username', 'Role', 'Created At'])
            
            # Display each user with delete button
            for _, user in users_df.iterrows():
                with st.expander(f"👤 {user['Username']} ({user['Role']})"):
                    st.write(f"User ID: {user['ID']}")
                    st.write(f"Created: {user['Created At']}")
                    
                    # Don't show delete button for the current user or other admins
                    if (user['ID'] != st.session_state.user["user_id"] and 
                        (user['Role'] != 'admin' or st.session_state.user["role"] == 'admin')):
                        if st.button("🗑️ Delete User", key=f"delete_user_{user['ID']}"):
                            if db.delete_user(user['ID'], st.session_state.user["user_id"]):
                                st.success(f"User '{user['Username']}' deleted successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to delete user. Cannot delete admin users.")
        else:
            st.info("No users found.")

def show_dashboard():
    st.markdown('<h2 class="sub-header">Main Dashboard</h2>', unsafe_allow_html=True)
    
    # Simple description
    st.markdown("""
    <div class="instruction-text">
    Welcome to your Poultry Business Dashboard! Here you can see how your business is doing at a glance.
    </div>
    """, unsafe_allow_html=True)
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Show data from", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("Show data until", datetime.now())
    
    # Convert dates to string format
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Get transactions data
    purchases = db.get_poultry_transactions(start_date_str, end_date_str, transaction_type='buy')
    sales = db.get_poultry_transactions(start_date_str, end_date_str, transaction_type='sell')

    # Map farmer_id to name for purchases and sales
    farmers = db.get_farmers()
    farmer_map = {row['farmer_id']: row['name'] for _, row in farmers.iterrows()}
    if not purchases.empty:
        purchases['name'] = purchases['farmer_id'].map(farmer_map).fillna("Unknown")
    if not sales.empty:
        sales['name'] = sales['farmer_id'].map(farmer_map).fillna("Unknown")

    
    
    # Calculate financial metrics
    total_purchase_amount = purchases['total_amount'].sum() if not purchases.empty else 0
    total_sales_amount = sales['total_amount'].sum() if not sales.empty else 0
    
    total_paid = purchases['payment_amount'].sum() if not purchases.empty else 0
    total_received = sales['payment_amount'].sum() if not sales.empty else 0
    
    pending_to_pay = total_purchase_amount - total_paid
    pending_to_receive = total_sales_amount - total_received
    
    actual_profit_loss = total_received - total_paid
    potential_profit_loss = total_sales_amount - total_purchase_amount
    
    # Get inventory data
    inventory_data = db.get_per_farmer_inventory()
    current_stock = inventory_data['remaining_stock'].sum() if not inventory_data.empty else 0

    
    # Display financial metrics in two rows
    st.subheader("Financial Overview")
    
    # First row - Purchase Metrics
    st.markdown("##### Purchase Information")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Purchase Amount", 
            f"PKR {total_purchase_amount:,.2f}",
            help="Total value of all purchases"
        )
    
    with col2:
        st.metric(
            "Amount Paid", 
            f"PKR {total_paid:,.2f}",
            help="Total amount paid to suppliers"
        )
    
    with col3:
        st.metric(
            "Pending to Pay", 
            f"PKR {pending_to_pay:,.2f}",
            delta=f"-PKR {pending_to_pay:,.2f}" if pending_to_pay > 0 else None,
            delta_color="inverse",
            help="Amount still to be paid to suppliers"
        )
    
    # Second row - Sales Metrics
    st.markdown("##### Sales Information")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Sales Amount", 
            f"PKR {total_sales_amount:,.2f}",
            help="Total value of all sales"
        )
    
    with col2:
        st.metric(
            "Amount Received", 
            f"PKR {total_received:,.2f}",
            help="Total amount received from customers"
        )
    
    with col3:
        st.metric(
            "Pending to Receive", 
            f"PKR {pending_to_receive:,.2f}",
            delta=f"+PKR {pending_to_receive:,.2f}" if pending_to_receive > 0 else None,
            delta_color="normal",
            help="Amount still to be received from customers"
        )
    
    # Third row - Profit/Loss and Stock
    st.markdown("##### Overall Status")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Actual Profit/Loss", 
            f"PKR {actual_profit_loss:,.2f}",
            delta=f"PKR {abs(actual_profit_loss):,.2f}" if actual_profit_loss != 0 else None,
            delta_color="normal" if actual_profit_loss > 0 else "inverse",
            help="Actual profit/loss based on received and paid amounts"
        )
    
    with col2:
        st.metric(
            "Potential Profit/Loss", 
            f"PKR {potential_profit_loss:,.2f}",
            delta=f"PKR {abs(potential_profit_loss):,.2f}" if potential_profit_loss != 0 else None,
            delta_color="normal" if potential_profit_loss > 0 else "inverse",
            help="Potential profit/loss based on total sales and purchase amounts"
        )
    
    with col3:
        st.metric(
            "Current Stock", 
            f"{current_stock:.2f} kg",
            help="Current available stock"
        )
    
    # Display payment status summary
    st.subheader("Payment Status Details")
    
    # Purchases payment status
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Purchase Payments")
        if not purchases.empty:
            purchase_status = purchases.groupby('payment_status')['total_amount'].agg(['count', 'sum']).reset_index()
            purchase_status.columns = ['Status', 'Count', 'Amount']
            st.dataframe(purchase_status, hide_index=True)
        else:
            st.info("No purchase data available")
    
    # Sales payment status
    with col2:
        st.markdown("##### Sales Payments")
        if not sales.empty:
            sales_status = sales.groupby('payment_status')['total_amount'].agg(['count', 'sum']).reset_index()
            sales_status.columns = ['Status', 'Count', 'Amount']
            st.dataframe(sales_status, hide_index=True)
        else:
            st.info("No sales data available")
    
    # Display recent transactions
    st.subheader("Recent Transactions")
    tab1, tab2 = st.tabs(["📥 Recent Purchases", "📤 Recent Sales"])
    
    with tab1:
        if not purchases.empty:
            st.dataframe(
                purchases[['date', 'name', 'quantity', 'price_per_unit', 'total_amount', 'payment_amount', 'payment_status']],
                hide_index=True
            )
        else:
            st.info("No recent purchases found.")
    
    with tab2:
        if not sales.empty:
            st.dataframe(
                sales[['date', 'name', 'quantity', 'price_per_unit', 'total_amount', 'payment_amount', 'payment_status']],
                hide_index=True
            )
        else:
            st.info("No recent sales found.")

def show_farmers():
    st.markdown('<h2 class="sub-header">Manage Farmers</h2>', unsafe_allow_html=True)
    
    # Tabs for Add Farmer and View Farmers
    tab1, tab2 = st.tabs(["➕ Add New Farmer", "👁️ View All Farmers"])
    
    # Add Farmer tab
    with tab1:
        with st.form("add_farmer_form", clear_on_submit=True):
            name = st.text_input("Farmer Name")
            contact_number = st.text_input("Contact Number")
            location = st.text_input("Location/Address")
            submit = st.form_submit_button("Add Farmer")
            
            if submit:
                if name:
                    farmer_id = db.add_farmer(name, contact_number, location)
                    if farmer_id:
                        st.success(f"Farmer '{name}' added successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to add farmer. Please try again.")
                else:
                    st.error("Farmer name is required!")


    
    # View Farmers tab
    with tab2:
        farmers = db.get_farmers()
        if not farmers.empty:
            st.dataframe(farmers)
        else:
            st.info("No farmers found. Add some using the 'Add New Farmer' tab.")

def show_transaction_details(transaction, transaction_type):
    import streamlit as st

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    name = transaction.get("name") or transaction.get("buyer_name") or "N/A"
    vehicle = transaction.get("vehicle_number", "N/A")
    driver = transaction.get("driver_name", "N/A")
    quantity = transaction.get("quantity", 0)
    price = transaction.get("price_per_unit", 0)
    amount = transaction.get("total_amount", 0)
    status = transaction.get("payment_status", "N/A")
    payment_mode = transaction.get("payment_mode", "N/A")
    paid = transaction.get("payment_amount", 0)
    date = transaction.get("date", "N/A")

    with col1:
        st.write(f"**{transaction_type} By:** {name}")
        st.write(f"**Driver:** {driver}")
        st.write(f"**Vehicle:** {vehicle}")
    with col2:
        st.write(f"**Quantity (kg):** {quantity}")
        st.write(f"**Rate (Rs/kg):** {price}")
        st.write(f"**Total Amount:** Rs {amount}")
    with col3:
        st.write(f"**Paid:** Rs {paid}")
        st.write(f"**Payment Mode:** {payment_mode}")
        st.write(f"**Status:** {status}")
        st.write(f"**Date:** {date}")
def show_buy_chicken():
    st.markdown('<h2 class="sub-header">Buy Chicken</h2>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🛍️ New Purchase", "📋 View Purchases"])
    
    # New Purchase tab
    with tab1:
        # Get farmers first
        farmers_df = db.get_farmers()
        if farmers_df.empty:
            st.error("No farmers found. Please add farmers first.")
            if st.button("Go to Farmers Section"):
                st.session_state.redirect = "👥 Farmers"
                st.rerun()
            return
        
        # Create farmer selection options with ID
        farmers_df['display_name'] = farmers_df.apply(
            lambda x: f"{x['name']} - {x['location']} (ID: {x.name})", axis=1
        )
        farmer_options = farmers_df['display_name'].tolist()
        
       # Input quantity & price outside form for reactivity
        quantity = st.number_input("Quantity (kg)", min_value=0.0, step=0.5, key="buy_quantity")
        price_per_unit = st.number_input("Price per kg (PKR )", min_value=0.0, step=1.0, key="buy_price")

        # Calculate and display total
        total_amount = st.session_state.get("buy_quantity", 0) * st.session_state.get("buy_price", 0)
        st.write(f"🧮 **Total Amount:** PKR {total_amount:,.2f}")
        

        # Payment checkbox outside form for live toggling
        st.subheader("Payment Info")
        payment_made = st.checkbox("Payment Made?", key="buy_payment_made")

        with st.form("buy_chicken_form", clear_on_submit=True):
            st.subheader("Purchase Details")
            selected_farmer = st.selectbox("Select Farmer", farmer_options)
            farmer_id = int(selected_farmer.split("ID: ")[1].rstrip(")"))

            # Payment fields shown only if checkbox is checked
            payment_mode = None
            payment_amount = 0
            payment_status = "Unpaid"

            if st.session_state.get("buy_payment_made", False):
                payment_mode = st.selectbox(
                    "Payment Mode",
                    ["Cash", "UPI", "Bank Transfer", "Cheque", "Credit/Due"],
                    key="buy_payment_mode"
                )
                payment_amount = st.number_input(
                    "Payment Amount (PKR )",
                    min_value=0.0,
                    max_value=float(total_amount),
                    value=float(total_amount),
                    step=100.0,
                    key="buy_payment_amount"
                )
                payment_status = "Fully Paid" if payment_amount >= total_amount else "Partially Paid"
                remaining_amount = total_amount - payment_amount

                st.write(f"Payment Status: {payment_status}")
                if remaining_amount > 0:
                    st.write(f"Remaining Amount: PKR {remaining_amount:,.2f}")

            # Date, vehicle info, notes
            date = st.date_input("Purchase Date", datetime.now())

            st.subheader("Vehicle Info")
            col1, col2 = st.columns(2)
            with col1:
                vehicle_number = st.text_input("Vehicle Number")
            with col2:
                driver_name = st.text_input("Driver Name")

            st.subheader("Additional Notes")
            notes = st.text_area("Notes")

            # Submit button
            submit = st.form_submit_button("Record Purchase")

            if submit:
                if quantity <= 0:
                    st.error("Please enter a valid quantity.")
                elif price_per_unit <= 0:
                    st.error("Please enter a valid price.")
                else:
                    try:
                        transaction_id = db.add_poultry_transaction(
                            date.strftime('%Y-%m-%d'),
                            farmer_id,
                            'buy',
                            quantity,
                            price_per_unit,
                            vehicle_number,
                            driver_name,
                            notes,
                            payment_mode=payment_mode,
                            payment_amount=payment_amount,
                            payment_status=payment_status
                        )

                        if transaction_id:
                            st.success("Purchase recorded successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to record purchase.")
                    except Exception as e:
                        st.error(f"Error recording purchase: {str(e)}")


    
    # View Purchases tab
    with tab2:
        # Add search functionality
        st.subheader("Search Purchases")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_term = st.text_input("Search by supplier name, vehicle number, or notes")
        with col2:
            start_date = st.date_input("From Date", datetime.now() - timedelta(days=30))
        with col3:
            end_date = st.date_input("To Date", datetime.now())
        
        # Get and filter purchases
        purchases = db.get_poultry_transactions(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            transaction_type='buy'
        )
        
        if not purchases.empty:
            if search_term:
                purchases = purchases[
                    purchases['name'].str.contains(search_term, case=False, na=False) |
                    purchases['vehicle_number'].str.contains(search_term, case=False, na=False) |
                    purchases['notes'].str.contains(search_term, case=False, na=False)
                ]
            
            # Display each purchase with details
            for _, purchase in purchases.iterrows():
                show_transaction_details(purchase, "Purchase")
        else:
            st.info("No purchases found.")

def show_sell_chicken():
    st.markdown('<h2 class="sub-header">Sell Chicken</h2>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["💰 New Sale", "📋 View Sales"])

    # New Sale tab
    with tab1:
        # Get farmers first
        farmers_df = db.get_farmers()
        if farmers_df.empty:
            st.error("No farmers found. Please add farmers first.")
            if st.button("Go to Farmers Section"):
                st.session_state.redirect = "👥 Farmers"
                st.rerun()
            return

        # Get inventory and filter only farmers with stock
        inventory_data = db.get_per_farmer_inventory()
        if inventory_data.empty:
            st.warning("No inventory data available.")
            return

        quantity = st.number_input("Quantity (kg)", min_value=0.0, step=0.5, key="sell_quantity")
        price_per_unit = st.number_input("Price per kg (PKR )", min_value=0.0, step=1.0, key="sell_price")
        total_amount = quantity * price_per_unit
        st.write(f"🧮 **Total Amount:** PKR {total_amount:,.2f}")

        st.subheader("Payment Info")
        payment_made = st.checkbox("Payment Received?", key="sell_payment_made")

        with st.form("sell_chicken_form", clear_on_submit=True):
            inventory_data = inventory_data.merge(farmers_df[['farmer_id', 'name', 'location']], on='farmer_id', how='left')
            inventory_data['display_name'] = inventory_data.apply(
                lambda x: f"{x['name']} - {x['location']} (ID: {x['farmer_id']})", axis=1
            )
            selected_farmer = st.selectbox("Select Buyer", inventory_data['display_name'].tolist())
            farmer_id = int(selected_farmer.split("ID: ")[1].rstrip(")"))

            payment_mode = None
            payment_amount = 0
            payment_status = "Unpaid"
            if payment_made:
                payment_mode = st.selectbox(
                    "Payment Mode",
                    ["Cash", "UPI", "Bank Transfer", "Cheque", "Credit/Due"],
                    key="sell_payment_mode"
                )
                payment_amount = st.number_input(
                    "Payment Amount (PKR )",
                    min_value=0.0,
                    max_value=float(total_amount),
                    value=float(total_amount),
                    step=100.0,
                    key="sell_payment_amount"
                )
                payment_status = "Fully Paid" if payment_amount >= total_amount else "Partially Paid"
                remaining_amount = total_amount - payment_amount
                st.write(f"Payment Status: {payment_status}")
                if remaining_amount > 0:
                    st.write(f"Remaining Amount: PKR {remaining_amount:,.2f}")

            date = st.date_input("Sale Date", datetime.now())
            col1, col2 = st.columns(2)
            with col1:
                vehicle_number = st.text_input("Vehicle Number")
            with col2:
                driver_name = st.text_input("Driver Name")
            notes = st.text_area("Additional Notes")

            submit = st.form_submit_button("Record Sale")

            if submit:
                if quantity <= 0 or price_per_unit <= 0:
                    st.error("Please enter valid quantity and price.")
                else:
                    transaction_id = db.add_poultry_transaction(
                        date.strftime('%Y-%m-%d'),
                        farmer_id,
                        'sell',
                        quantity,
                        price_per_unit,
                        vehicle_number,
                        driver_name,
                        notes,
                        payment_mode,
                        payment_amount,
                        payment_status
                    )
                    if transaction_id:
                        st.success("Sale recorded successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to record sale.")

    # View Sales tab
    with tab2:
        st.subheader("Search Sales")
        col1, col2, col3 = st.columns(3)
        with col1:
            search_term = st.text_input("Search by buyer name, vehicle number, or notes")
        with col2:
            start_date = st.date_input("From Date", datetime.now() - timedelta(days=30))
        with col3:
            end_date = st.date_input("To Date", datetime.now())

        sales = db.get_poultry_transactions(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            transaction_type='sell'
        )

        if not sales.empty:
            sales['name'] = sales['farmer_name'].fillna("Unknown")

            if search_term:
                sales = sales[
                    sales['name'].str.contains(search_term, case=False, na=False) |
                    sales['vehicle_number'].str.contains(search_term, case=False, na=False) |
                    sales['notes'].str.contains(search_term, case=False, na=False)
                ]

            for _, sale in sales.iterrows():
                show_transaction_details(sale, "Sale")
        else:
            st.info("No sales found.")

def show_transaction_details(transaction, transaction_type):
    import streamlit as st

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    name = transaction.get("name") or transaction.get("buyer_name") or "N/A"
    vehicle = transaction.get("vehicle_number", "N/A")
    driver = transaction.get("driver_name", "N/A")
    quantity = transaction.get("quantity", 0)
    price = transaction.get("price_per_unit", 0)
    amount = transaction.get("total_amount", 0)
    status = transaction.get("payment_status", "N/A")
    payment_mode = transaction.get("payment_mode", "N/A")
    paid = transaction.get("payment_amount", 0)
    date = transaction.get("date", "N/A")

    with col1:
        st.write(f"**{transaction_type} By:** {name}")
        st.write(f"**Driver:** {driver}")
        st.write(f"**Vehicle:** {vehicle}")
    with col2:
        st.write(f"**Quantity (kg):** {quantity}")
        st.write(f"**Rate (Rs/kg):** {price}")
        st.write(f"**Total Amount:** Rs {amount}")
    with col3:
        st.write(f"**Paid:** Rs {paid}")
        st.write(f"**Payment Mode:** {payment_mode}")
        st.write(f"**Status:** {status}")
        st.write(f"**Date:** {date}")

    show_payment_form = False
    if st.session_state.get("is_admin", False) and status == "Partially Paid":
        if st.button("Add Remaining Payment", key=f"show_button_{transaction['transaction_id']}"):
            show_payment_form = True

    if show_payment_form:
        st.markdown("#### 💳 Add Remaining Payment")
        with st.form(f"add_payment_form_{transaction['transaction_id']}"):
            additional_payment = st.number_input(
                "Additional Payment (PKR )",
                min_value=0.0,
                max_value=amount - paid,
                step=100.0,
                key=f"additional_payment_{transaction['transaction_id']}"
            )
            new_payment_mode = st.selectbox(
                "Payment Mode",
                ["Cash", "UPI", "Bank Transfer", "Cheque", "Credit/Due"],
                key=f"payment_mode_{transaction['transaction_id']}"
            )
            notes = st.text_area("Payment Notes", key=f"payment_notes_{transaction['transaction_id']}")
            submit_payment = st.form_submit_button("Add Payment")

            if submit_payment and additional_payment > 0:
                success = db.add_payment_history(
                    transaction['transaction_id'],
                    datetime.now().strftime('%Y-%m-%d'),
                    additional_payment,
                    new_payment_mode,
                    notes
                )
                if success:
                    st.success("Payment updated successfully!")
                    st.rerun()
                else:
                    st.error("Failed to update payment.")

    # Payment history section
    history = db.get_payment_history(transaction["transaction_id"])
    if not history.empty:
        st.markdown("#### 📝 Payment History")
        st.dataframe(history[["payment_date", "payment_amount", "payment_mode", "notes"]], hide_index=True)

# Add this filter to both view_purchases and view_sales screens wherever transactions are fetched
def filter_transactions_by_payment_status(df):
    status_filter = st.selectbox("Filter by Payment Status", ["All", "Fully Paid", "Partially Paid", "Unpaid"], key="payment_status_filter")
    if status_filter != "All":
        df = df[df["payment_status"] == status_filter]
    return df

def view_purchases():
    st.title("View Purchases")
    df = db.get_poultry_transactions(transaction_type="buy")
    if not df.empty:
        df = filter_transactions_by_payment_status(df)
        for _, transaction in df.iterrows():
            show_transaction_details(transaction, "Purchase")
    else:
        st.info("No purchase transactions found.")

def view_sales():
    st.title("View Sales")
    df = db.get_poultry_transactions(transaction_type="sell")
    if not df.empty:
        df = filter_transactions_by_payment_status(df)
        for _, transaction in df.iterrows():
            show_transaction_details(transaction, "Sale")
    else:
        st.info("No sale transactions found.")


def show_inventory():
    st.title("Inventory Management")
    
    # Get all inventory data
    inventory_data = db.get_per_farmer_inventory()
    
    if inventory_data.empty:
        st.warning("No inventory data available.")
        return
    
    # Display total metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Stock Purchased (kg)", 
                 f"{inventory_data['total_purchased'].sum():.2f}")
    
    with col2:
        st.metric("Total Stock Sold (kg)", 
                 f"{inventory_data['total_sold'].sum():.2f}")
    
    with col3:
        available_stock = inventory_data['total_purchased'].sum() - inventory_data['total_sold'].sum()
        st.metric("Current Available Stock (kg)", 
                 f"{available_stock:.2f}")

    # Display detailed inventory data
    st.subheader("Detailed Inventory")
    st.dataframe(inventory_data)

def show_money_management():
    from money_management import handle_money_management
    handle_money_management()

def show_user_management():
    if not st.session_state.get('is_admin', False):
        st.error("Access Denied. Only administrators can access this section.")
        return
        
    st.title("User Management")
    # ... rest of user management code ...

# Main app logic
def main():
    """Main application function."""
    # Initialize session state
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False
    
    # Check if user is logged in
    if st.session_state.user is None:
        login_page()
        return
    
    # Show header with business name
    st.markdown('<h1 class="main-header">Haji Poultry Management System</h1>', unsafe_allow_html=True)
    
    # Show sidebar and navigation only after login
    navigation_options = get_navigation_options(st.session_state.user['role'])
    page = st.sidebar.radio("Go to", navigation_options)
    
    # Show user info in sidebar
    st.sidebar.markdown(f"""
    <div style='padding: 10px; background-color: rgba(255, 255, 255, 0.1); border-radius: 5px; margin-bottom: 10px;'>
        <div style='font-size: 1.1em; margin-bottom: 5px;'>👤 User Information</div>
        <div>Logged in as: <b>{st.session_state.username}</b></div>
        <div>Role: <b>{st.session_state.user['role']}</b></div>
        <div>Admin Access: <b>{'Yes' if st.session_state.is_admin else 'No'}</b></div>
    </div>
    """, unsafe_allow_html=True)
        
    # Show logout button in sidebar
    if st.sidebar.button("Logout", key="logout_button"):
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # Page routing with role-based access control
    if not st.session_state.is_admin and page not in ["💵 Money Management"]:
        st.error("You don't have permission to access this page. Please log in as an admin.")
        return

    # Rest of your page routing code...
    if page == "📊 Main Dashboard":
        show_dashboard()
    elif page == "👥 Farmers":
        show_farmers()
    elif page == "🛒 Buy Chicken":
        show_buy_chicken()
    elif page == "💰 Sell Chicken":
        show_sell_chicken()
    elif page == "💵 Money Management":
        show_money_management()
    elif page == "👤 User Management":
        user_management_page()
    elif page == "📊 Inventory":
        show_inventory()

if __name__ == "__main__":
    main()