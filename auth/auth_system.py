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
            
            # Create users table if not exists - don't drop!
            agent.execute_query("""
                CREATE TABLE IF NOT EXISTS users (
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
            print("✅ Users table verified/created")
            
            # Check if admin exists
            result = agent.execute_query("""
                SELECT COUNT(*) as count FROM users WHERE email = 'admin@example.com'
            """)
            
            if result and result[0]['count'] == 0:
                # Create default admin (password: admin123)
                salt = secrets.token_hex(16)
                password_hash = hashlib.sha256(("admin123" + salt).encode()).hexdigest()
                agent.execute_query("""
                    INSERT INTO users (email, name, password_hash, salt, role)
                    VALUES (%s, %s, %s, %s, 'admin')
                """, ("admin@example.com", "Administrator", password_hash, salt))
                print("✅ Admin user created (admin@example.com / admin123)")
            else:
                print("✅ Admin user already exists")
            
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
                return {"success": False, "error": "User not found"}
            
            user = result[0]
            
            if self.verify_password(password, user['password_hash'], user['salt']):
                # Update last login
                agent.execute_query("""
                    UPDATE users SET last_login = NOW() 
                    WHERE email = %s
                """, (email,))
                
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
                return {"success": False, "error": "Invalid password"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def change_password(self, email, old_password, new_password):
        """Change user password"""
        try:
            agent = SQLAgent(self.db_config)
            
            # Verify old password first
            result = agent.execute_query("""
                SELECT password_hash, salt FROM users WHERE email = %s
            """, (email,))
            
            if not result:
                return {"success": False, "error": "User not found"}
            
            user = result[0]
            
            if not self.verify_password(old_password, user['password_hash'], user['salt']):
                return {"success": False, "error": "Old password is incorrect"}
            
            # Update to new password
            new_password_hash, new_salt = self.hash_password(new_password)
            agent.execute_query("""
                UPDATE users SET password_hash = %s, salt = %s 
                WHERE email = %s
            """, (new_password_hash, new_salt, email))
            
            return {"success": True, "message": "Password changed successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_by_email(self, email):
        """Get user information by email"""
        try:
            agent = SQLAgent(self.db_config)
            
            result = agent.execute_query("""
                SELECT id, email, name, role, created_at, last_login 
                FROM users 
                WHERE email = %s
            """, (email,))
            
            if result:
                return result[0]
            return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    def update_user_role(self, email, new_role):
        """Update user role (admin only)"""
        try:
            agent = SQLAgent(self.db_config)
            
            agent.execute_query("""
                UPDATE users SET role = %s 
                WHERE email = %s
            """, (new_role, email))
            
            return {"success": True, "message": f"User {email} role updated to {new_role}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_all_users(self):
        """Get all users (admin only)"""
        try:
            agent = SQLAgent(self.db_config)
            
            result = agent.execute_query("""
                SELECT id, email, name, role, created_at, last_login 
                FROM users 
                ORDER BY created_at DESC
            """)
            
            return result
        except Exception as e:
            print(f"Error getting users: {e}")
            return []
    
    def delete_user(self, email):
        """Delete a user (admin only)"""
        try:
            agent = SQLAgent(self.db_config)
            
            # Don't allow deleting the last admin
            admin_count = agent.execute_query("""
                SELECT COUNT(*) as count FROM users WHERE role = 'admin'
            """)
            
            if admin_count and admin_count[0]['count'] <= 1:
                user = self.get_user_by_email(email)
                if user and user['role'] == 'admin':
                    return {"success": False, "error": "Cannot delete the last admin user"}
            
            agent.execute_query("DELETE FROM users WHERE email = %s", (email,))
            
            return {"success": True, "message": f"User {email} deleted successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}
