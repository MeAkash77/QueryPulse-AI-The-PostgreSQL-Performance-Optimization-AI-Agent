import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
import jwt
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class AuthManager:
    def __init__(self, sql_agent):
        self.sql_agent = sql_agent
    
    def hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        return f"{salt}:{hashlib.sha256((password + salt).encode()).hexdigest()}"
    
    def verify_password(self, password: str, hashed: str) -> bool:
        salt, hash_value = hashed.split(":")
        return hash_value == hashlib.sha256((password + salt).encode()).hexdigest()
    
    def create_user(self, email: str, password: str, tenant_id: str) -> Dict:
        hashed = self.hash_password(password)
        
        try:
            self.sql_agent.execute_query("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE,
                    password_hash TEXT,
                    tenant_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            self.sql_agent.execute_query("""
                INSERT INTO users (email, password_hash, tenant_id)
                VALUES (%s, %s, %s)
            """, (email, hashed, tenant_id))
            
            return {"success": True, "message": "User created"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def authenticate(self, email: str, password: str) -> Optional[str]:
        result = self.sql_agent.execute_query("""
            SELECT password_hash, tenant_id FROM users WHERE email = %s AND is_active = TRUE
        """, (email,))
        
        if not result:
            return None
        
        user = result[0]
        if self.verify_password(password, user["password_hash"]):
            token = self._create_access_token({"sub": email, "tenant_id": user["tenant_id"]})
            return token
        
        return None
    
    def _create_access_token(self, data: Dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)