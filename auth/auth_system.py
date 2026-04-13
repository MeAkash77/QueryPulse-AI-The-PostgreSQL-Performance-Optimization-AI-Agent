import streamlit as st
import hashlib
import secrets
from sql.sql_agent import SQLAgent

class AuthSystem:
    def __init__(self, db_config):
        self.db_config = db_config
        if not hasattr(AuthSystem, '_tables_created'):
            self._init_db()
            AuthSystem._tables_created = True
    
    def _init_db(self):
        """Initialize database tables"""
        try:
            agent = SQLAgent(self.db_config)
            
            # Create table if not exists
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
            
            # Check if admin exists
            result = agent.execute_query("SELECT COUNT(*) as count FROM users WHERE email = 'admin@example.com'")
            
            if result and result[0]['count'] == 0:
                # Create admin with correct hash
                agent.execute_query("""
                    INSERT INTO users (email, name, password_hash, salt, role)
                    VALUES (%s, %s, %s, %s, 'admin')
                """, ("admin@example.com", "Administrator", 
                      "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918", 
                      "fixed_salt_123"))
                print("✅ Admin user created")
            
            return True
        except Exception as e:
            print(f"DB init error: {e}")
            return False
    
    def hash_password(self, password, salt=None):
        """Hash password with salt"""
        if not salt:
            salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash, salt
    
    def verify_password(self, password, stored_hash, salt):
        """Verify password"""
        computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return computed_hash == stored_hash
    
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
                return {"success": False, "error": f"User '{email}' not found"}
            
            user = result[0]
            
            # Verify password
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
