import streamlit as st
import hashlib
import secrets
from sql.sql_agent import SQLAgent
from datetime import datetime

class AuthSystem:
    def __init__(self, db_config):
        self.db_config = db_config
        # Only create tables once
        if not hasattr(AuthSystem, '_tables_created'):
            self._create_tables()
            AuthSystem._tables_created = True
    
    def _create_tables(self):
        """Create authentication tables in your database (only once)"""
        try:
            agent = SQLAgent(self.db_config)
            
            # Check if table exists first
            result = agent.execute_query("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'users'
                )
            """)
            
            table_exists = result[0]['exists'] if result else False
            
            if not table_exists:
                # Create users table
                agent.execute_query("""
                    CREATE TABLE users (
                        id SERIAL PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        name TEXT,
                        password_hash TEXT NOT NULL,
                        salt TEXT NOT NULL,
                        role TEXT DEFAULT 'viewer',
                        created_at TIMESTAMP DEFAULT NOW(),
                        last_login TIMESTAMP
                    )
                """)
                print("✅ Users table created")
                
                # Create default admin (password: admin123)
                salt = secrets.token_hex(16)
                password_hash = hashlib.sha256(("admin123" + salt).encode()).hexdigest()
                agent.execute_query("""
                    INSERT INTO users (email, name, password_hash, salt, role)
                    VALUES (%s, %s, %s, %s, 'admin')
                """, ("admin@example.com", "Administrator", password_hash, salt))
                print("✅ Admin user created (admin@example.com / admin123)")
            
            # Create login_activity table
            activity_result = agent.execute_query("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'login_activity'
                )
            """)
            
            activity_exists = activity_result[0]['exists'] if activity_result else False
            
            if not activity_exists:
                agent.execute_query("""
                    CREATE TABLE login_activity (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        email TEXT,
                        login_time TIMESTAMP DEFAULT NOW(),
                        ip_address TEXT,
                        user_agent TEXT,
                        status TEXT
                    )
                """)
                print("✅ Login activity table created")
            
            return True
        except Exception as e:
            print(f"Table creation error: {e}")
            return False
    
    def hash_password(self, password):
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash, salt
    
    def verify_password(self, password, stored_hash, salt):
        """Verify password"""
        computed = hashlib.sha256((password + salt).encode()).hexdigest()
        return computed == stored_hash
    
    def register(self, name, email, password):
        """Register a new user"""
        try:
            agent = SQLAgent(self.db_config)
            
            # Check if user exists
            existing = agent.execute_query("SELECT COUNT(*) as count FROM users WHERE email = %s", (email,))
            
            if existing and existing[0]['count'] > 0:
                return {"success": False, "error": "Email already registered"}
            
            # Create new user
            password_hash, salt = self.hash_password(password)
            agent.execute_query("""
                INSERT INTO users (email, name, password_hash, salt, role)
                VALUES (%s, %s, %s, %s, 'viewer')
            """, (email, name, password_hash, salt))
            
            return {"success": True, "message": "Registration successful! Please login."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def login(self, email, password):
        """Login user"""
        try:
            agent = SQLAgent(self.db_config)
            
            result = agent.execute_query("""
                SELECT id, email, name, password_hash, salt, role 
                FROM users 
                WHERE email = %s
            """, (email,))
            
            if not result:
                # Log failed login attempt
                self._log_activity(None, email, None, None, "failed")
                return {"success": False, "error": "User not found"}
            
            user = result[0]
            
            if self.verify_password(password, user['password_hash'], user['salt']):
                # Update last login timestamp
                agent.execute_query("""
                    UPDATE users SET last_login = NOW() 
                    WHERE email = %s
                """, (email,))
                
                # Log successful login
                self._log_activity(user['id'], email, None, None, "success")
                
                return {
                    "success": True,
                    "user": {
                        "id": user['id'],
                        "email": user['email'],
                        "name": user['name'],
                        "role": user['role']
                    }
                }
            else:
                # Log failed login attempt
                self._log_activity(user['id'], email, None, None, "failed")
                return {"success": False, "error": "Invalid password"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _log_activity(self, user_id, email, ip_address=None, user_agent=None, status="success"):
        """Log login activity"""
        try:
            agent = SQLAgent(self.db_config)
            agent.execute_query("""
                INSERT INTO login_activity (user_id, email, ip_address, user_agent, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, email, ip_address, user_agent, status))
        except Exception as e:
            print(f"Failed to log activity: {e}")
    
    def get_login_activity(self, limit=50):
        """Get recent login activity"""
        try:
            agent = SQLAgent(self.db_config)
            result = agent.execute_query("""
                SELECT 
                    la.id,
                    la.email,
                    la.login_time,
                    la.ip_address,
                    la.user_agent,
                    la.status,
                    u.name as user_name
                FROM login_activity la
                LEFT JOIN users u ON la.user_id = u.id
                ORDER BY la.login_time DESC
                LIMIT %s
            """, (limit,))
            return result
        except Exception as e:
            print(f"Failed to get login activity: {e}")
            return []
    
    def get_all_users(self):
        """Get all users"""
        try:
            agent = SQLAgent(self.db_config)
            result = agent.execute_query("""
                SELECT id, email, name, role, created_at, last_login
                FROM users
                ORDER BY created_at DESC
            """)
            return result
        except Exception as e:
            print(f"Failed to get users: {e}")
            return []
    
    def update_user_role(self, user_id, new_role):
        """Update user role"""
        try:
            agent = SQLAgent(self.db_config)
            agent.execute_query("""
                UPDATE users SET role = %s
                WHERE id = %s
            """, (new_role, user_id))
            return {"success": True, "message": "User role updated"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_user(self, user_id):
        """Delete a user"""
        try:
            agent = SQLAgent(self.db_config)
            agent.execute_query("DELETE FROM users WHERE id = %s", (user_id,))
            return {"success": True, "message": "User deleted successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def change_password(self, user_id, old_password, new_password):
        """Change user password"""
        try:
            agent = SQLAgent(self.db_config)
            
            # Get current user
            result = agent.execute_query("""
                SELECT password_hash, salt FROM users WHERE id = %s
            """, (user_id,))
            
            if not result:
                return {"success": False, "error": "User not found"}
            
            user = result[0]
            
            # Verify old password
            if not self.verify_password(old_password, user['password_hash'], user['salt']):
                return {"success": False, "error": "Current password is incorrect"}
            
            # Update to new password
            new_hash, new_salt = self.hash_password(new_password)
            agent.execute_query("""
                UPDATE users SET password_hash = %s, salt = %s
                WHERE id = %s
            """, (new_hash, new_salt, user_id))
            
            return {"success": True, "message": "Password changed successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}