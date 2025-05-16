import psycopg2
import os
import pandas as pd
from datetime import datetime
import hashlib

class PoultryDatabase:
    def connect(self):
        return psycopg2.connect(**self.db_config)

    def __init__(self):
        self.db_config = {
            "dbname": os.environ.get("PG_DBNAME"),
            "user": os.environ.get("PG_USER"),
            "password": os.environ.get("PG_PASSWORD"),
            "host": os.environ.get("PG_HOST"),
            "port": 5432
        }
        self._create_tables()
        self._verify_tables()
        self._verify_database_setup()  # Add verification step
    
    def _create_tables(self):
        """Initialize the database by creating tables if they don't exist."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Start transaction
            conn.execute("BEGIN IMMEDIATE")
            
            # Create Users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create System Money table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_money (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_amount REAL NOT NULL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create money_transactions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS money_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                proof_image BLOB,
                transaction_type TEXT NOT NULL,
                remaining_balance REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users (user_id),
                FOREIGN KEY (to_user_id) REFERENCES users (user_id)
            )
            ''')
            
            # Create Farmers table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS farmers (
                farmer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_number TEXT,
                location TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create Poultry Transactions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS poultry_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                farmer_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price_per_unit REAL NOT NULL,
                total_amount REAL NOT NULL,
                vehicle_number TEXT,
                driver_name TEXT,
                notes TEXT,
                payment_mode TEXT,
                payment_amount REAL DEFAULT 0,
                payment_status TEXT DEFAULT 'Unpaid',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (farmer_id) REFERENCES farmers (farmer_id)
            )
            ''')
            
            # Initialize system money if not exists
            cursor.execute("SELECT COUNT(*) FROM system_money")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO system_money (total_amount) VALUES (0)")
            
            # Commit changes
            conn.commit()
            print("Debug: Tables created/verified successfully")
            
        except Exception as e:
            print(f"Error creating/verifying tables: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def _verify_tables(self):
        """Verify that all tables have the correct structure."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Check poultry_transactions table structure
            cursor.execute("PRAGMA table_info(poultry_transactions)")
            columns = {column[1]: column[2] for column in cursor.fetchall()}
            
            print("Debug: Current table structure:")
            for column, type_ in columns.items():
                print(f"Column: {column}, Type: {type_}")
            
            # Verify required columns exist
            required_columns = {
                'transaction_id': 'INTEGER',
                'date': 'TEXT',
                'farmer_id': 'INTEGER',
                'transaction_type': 'TEXT',
                'quantity': 'REAL',
                'price_per_unit': 'REAL',
                'total_amount': 'REAL',
                'vehicle_number': 'TEXT',
                'driver_name': 'TEXT',
                'notes': 'TEXT',
                'payment_mode': 'TEXT',
                'payment_amount': 'REAL',
                'payment_status': 'TEXT',
                'created_at': 'TIMESTAMP'
            }
            
            missing_columns = set(required_columns.keys()) - set(columns.keys())
            if missing_columns:
                print(f"Warning: Missing columns in poultry_transactions: {missing_columns}")
                self._update_poultry_transactions_table()
        
        except Exception as e:
            print(f"Error verifying tables: {str(e)}")
        finally:
            conn.close()
    
    def _update_poultry_transactions_table(self):
        """Update poultry_transactions table with new payment columns if they don't exist."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Rename the existing table
            cursor.execute("ALTER TABLE poultry_transactions RENAME TO poultry_transactions_old")
            
            # Create the new table with all columns
            cursor.execute('''
            CREATE TABLE poultry_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                farmer_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price_per_unit REAL NOT NULL,
                total_amount REAL NOT NULL,
                vehicle_number TEXT,
                driver_name TEXT,
                notes TEXT,
                payment_mode TEXT,
                payment_amount REAL DEFAULT 0,
                payment_status TEXT DEFAULT 'Unpaid',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (farmer_id) REFERENCES farmers (farmer_id)
            )
            ''')
            
            # Copy data from old table to new table
            cursor.execute('''
            INSERT INTO poultry_transactions (
                transaction_id, date, farmer_id, transaction_type,
                quantity, price_per_unit, total_amount,
                vehicle_number, driver_name, notes,
                payment_mode, payment_amount, payment_status,
                created_at
            )
            SELECT 
                transaction_id, date, farmer_id, transaction_type,
                quantity, price_per_unit, total_amount,
                vehicle_number, driver_name, notes,
                COALESCE(payment_mode, NULL),
                COALESCE(payment_amount, 0),
                COALESCE(payment_status, 'Unpaid'),
                created_at
            FROM poultry_transactions_old
            ''')
            
            # Drop the old table
            cursor.execute("DROP TABLE poultry_transactions_old")
            
            conn.commit()
        except Exception as e:
            print(f"Error updating table: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    # User management methods
    def add_user(self, username, password, role="user", created_by_admin_id=None):
        """Add a new user to the database. Only admin can create users."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Check if creator is admin
            if created_by_admin_id:
                cursor.execute("SELECT role FROM users WHERE user_id = %s", (created_by_admin_id,))
                creator_role = cursor.fetchone()
                if not creator_role or creator_role[0] != 'admin':
                    conn.close()
                    return None
            
            # Hash the password
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute('''
            INSERT INTO users (username, password_hash, role) 
            VALUES (%s, %s, %s)
            ''', (username, password_hash, role))
            
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        except psycopg2.IntegrityError:
            return None
        finally:
            conn.close()
    
    def get_all_users(self):
        """Get all users (admin only)."""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT user_id, username, role, created_at 
        FROM users 
        ORDER BY created_at DESC
        ''')
        
        users = cursor.fetchall()
        conn.close()
        return users
    
    def authenticate_user(self, username, password):
        """Authenticate a user and return their role if successful."""
        conn = self.connect()
        cursor = conn.cursor()
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute('''
        SELECT user_id, role FROM users 
        WHERE username = %s AND password_hash = %s
        ''', (username, password_hash))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {"user_id": result[0], "role": result[1]}
        return None
    
    def get_user_balance(self, user_id):
        """Calculate the current balance for a user."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Get balance from ALL transactions
            cursor.execute('''
            SELECT COALESCE(SUM(CASE 
                WHEN to_user_id = %s THEN amount 
                WHEN from_user_id = %s THEN -amount 
                ELSE 0 
            END), 0)
            FROM money_transactions
            ''', (user_id, user_id))
            
            balance = cursor.fetchone()[0] or 0
            print(f"Debug: User {user_id} balance calculation:")
            print(f"Final balance: {balance}")
            return float(balance)
        
        except Exception as e:
            print(f"Error calculating balance: {e}")
            return 0.0
        finally:
            conn.close()
    
    # Money transaction methods
    def update_system_money(self, amount):
        """Update system money (admin's balance)."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Get admin user_id
            cursor.execute("SELECT user_id FROM users WHERE role = 'admin' LIMIT 1")
            admin_result = cursor.fetchone()
            
            if not admin_result:
                print("Debug: No admin user found")
                return False
            
            admin_id = admin_result[0]
            
            # Add a transaction to adjust admin's balance
            current_balance = self.get_system_money()
            adjustment_amount = amount - current_balance
            
            if adjustment_amount != 0:
                # Create a system_input transaction to adjust the balance
                cursor.execute("""
                INSERT INTO money_transactions (
                    date, from_user_id, to_user_id, amount, 
                    description, transaction_type, remaining_balance
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    datetime.now().strftime('%Y-%m-%d'),
                    0 if adjustment_amount > 0 else admin_id,  # From system if positive, from admin if negative
                    admin_id if adjustment_amount > 0 else 0,  # To admin if positive, to system if negative
                    abs(adjustment_amount),
                    "System money adjustment",
                    'system_input',
                    amount
                ))
                
                conn.commit()
                print(f"Debug: System money updated to: {amount}")
                return True
            return True  # No adjustment needed
                
        except Exception as e:
            print(f"Error updating system money: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_system_money(self):
        """Get current system money (which is the admin's balance)."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # First get the admin user_id
            cursor.execute("SELECT user_id FROM users WHERE role = 'admin' LIMIT 1")
            admin_result = cursor.fetchone()
            
            if not admin_result:
                print("Debug: No admin user found")
                return 0
            
            admin_id = admin_result[0]
            print(f"Debug: Found admin_id: {admin_id}")
            
            # Get admin's balance including ALL transactions
            cursor.execute('''
            SELECT COALESCE(SUM(CASE 
                WHEN to_user_id = %s THEN amount 
                WHEN from_user_id = %s THEN -amount 
                ELSE 0 
            END), 0) as balance
            FROM money_transactions
            ''', (admin_id, admin_id))
            
            balance = cursor.fetchone()[0] or 0
            print(f"Debug: Admin (system) balance calculation:")
            
            # For debugging, let's see all transactions
            cursor.execute('''
            SELECT date, from_user_id, to_user_id, amount, transaction_type, description
            FROM money_transactions
            WHERE from_user_id = %s OR to_user_id = %s
            ORDER BY date
            ''', (admin_id, admin_id))
            
            transactions = cursor.fetchall()
            print("Debug: Admin transactions:")
            for t in transactions:
                print(f"  {t[0]}: {t[1]}->{t[2]} Amount: {t[3]} Type: {t[4]} Desc: {t[5]}")
            
            print(f"Debug: Final admin balance: {balance}")
            return float(balance)
        
        except Exception as e:
            print(f"Error getting system money: {e}")
            return 0
        finally:
            conn.close()

    def get_balance(self, user_id):
        """Calculate user balance from transactions."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            print(f"Debug: Calculating balance for user {user_id}")
            # Get all transactions involving this user
            cursor.execute("""
                SELECT from_user_id, to_user_id, amount, transaction_type, description
                FROM money_transactions
                WHERE from_user_id = %s OR to_user_id = %s
            """, (user_id, user_id))
            
            transactions = cursor.fetchall()
            balance = 0
            
            print("Debug: User transactions:")
            for trans in transactions:
                from_id, to_id, amount, trans_type, desc = trans
                
                # Include ALL transactions in balance calculation
                if to_id == user_id:
                    balance += amount
                    print(f"  +{amount} ({trans_type}: {desc})")
                if from_id == user_id:
                    balance -= amount
                    print(f"  -{amount} ({trans_type}: {desc})")
            
            print(f"Debug: Final balance calculation: {balance}")
            return balance
            
        except Exception as e:
            print(f"Error in get_balance: {str(e)}")
            return 0
        finally:
            conn.close()

    def add_money_transaction(self, date, from_user_id, to_user_id, amount, description, transaction_type='normal', proof_image=None):
        """Add a new money transaction."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            print(f"Debug: Adding transaction: {from_user_id}->{to_user_id} Amount: {amount} Type: {transaction_type}")
            
            # Special handling for system input transactions
            if transaction_type == 'system_input':
                # Insert the transaction record
                cursor.execute("""
                    INSERT INTO money_transactions (
                        date, from_user_id, to_user_id, amount, 
                        description, transaction_type, remaining_balance, proof_image
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    date, from_user_id, to_user_id, amount, 
                    description, transaction_type,
                    amount,  # For system_input, remaining_balance is the amount being added
                    proof_image
                ))
                
                transaction_id = cursor.lastrowid
                conn.commit()
                print(f"Debug: Added system_input transaction {transaction_id}")
                return transaction_id

            # For normal transactions
            # Get current balances
            from_balance = self.get_balance(from_user_id)
            print(f"Debug: From user {from_user_id} balance: {from_balance}")
            
            # Check sufficient balance
            if from_user_id != 0 and from_balance < amount:  # Skip check if from_user_id is system (0)
                print(f"Debug: Insufficient balance. Has: {from_balance}, Needs: {amount}")
                return None
                    
            # Insert the transaction
            cursor.execute("""
                INSERT INTO money_transactions (
                    date, from_user_id, to_user_id, amount, 
                    description, transaction_type, remaining_balance, proof_image
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                date, from_user_id, to_user_id, amount, 
                description, transaction_type,
                from_balance - amount if from_user_id != 0 else 0,  # Only track remaining balance for real users
                proof_image
            ))
            
            transaction_id = cursor.lastrowid
            conn.commit()
            print(f"Debug: Added normal transaction {transaction_id}")
            return transaction_id
            
        except Exception as e:
            print(f"Error in add_money_transaction: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_user_transactions_with_proof(self, user_id):
        """Get all transactions for a user including proof images."""
        conn = self.connect()
        
        try:
            query = '''
            SELECT 
                mt.*,
                u1.username as from_username,
                u2.username as to_username,
                CASE 
                    WHEN mt.from_user_id = %s THEN -mt.amount 
                    WHEN mt.to_user_id = %s THEN mt.amount 
                END as balance_change,
                mt.remaining_balance
            FROM money_transactions mt
            LEFT JOIN users u1 ON mt.from_user_id = u1.user_id
            LEFT JOIN users u2 ON mt.to_user_id = u2.user_id
            WHERE mt.from_user_id = %s OR mt.to_user_id = %s
            ORDER BY mt.date DESC, mt.created_at DESC
            '''
            
            df = pd.read_sql(query, conn, params=(user_id, user_id, user_id, user_id))
            # Convert numeric columns to float
            numeric_columns = ['amount', 'balance_change', 'remaining_balance']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            return df
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def get_all_transactions_with_proof(self):
        """Get all transactions with proof images (admin only)."""
        conn = self.connect()
        
        try:
            query = '''
            SELECT 
                mt.*,
                u1.username as from_username,
                u2.username as to_username,
                CASE 
                    WHEN mt.from_user_id = 0 THEN -mt.amount 
                    WHEN mt.to_user_id = 0 THEN mt.amount 
                END as balance_change,
                mt.remaining_balance
            FROM money_transactions mt
            LEFT JOIN users u1 ON mt.from_user_id = u1.user_id
            LEFT JOIN users u2 ON mt.to_user_id = u2.user_id
            ORDER BY mt.date DESC, mt.created_at DESC
            '''
            
            df = pd.read_sql(query, conn)
            # Convert numeric columns to float
            numeric_columns = ['amount', 'balance_change', 'remaining_balance']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            return df
        except Exception as e:
            print(f"Error getting all transactions: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    # Expense methods
    def add_expense(self, user_id, amount, category, description, date, receipt_image=None):
        """Add a new expense record"""
        conn = self.connect()
        c = conn.cursor()
        try:
            c.execute('''
            INSERT INTO expenses (user_id, amount, category, description, date, receipt_image)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''', (user_id, amount, category, description, date, receipt_image))
            
            expense_id = c.lastrowid
            conn.commit()
            return expense_id
        except Exception as e:
            print(f"Error adding expense: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_expenses(self, user_id):
        """Get all expenses for a user"""
        conn = self.connect()
        try:
            query = '''
            SELECT 
                expense_id,
                amount,
                category,
                description,
                date,
                receipt_image,
                created_at
            FROM expenses
            WHERE user_id = %s
            ORDER BY date DESC, created_at DESC
            '''
            
            expenses = pd.read_sql_query(query, conn, params=(user_id,))
            return expenses
        except Exception as e:
            print(f"Error getting expenses: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_all_expenses(self):
        """Get all expenses (admin only)"""
        conn = self.connect()
        try:
            query = '''
            SELECT 
                e.expense_id,
                e.user_id,
                u.username,
                e.amount,
                e.category,
                e.description,
                e.date,
                e.receipt_image,
                e.created_at
            FROM expenses e
            JOIN users u ON e.user_id = u.user_id
            ORDER BY e.date DESC, e.created_at DESC
            '''
            
            expenses = pd.read_sql_query(query, conn)
            return expenses
        except Exception as e:
            print(f"Error getting all expenses: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def delete_expense(self, expense_id, user_id):
        """Delete an expense record"""
        conn = self.connect()
        c = conn.cursor()
        try:
            c.execute('''
            DELETE FROM expenses 
            WHERE expense_id = %s AND user_id = %s
            ''', (expense_id, user_id))
            
            if c.rowcount > 0:
                conn.commit()
                return True
            return False
        except Exception as e:
            print(f"Error deleting expense: {e}")
            return False
        finally:
            conn.close()

    # Farmer operations
    def add_farmer(self, name, contact_number=None, location=None):
        """Add a new farmer to the database."""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO farmers (name, contact_number, location) 
        VALUES (%s, %s, %s)
        ''', (name, contact_number, location))
        
        farmer_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return farmer_id
    
    def get_farmers(self):
        """Get all farmers."""
        conn = self.connect()
        try:
            query = "SELECT * FROM farmers ORDER BY name"
            df = pd.read_sql(query, conn)
            return df
        except Exception as e:
            print(f"Error getting farmers: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def get_farmer(self, farmer_id):
        """Get a specific farmer's details."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM farmers WHERE farmer_id = %s", (farmer_id,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'farmer_id': result[0],
                    'name': result[1],
                    'contact_number': result[2],
                    'location': result[3],
                    'created_at': result[4]
                }
            return None
        finally:
            conn.close()

    def edit_farmer(self, farmer_id, name=None, contact_number=None, location=None):
        """Edit farmer details."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            updates = []
            params = []
            
            if name is not None:
                updates.append("name = %s")
                params.append(name)
            if contact_number is not None:
                updates.append("contact_number = %s")
                params.append(contact_number)
            if location is not None:
                updates.append("location = %s")
                params.append(location)
            
            if updates:
                query = f"UPDATE farmers SET {', '.join(updates)} WHERE farmer_id = %s"
                params.append(farmer_id)
                cursor.execute(query, params)
                success = cursor.rowcount > 0
                conn.commit()
                return success
            return False
        finally:
            conn.close()
    
    def delete_farmer(self, farmer_id, admin_id):
        """Delete a farmer. Only admin can delete farmers."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Check if the requesting user is admin
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (admin_id,))
            admin_role = cursor.fetchone()
            
            if not admin_role or admin_role[0] != 'admin':
                conn.close()
                return False
            
            # Check if farmer has any transactions
            cursor.execute("SELECT COUNT(*) FROM poultry_transactions WHERE farmer_id = %s", (farmer_id,))
            transaction_count = cursor.fetchone()[0]
            
            if transaction_count > 0:
                return False  # Cannot delete farmer with transactions
            
            cursor.execute("DELETE FROM farmers WHERE farmer_id = %s", (farmer_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success
        finally:
            conn.close()

    # Poultry Transaction operations
    def add_poultry_transaction(self, date, farmer_id, transaction_type, quantity, 
                              price_per_unit, vehicle_number=None, driver_name=None, notes=None,
                              payment_mode=None, payment_amount=0, payment_status="Unpaid"):
        """Add a new poultry transaction."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            print(f"Debug: Adding transaction with payment_mode={payment_mode}, payment_amount={payment_amount}, payment_status={payment_status}")
            
            total_amount = quantity * price_per_unit
            
            # Print the SQL query and parameters for debugging
            query = '''
            INSERT INTO poultry_transactions (
                date, farmer_id, transaction_type, quantity, price_per_unit,
                total_amount, vehicle_number, driver_name, notes,
                payment_mode, payment_amount, payment_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            params = (
                date, farmer_id, transaction_type, quantity, price_per_unit,
                total_amount, vehicle_number, driver_name, notes,
                payment_mode, payment_amount, payment_status
            )
            
            print("Debug: SQL Query:", query)
            print("Debug: Parameters:", params)
            
            cursor.execute(query, params)
            
            transaction_id = cursor.lastrowid
            print(f"Debug: Transaction ID after insert: {transaction_id}")
            
            conn.commit()
            return transaction_id
        except Exception as e:
            print(f"Error adding transaction: {str(e)}")
            print(f"Error type: {type(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_poultry_transactions(self, start_date=None, end_date=None, transaction_type=None):
        conn = self.connect()
        try:
            query = "SELECT * FROM poultry_transactions WHERE 1=1"
            params = []

            if transaction_type:
                query += " AND LOWER(transaction_type) = %s"
                params.append(transaction_type.lower())
            if start_date:
                query += " AND date >= %s"
                params.append(start_date)
            if end_date:
                query += " AND date <= %s"
                params.append(end_date)

            query += " ORDER BY date DESC, created_at DESC"

            print("Debug: Simple query:", query)
            print("Debug: Parameters:", params)

            df = pd.read_sql_query(query, conn, params=params)
            print(f"Debug: Found {len(df)} transactions")
            if not df.empty:
                print("Debug: First transaction:", tuple(df.iloc[0]))

                # Merge with farmer table for name/location
                farmers_df = pd.read_sql("SELECT farmer_id, name, location FROM farmers", conn)
                df = df.merge(farmers_df, on='farmer_id', how='left')
                df.rename(columns={'name': 'farmer_name', 'location': 'farmer_location'}, inplace=True)

            return df
        except Exception as e:
            print(f"Error fetching transactions: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    
    def get_transaction_summary(self, start_date=None, end_date=None):
        """Get summary of transactions between dates."""
        conn = self.connect()
        
        query = '''
        SELECT 
            t.*,
            f.name as supplier_name,
            f.contact_number as supplier_contact,
            f.location as supplier_location,
            COALESCE(s.total_sales, 0) as total_sales,
            COALESCE(s.total_sales, 0) - t.total_amount as profit_loss
        FROM poultry_transactions t
        JOIN farmers f ON t.farmer_id = f.farmer_id
        LEFT JOIN (
            SELECT 
                transaction_id,
                SUM(total_amount) as total_sales
            FROM poultry_transactions 
            WHERE transaction_type = 'sell'
            GROUP BY transaction_id
        ) s ON t.transaction_id = s.transaction_id
        WHERE t.transaction_type = 'buy'
        '''
        
        conditions = []
        params = []
        
        if start_date:
            conditions.append("t.date >= %s")
            params.append(start_date)
        
        if end_date:
            conditions.append("t.date <= %s")
            params.append(end_date)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY t.date DESC, t.created_at DESC"
        
        try:
            df = pd.read_sql(query, conn, params=params)
            return df
        except Exception as e:
            print(f"Error getting transaction summary: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def edit_transaction(self, transaction_id, admin_id, date=None, quantity=None, 
                        price_per_unit=None, vehicle_number=None, driver_name=None, notes=None):
        """Edit a transaction. Only admin can edit transactions."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Check if the requesting user is admin
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (admin_id,))
            admin_role = cursor.fetchone()
            
            if not admin_role or admin_role[0] != 'admin':
                conn.close()
                return False
            
            updates = []
            params = []
            
            if date is not None:
                updates.append("date = %s")
                params.append(date)
            if quantity is not None:
                updates.append("quantity = %s")
                params.append(quantity)
            if price_per_unit is not None:
                updates.append("price_per_unit = %s")
                params.append(price_per_unit)
                updates.append("total_amount = %s")
                params.append(quantity * price_per_unit if quantity is not None else cursor.execute("SELECT quantity FROM poultry_transactions WHERE transaction_id = %s", (transaction_id,)).fetchone()[0] * price_per_unit)
            if vehicle_number is not None:
                updates.append("vehicle_number = %s")
                params.append(vehicle_number)
            if driver_name is not None:
                updates.append("driver_name = %s")
                params.append(driver_name)
            if notes is not None:
                updates.append("notes = %s")
                params.append(notes)
            
            if updates:
                query = f"UPDATE poultry_transactions SET {', '.join(updates)} WHERE transaction_id = %s"
                params.append(transaction_id)
                cursor.execute(query, params)
                success = cursor.rowcount > 0
                conn.commit()
                return success
            return False
        finally:
            conn.close()

    def delete_user(self, user_id, admin_id):
        """Delete a user from the database. Only admin can delete users."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Check if the requesting user is admin
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (admin_id,))
            admin_role = cursor.fetchone()
            
            if not admin_role or admin_role[0] != 'admin':
                conn.close()
                return False
            
            # Check if trying to delete an admin
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
            user_role = cursor.fetchone()
            
            if user_role and user_role[0] == 'admin':
                conn.close()
                return False  # Cannot delete admin users
            
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success
        finally:
            conn.close()

    def delete_transaction(self, transaction_id, admin_id):
        """Delete a poultry transaction. Only admin can delete transactions."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Check if the requesting user is admin
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (admin_id,))
            admin_role = cursor.fetchone()
            
            if not admin_role or admin_role[0] != 'admin':
                conn.close()
                return False
            
            cursor.execute("DELETE FROM poultry_transactions WHERE transaction_id = %s", (transaction_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success
        finally:
            conn.close()

    def search_transactions(self, search_term, transaction_type=None):
        """Search transactions by farmer name, vehicle number, or notes."""
        conn = self.connect()
        
        query = '''
        SELECT 
            t.*,
            f.name as farmer_name,
            f.contact_number as farmer_contact,
            f.location as farmer_location
        FROM poultry_transactions t
        JOIN farmers f ON t.farmer_id = f.farmer_id
        WHERE (
            f.name LIKE %s OR
            t.vehicle_number LIKE %s OR
            t.driver_name LIKE %s OR
            t.notes LIKE %s
        )
        '''
        
        search_pattern = f"%{search_term}%"
        params = [search_pattern, search_pattern, search_pattern, search_pattern]
        
        if transaction_type:
            query += " AND t.transaction_type = %s"
            params.append(transaction_type)
        
        query += " ORDER BY t.date DESC, t.created_at DESC"
        
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    
    def get_all_inventory(self):
        """Get all inventory data with supplier details."""
        conn = self.connect()
        
        query = '''
        WITH total_stock AS (
            SELECT 
                COALESCE(SUM(CASE WHEN transaction_type = 'buy' THEN quantity ELSE 0 END), 0) as total_bought,
                COALESCE(SUM(CASE WHEN transaction_type = 'sell' THEN quantity ELSE 0 END), 0) as total_sold
            FROM poultry_transactions
        )
        SELECT 
            total_bought as total_buying_weight,
            total_sold as sold_weight,
            (total_bought - total_sold) as remaining_inventory
        FROM total_stock
        '''
        
        try:
            df = pd.read_sql(query, conn)
            if df.empty:
                return pd.DataFrame([{
                    'total_buying_weight': 0,
                    'sold_weight': 0,
                    'remaining_inventory': 0
                }])
            return df
        except Exception as e:
            print(f"Error getting inventory: {e}")
            return pd.DataFrame([{
                'total_buying_weight': 0,
                'sold_weight': 0,
                'remaining_inventory': 0
            }])
        finally:
            conn.close()

    def delete_transaction(self, transaction_id, admin_id):
        """Delete a transaction (admin only)."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Check if the requesting user is admin
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (admin_id,))
            admin_role = cursor.fetchone()
            
            if not admin_role or admin_role[0] != 'admin':
                conn.close()
                return False
            
            cursor.execute("DELETE FROM poultry_transactions WHERE transaction_id = %s", (transaction_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success
        finally:
            conn.close()

    def update_payment(self, transaction_id, payment_amount, payment_mode='Cash'):
        """Update payment details for a transaction."""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Get current transaction details
        cursor.execute('''
        SELECT total_amount, payment_amount 
        FROM poultry_transactions 
        WHERE transaction_id = %s
        ''', (transaction_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            raise ValueError("Transaction not found")
            
        total_amount, current_payment = result
        new_payment_amount = current_payment + payment_amount
        payment_status = "Fully Paid" if new_payment_amount >= total_amount else "Partially Paid"
        
        cursor.execute('''
        UPDATE poultry_transactions 
        SET payment_amount = %s,
            payment_mode = %s,
            payment_status = %s
        WHERE transaction_id = %s
        ''', (new_payment_amount, payment_mode, payment_status, transaction_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_payment_summary(self, farmer_id=None, start_date=None, end_date=None):
        """Get payment summary for transactions."""
        conn = self.connect()
        cursor = conn.cursor()
        
        query = '''
        SELECT 
            t.transaction_id,
            t.date,
            f.name as farmer_name,
            t.transaction_type,
            t.quantity,
            t.price_per_unit,
            t.total_amount,
            t.payment_amount,
            t.payment_mode,
            t.payment_status
        FROM poultry_transactions t
        JOIN farmers f ON t.farmer_id = f.farmer_id
        WHERE 1=1
        '''
        params = []
        
        if farmer_id:
            query += " AND t.farmer_id = %s"
            params.append(farmer_id)
        if start_date:
            query += " AND t.date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND t.date <= %s"
            params.append(end_date)
            
        query += " ORDER BY t.date DESC"
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        
        conn.close()
        
        if not results:
            return pd.DataFrame(columns=columns)
            
        return pd.DataFrame(results, columns=columns)

    def add_payment_history(self, transaction_id, payment_date, payment_amount, payment_mode, notes=None):
        """Add a payment history record and update the transaction's payment status."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # First get the transaction details
            cursor.execute('''
            SELECT total_amount, payment_amount 
            FROM poultry_transactions 
            WHERE transaction_id = %s
            ''', (transaction_id,))
            result = cursor.fetchone()
            
            if not result:
                raise ValueError("Transaction not found")
            
            total_amount, current_payment = result
            new_payment_amount = current_payment + payment_amount
            
            # Determine payment status
            payment_status = "Fully Paid" if new_payment_amount >= total_amount else "Partially Paid"
            
            # Add payment history record
            cursor.execute('''
            INSERT INTO payment_history (
                transaction_id, payment_date, payment_amount, 
                payment_mode, notes
            ) VALUES (%s, %s, %s, %s, %s)
            ''', (transaction_id, payment_date, payment_amount, payment_mode, notes))
            
            # Update transaction payment details
            cursor.execute('''
            UPDATE poultry_transactions 
            SET payment_amount = %s,
                payment_status = %s,
                payment_mode = %s
            WHERE transaction_id = %s
            ''', (new_payment_amount, payment_status, payment_mode, transaction_id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding payment history: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_payment_history(self, transaction_id):
        """Get payment history for a specific transaction."""
        conn = self.connect()
        
        query = '''
        SELECT 
            h.history_id,
            h.payment_date,
            h.payment_amount,
            h.payment_mode,
            h.notes,
            h.created_at,
            t.total_amount,
            t.transaction_type
        FROM payment_history h
        JOIN poultry_transactions t ON h.transaction_id = t.transaction_id
        WHERE h.transaction_id = %s
        ORDER BY h.payment_date DESC, h.created_at DESC
        '''
        
        try:
            df = pd.read_sql(query, conn, params=(transaction_id,))
            return df
        except Exception as e:
            print(f"Error getting payment history: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def _verify_database_setup(self):
        """Verify and fix database setup."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Start transaction
            conn.execute("BEGIN IMMEDIATE")
            
            # Check system_money table
            cursor.execute("SELECT COUNT(*) FROM system_money")
            if cursor.fetchone()[0] == 0:
                print("Debug: Initializing system_money table")
                cursor.execute("INSERT INTO system_money (total_amount) VALUES (0)")
            
            # Verify money_transactions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS money_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                proof_image BLOB,
                transaction_type TEXT NOT NULL,
                remaining_balance REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users (user_id),
                FOREIGN KEY (to_user_id) REFERENCES users (user_id)
            )
            """)
            
            # Commit changes
            conn.commit()
            print("Debug: Database setup verified and fixed")
            return True
            
        except Exception as e:
            print(f"Error verifying database setup: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def verify_and_fix_balances(self):
        """Verify and fix any inconsistencies in the database."""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            # Start transaction
            conn.execute("BEGIN IMMEDIATE")
            
            # Get all users
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            
            # Verify and fix system money
            cursor.execute("""
            SELECT COALESCE(SUM(CASE 
                WHEN to_user_id = 0 THEN amount 
                WHEN from_user_id = 0 THEN -amount 
                ELSE 0 
            END), 0)
            FROM money_transactions
            """)
            calculated_system_money = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT total_amount FROM system_money WHERE id = 1")
            current_system_money = cursor.fetchone()[0] or 0
            
            if calculated_system_money != current_system_money:
                print(f"Debug: Fixing system money from {current_system_money} to {calculated_system_money}")
                cursor.execute("""
                UPDATE system_money 
                SET total_amount = %s, 
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
                """, (calculated_system_money,))
            
            # Verify and fix user balances
            for user_id in users:
                user_id = user_id[0]
                cursor.execute('''
                SELECT COALESCE(SUM(CASE 
                    WHEN to_user_id = %s THEN amount 
                    WHEN from_user_id = %s THEN -amount 
                    ELSE 0 
                END), 0)
                FROM money_transactions
                ''', (user_id, user_id))
                calculated_balance = cursor.fetchone()[0] or 0
                
                # Update the last transaction's remaining balance
                cursor.execute("""
                UPDATE money_transactions 
                SET remaining_balance = %s
                WHERE transaction_id = (
                    SELECT transaction_id 
                    FROM money_transactions 
                    WHERE from_user_id = %s OR to_user_id = %s
                    ORDER BY date DESC, created_at DESC 
                    LIMIT 1
                )
                """, (calculated_balance, user_id, user_id))
            
            # Commit changes
            conn.commit()
            print("Debug: Database balances verified and fixed")
            return True
            
        except Exception as e:
            print(f"Error verifying and fixing balances: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


    def get_per_farmer_inventory(self):
            conn = self.connect()
            try:
                query = """
                SELECT
                    farmer_id,
                    SUM(CASE WHEN transaction_type = 'buy' THEN quantity ELSE 0 END) AS total_purchased,
                    SUM(CASE WHEN transaction_type = 'sell' THEN quantity ELSE 0 END) AS total_sold,
                    SUM(CASE WHEN transaction_type = 'buy' THEN quantity ELSE 0 END) -
                    SUM(CASE WHEN transaction_type = 'sell' THEN quantity ELSE 0 END) AS remaining_stock
                FROM poultry_transactions
                GROUP BY farmer_id
                """
                return pd.read_sql(query, conn)
            except Exception as e:
                print(f"Error in get_per_farmer_inventory: {e}")
                return pd.DataFrame()
            finally:
                conn.close()

    