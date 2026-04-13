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