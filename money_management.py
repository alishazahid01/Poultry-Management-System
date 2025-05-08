import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
import io
import sqlite3
from database import PoultryDatabase

# Custom CSS for money management
st.markdown("""
<style>
    .money-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .balance-positive {
        color: #2ecc71;
        font-size: 2rem;
        font-weight: bold;
    }
    .balance-negative {
        color: #e74c3c;
        font-size: 2rem;
        font-weight: bold;
    }
    .transaction-row {
        padding: 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    .transaction-row:hover {
        background-color: rgba(255, 255, 255, 0.05);
    }
    .expense-category {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 5px 10px;
        border-radius: 15px;
        margin: 2px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

def display_balance(container, balance):
    container.markdown(f"""
    <div class="money-card">
        <h2>Current Balance</h2>
        <div class="{'balance-positive' if balance >= 0 else 'balance-negative'}">
            PKR {abs(balance):,.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=5)  # Cache for 5 seconds
def get_cached_balance(_db, user_id):
    return _db.get_user_balance(user_id)

@st.cache_data(ttl=5)  # Cache for 5 seconds
def get_cached_transactions(_db, user_id):
    return _db.get_user_transactions(user_id)

@st.cache_data(ttl=5)  # Cache for 5 seconds
def get_cached_expenses(_db, user_id):
    return _db.get_user_expenses(user_id)

def expense_form(db, user_id):
    """Display and handle the expense recording form"""
    with st.form("record_expense_form", clear_on_submit=True):
        st.subheader("Record New Expense")
        
        # Amount
        amount = st.number_input("Expense Amount (PKR )", min_value=0.0, step=10.0)
        
        # Category selection
        categories = [
            "Food & Beverages",
            "Transportation",
            "Utilities",
            "Office Supplies",
            "Equipment",
            "Maintenance",
            "Salaries",
            "Marketing",
            "Other"
        ]
        category = st.selectbox("Expense Category", categories)
        
        # Description
        description = st.text_area("Expense Description")
        
        # Date
        expense_date = st.date_input("Expense Date", datetime.now())
        
        # Receipt image upload
        receipt_image = st.file_uploader("Upload Receipt Image (optional)", type=['png', 'jpg', 'jpeg'])
        
        # Submit button
        submit_expense = st.form_submit_button("Record Expense")
        
        if submit_expense:
            if amount <= 0:
                st.error("Please enter a valid amount greater than 0.")
            else:
                # Get current balance
                current_balance = get_cached_balance(db, user_id)
                
                if current_balance < amount:
                    st.error(f"Insufficient balance! You only have PKR {current_balance:,.2f}")
                    return
                
                # Process receipt image if uploaded
                image_data = None
                if receipt_image:
                    image_bytes = receipt_image.getvalue()
                    # Resize image if too large
                    img = Image.open(io.BytesIO(image_bytes))
                    max_size = (800, 800)
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    # Convert back to bytes
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format=img.format if img.format else 'JPEG')
                    image_data = img_byte_arr.getvalue()
                
                # Start a transaction
                conn = sqlite3.connect(db.db_file)
                cursor = conn.cursor()
                try:
                    # 1. Record the expense
                    cursor.execute('''
                    INSERT INTO expenses (user_id, amount, category, description, date, receipt_image)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, amount, category, description, expense_date.strftime('%Y-%m-%d'), image_data))
                    expense_id = cursor.lastrowid
                    
                    # 2. Create a money transaction (from user to system/expense)
                    cursor.execute('''
                    INSERT INTO money_transactions (date, from_user_id, to_user_id, amount, description)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (
                        expense_date.strftime('%Y-%m-%d'),
                        user_id,  # From user
                        0,  # To system (0 is system ID)
                        amount,
                        f"Expense: {category} - {description}"
                    ))
                    
                    # Commit both operations
                    conn.commit()
                    
                    # Clear specific cache entries
                    get_cached_expenses.clear()
                    get_cached_balance.clear()
                    get_cached_transactions.clear()
                    
                    st.success(f"Expense of PKR {amount:,.2f} recorded successfully!")
                    st.info(f"Your new balance: PKR {(current_balance - amount):,.2f}")
                    st.rerun()
                    
                except Exception as e:
                    conn.rollback()
                    st.error(f"Failed to record expense: {str(e)}")
                finally:
                    conn.close()

def view_expenses(db, user_id, is_admin=False):
    """Display expense history with filters"""
    st.markdown("### Expense History")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        if is_admin:
            # Get all users for admin
            users = db.get_all_users()
            user_options = [(user[0], user[1]) for user in users]
            selected_user = st.selectbox(
                "Select User",
                options=user_options,
                format_func=lambda x: x[1],
                index=[i for i, user in enumerate(user_options) if user[0] == user_id][0]
            )
            filter_user_id = selected_user[0]
        else:
            filter_user_id = user_id
    
    with col2:
        categories = ["All Categories", "Food & Beverages", "Transportation", "Utilities", 
                     "Office Supplies", "Equipment", "Maintenance", "Salaries", "Marketing", "Other"]
        selected_category = st.selectbox("Category Filter", categories)
    
    with col3:
        date_range = st.selectbox(
            "Date Range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "All time"]
        )
    
    # Get expenses based on filters
    expenses = get_cached_expenses(db, filter_user_id)
    
    if not expenses.empty:
        # Apply filters
        if selected_category != "All Categories":
            expenses = expenses[expenses['category'] == selected_category]
        
        if date_range != "All time":
            days = int(date_range.split()[1])
            cutoff_date = datetime.now() - pd.Timedelta(days=days)
            expenses['date'] = pd.to_datetime(expenses['date'])
            expenses = expenses[expenses['date'] >= cutoff_date]
        
        # Display expenses
        if not expenses.empty:
            # Format for display
            display_expenses = expenses.copy()
            display_expenses['amount'] = display_expenses['amount'].apply(lambda x: f"PKR {x:,.2f}")
            display_expenses['date'] = pd.to_datetime(display_expenses['date']).dt.strftime('%Y-%m-%d')
            
            # Add view receipt button column
            st.dataframe(
                display_expenses[['date', 'category', 'description', 'amount']],
                use_container_width=True
            )
            
            # Show receipt images in expandable sections
            for idx, row in expenses.iterrows():
                if row['receipt_image'] is not None:
                    with st.expander(f"View Receipt - {row['date'].strftime('%Y-%m-%d')} - {row['description'][:30]}..."):
                        image = Image.open(io.BytesIO(row['receipt_image']))
                        st.image(image, caption=f"Receipt for PKR {row['amount']:,.2f}")
            
            # Summary statistics
            total_expenses = expenses['amount'].sum()
            st.markdown(f"**Total Expenses:** PKR {total_expenses:,.2f}")
            
            # Category-wise breakdown
            st.markdown("### Expense Breakdown by Category")
            category_summary = expenses.groupby('category')['amount'].sum().reset_index()
            category_summary['percentage'] = (category_summary['amount'] / total_expenses * 100).round(2)
            
            # Display category breakdown
            for _, row in category_summary.iterrows():
                st.markdown(f"""
                <div class="expense-category">
                    {row['category']}: PKR {row['amount']:,.2f} ({row['percentage']}%)
                </div>
                """, unsafe_allow_html=True)
            
            # Export option
            if st.button("Export Expenses to Excel"):
                with pd.ExcelWriter("expense_report.xlsx", engine='xlsxwriter') as writer:
                    display_expenses.to_excel(writer, sheet_name='Expenses', index=False)
                st.success("Expenses exported to 'expense_report.xlsx'")
        else:
            st.info("No expenses found matching the selected filters.")
    else:
        st.info("No expenses recorded yet.")

def handle_money_management():
    st.markdown('<h2 class="sub-header">Money Management</h2>', unsafe_allow_html=True)
    
    # Initialize database
    db = PoultryDatabase()
    
    # Create tabs for different money management functions
    if st.session_state.is_admin:
        tabs = st.tabs(["💰 Admin Money", "💸 Add Transaction", "📊 View Transactions"])
    
        # Admin Money tab
        with tabs[0]:
            st.subheader("System Money Management")
            
            # Get system money
            system_balance = db.get_system_money()
            
            # Display system balance
            st.metric(
                "System Balance",
                f"PKR {system_balance:,.2f}",
                help="Total money in the system"
            )
            
            # Form to update system money
            with st.form("update_system_money", clear_on_submit=True):
                st.subheader("Update System Money")
                new_amount = st.number_input("New Amount (PKR )", min_value=0.0, step=100.0, value=float(system_balance))
                reason = st.text_area("Reason for Update")
                update_submitted = st.form_submit_button("Update System Money")
                
                if update_submitted:
                    if new_amount < 0:
                        st.error("Amount cannot be negative!")
                    else:
                        success = db.update_system_money(new_amount)
                        if success:
                            st.success(f"System money updated to PKR {new_amount:,.2f}")
                            st.rerun()
                        else:
                            st.error("Failed to update system money!")
            
            # Distribution section
            st.markdown("---")
            st.subheader("Distribute Money to Users")
            with st.form("distribute_money", clear_on_submit=True):
                # Get all users except admin
                users = db.get_all_users()
                users_df = pd.DataFrame(users, columns=['ID', 'Username', 'Role', 'Created At'])
                users_df = users_df[users_df['Role'] != 'admin']  # Filter out admins
                
                if not users_df.empty:
                    # Create user selection dropdown
                    user_options = [(row['ID'], f"{row['Username']} ({row['Role']})") for _, row in users_df.iterrows()]
                    selected_user_id = st.selectbox(
                        "Select User",
                        options=[uid for uid, _ in user_options],
                        format_func=lambda x: next((name for uid, name in user_options if uid == x), ""),
                        key="distribution_user_select"
                    )
                    
                    # Amount input for selected user
                    amount = st.number_input(
                        "Amount to Distribute (PKR )",
                        min_value=0.0,
                        max_value=float(system_balance),
                        step=100.0,
                        key="distribution_amount"
                    )
                    
                    description = st.text_area("Distribution Description", key="dist_description")
                    distribute_submitted = st.form_submit_button("Distribute Money")
                    
                    if distribute_submitted:
                        if amount <= 0:
                            st.error("Please enter an amount greater than 0.")
                        elif amount > system_balance:
                            st.error(f"Distribution amount (PKR {amount:,.2f}) exceeds system balance (PKR {system_balance:,.2f})!")
                        else:
                            # First deduct from system (system to user transaction)
                            transaction_id = db.add_money_transaction(
                                datetime.now().strftime('%Y-%m-%d'),
                                0,  # From system
                                int(selected_user_id),  # To selected user
                                amount,
                                f"Distribution: {description}",
                                transaction_type='distribution'
                            )
                            
                            if transaction_id:
                                # Update system balance
                                new_system_balance = system_balance - amount
                                success = db.update_system_money(new_system_balance)
                                
                                if success:
                                    selected_username = next((name for uid, name in user_options if uid == selected_user_id), "")
                                    st.success(f"Successfully distributed PKR {amount:,.2f} to {selected_username}!")
                                    st.info(f"New system balance: PKR {new_system_balance:,.2f}")
                                    st.rerun()
                                else:
                                    st.error("Failed to update system balance!")
                            else:
                                st.error("Failed to distribute money. Please try again.")
                else:
                    st.warning("No users found to distribute money to. Please add users in User Management first.")
            
            st.markdown("---")
            # Display recent system transactions
            st.subheader("Recent System Transactions")
            system_transactions = db.get_all_transactions_with_proof()
            if not system_transactions.empty:
                # Filter for system transactions only
                system_transactions = system_transactions[
                    (system_transactions['from_user_id'] == 0) | 
                    (system_transactions['to_user_id'] == 0)
                    ].copy()
                    
                if not system_transactions.empty:
                    # Format date
                    system_transactions['date'] = pd.to_datetime(system_transactions['date']).dt.strftime('%Y-%m-%d')
                    # Display transactions
                    st.dataframe(
                        system_transactions[['date', 'from_username', 'to_username', 'amount', 'description', 'transaction_type']],
                        use_container_width=True
                    )
                else:
                    st.info("No system transactions found.")
            else:
                st.info("No transactions found.")
    else:
        tabs = st.tabs(["💸 Add Transaction", "📊 View Transactions"])

        with tabs[0]:
            st.subheader("Add Money Transaction")
            current_balance = db.get_user_balance(st.session_state.user["user_id"])
            st.metric("Your Current Balance", f"PKR {current_balance:,.2f}")

            with st.form("user_add_transaction_form", clear_on_submit=True):
                date = st.date_input("Transaction Date", datetime.now())
                receiver_username = st.text_input("Receiver Name")
                amount = st.number_input("Amount (PKR )", min_value=0.01, step=100.0)
                description = st.text_area("Description")
                proof_file = st.file_uploader("Upload Proof", type=['jpg', 'jpeg', 'png'])
                submit = st.form_submit_button("Submit Transaction")

                if submit:
                    if not receiver_username:
                        st.error("Receiver name is required.")
                    elif amount > current_balance:
                        st.error("Insufficient balance.")
                    else:
                        proof_image = proof_file.getvalue() if proof_file else None
                        txn_id = db.add_money_transaction(
                            date.strftime('%Y-%m-%d'),
                            st.session_state.user["user_id"],
                            0,
                            amount,
                            f"Payment to {receiver_username}: {description}",
                            proof_image=proof_image,
                            transaction_type='expense'
                        )
                        if txn_id:
                            st.success(f"PKR {amount:,.2f} sent to {receiver_username}.")
                            st.rerun()
                        else:
                            st.error("Transaction failed.")

        with tabs[1]:
            st.subheader("Your Transactions")
            transactions = db.get_user_transactions_with_proof(st.session_state.user["user_id"])
            if not transactions.empty:
                transactions['date'] = pd.to_datetime(transactions['date'])
                for _, tx in transactions.iterrows():
                    with st.expander(f"PKR {tx['amount']:,.2f} - {tx['date'].strftime('%Y-%m-%d')} - {tx['description'][:40]}..."):
                        st.write(f"From: {tx['from_username'] or 'System'}")
                        st.write(f"To: {tx['to_username'] or 'System'}")
                        st.write(f"Description: {tx['description']}")
                        if tx['proof_image'] is not None:
                            st.image(tx['proof_image'], caption='Proof')
            else:
                st.info("No transactions found.")

def main(db):  # Accept database instance as parameter
    st.title("Money Management Dashboard")
    
    # Create a container for the balance display
    balance_container = st.empty()
    
    # Get user's current balance
    user_id = st.session_state.user["user_id"]
    balance = get_cached_balance(db, user_id)
    display_balance(balance_container, balance)
    
    # Tabs for different sections
    tabs = st.tabs(["💰 Transactions", "📝 Record Expense", "📊 View Expenses"])
    
    with tabs[0]:
        # Original transaction functionality
        with st.expander("Transaction Details", expanded=False):
            # Get received transactions
            received = get_cached_transactions(db, user_id)
            if not received.empty:
                st.write("### Received Transactions")
                received_sum = received[received['to_user_id'] == user_id]['amount'].sum()
                st.write(f"Total Received: PKR {received_sum:,.2f}")
                st.dataframe(received[received['to_user_id'] == user_id])
            
            # Get sent transactions
            st.write("### Sent Transactions")
            if not received.empty:
                sent_sum = received[received['from_user_id'] == user_id]['amount'].sum()
                st.write(f"Total Sent: PKR {sent_sum:,.2f}")
                st.dataframe(received[received['from_user_id'] == user_id])
        
        # Admin specific features
        if st.session_state.user["role"] == "admin":
            st.markdown("### Admin Controls")
            
            # Add money form
            with st.form("add_money_form", clear_on_submit=True):
                st.subheader("Add Money to System")
                amount = st.number_input("Amount (PKR )", min_value=0.0, step=100.0)
                description = st.text_area("Description")
                add_money_submitted = st.form_submit_button("Add Money")
                
                if add_money_submitted:
                    if amount <= 0:
                        st.error("Please enter a valid amount greater than 0.")
                    else:
                        # Add money to system (from system to system, special case)
                        transaction_id = db.add_money_transaction(
                            datetime.now().strftime('%Y-%m-%d'),
                            0,  # System is the source
                            0,  # System is the destination
                            amount,
                            description,
                            transaction_type='system_input'
                        )
                        if transaction_id:
                            # Clear specific cache entries
                            get_cached_balance.clear()
                            get_cached_transactions.clear()
                            st.success(f"Successfully added PKR {amount:,.2f}")
                            st.rerun()
                        else:
                            st.error("Failed to add money. Please try again.")
            
            # Transfer money form
            with st.form("transfer_money_form", clear_on_submit=True):
                st.subheader("Transfer Money to User")
                
                # Get all users except current admin
                users = db.get_all_users()
                if users:
                    # Convert users list to DataFrame
                    users_df = pd.DataFrame(users, columns=['ID', 'Username', 'Role', 'Created At'])
                    # Filter out current admin
                    users_df = users_df[users_df['ID'] != user_id]
                    
                    if not users_df.empty:
                        user_options = users_df.apply(
                            lambda x: f"{x['Username']} ({x['Role']}) - ID: {x['ID']}", 
                            axis=1
                        ).tolist()
                        
                        selected_user = st.selectbox("Select User", user_options)
                        transfer_amount = st.number_input("Amount to Transfer (PKR )", min_value=0.0, step=100.0)
                        transfer_desc = st.text_area("Transfer Description")
                        
                        transfer_submit = st.form_submit_button("Transfer Money")
                        
                        if transfer_submit:
                            if transfer_amount > balance:
                                st.error("Insufficient balance!")
                            elif transfer_amount <= 0:
                                st.error("Please enter a valid amount greater than 0.")
                            else:
                                # Extract user ID from selection
                                to_user_id = int(selected_user.split("ID: ")[1])
                                
                                # Add transfer transaction
                                transaction_id = db.add_money_transaction(
                                    datetime.now().strftime('%Y-%m-%d'),
                                    user_id,
                                    to_user_id,
                                    transfer_amount,
                                    transfer_desc
                                )
                                if transaction_id:
                                    # Clear specific cache entries
                                    get_cached_balance.clear()
                                    get_cached_transactions.clear()
                                    st.success(f"Money transferred successfully to {selected_user.split(' (')[0]}!")
                                    st.rerun()
                                else:
                                    st.error("Failed to transfer money. Please try again.")
                    else:
                        st.warning("No other users found in the system.")
                else:
                    st.warning("No users found. Please add users in User Management first.")
    
    with tabs[1]:
        # Record expense form
        expense_form(db, user_id)
    
    if st.session_state.is_admin:
        with tabs[2]:
            # View expenses with filters
            view_expenses(db, user_id, is_admin=st.session_state.user["role"] == "admin")

if __name__ == "__main__":
    handle_money_management() 