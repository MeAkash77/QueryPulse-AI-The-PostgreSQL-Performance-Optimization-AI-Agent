import streamlit as st
import hashlib
from sql.sql_agent import SQLAgent

class AuthSystem:
    def __init__(self, db_config):
        self.db_config = db_config
        self._init_db()
    
    def _init_db(self):
        try:
            agent = SQLAgent(self.db_config)
            
            # Create table
            agent.execute_query("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Check if admin exists
            result = agent.execute_query("SELECT COUNT(*) as count FROM users WHERE email = 'admin@example.com'")
            
            if result and result[0]['count'] == 0:
                # Insert admin with correct hash
                agent.execute_query("""
                    INSERT INTO users (email, name, password_hash, salt, role)
                    VALUES (%s, %s, %s, %s, 'admin')
                """, (
                    "admin@example.com", 
                    "Administrator",
                    "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
                    "fixed_salt_123"
                ))
                print("✅ Admin created")
            
            return True
        except Exception as e:
            print(f"Init error: {e}")
            return False
    
    def login(self, email, password):
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
            
            # Compute hash with stored salt
            computed_hash = hashlib.sha256((password + user['salt']).encode()).hexdigest()
            
            # Compare
            if computed_hash == user['password_hash']:
                return {
                    "success": True,
                    "user": {
                        "id": user['id'],
                        "email": user['email'],
                        "name': user['name'],
                        "role": user['role']
                    }
                }
            else:
                return {"success": False, "error": "Invalid password"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def register(self, name, email, password):
        try:
            agent = SQLAgent(self.db_config)
            
            # Check if exists
            existing = agent.execute_query("SELECT COUNT(*) as count FROM users WHERE email = %s", (email,))
            if existing and existing[0]['count'] > 0:
                return {"success": False, "error": "Email already registered"}
            
            # Create new user with hash
            import secrets
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            
            agent.execute_query("""
                INSERT INTO users (email, name, password_hash, salt, role)
                VALUES (%s, %s, %s, %s, 'viewer')
            """, (email, name, password_hash, salt))
            
            return {"success": True, "message": "Registration successful!"}
        except Exception as e:
            return {"success": False, "error": str(e)}
