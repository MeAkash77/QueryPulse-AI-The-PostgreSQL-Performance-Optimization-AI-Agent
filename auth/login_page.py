import streamlit as st
import hashlib
import secrets
from sql.sql_agent import SQLAgent

def init_auth_tables(db_config):
    """Create authentication tables in your Neon database"""
    try:
        agent = SQLAgent(db_config)
        
        # Create users table
        agent.execute_query("""
            CREATE TABLE IF NOT EXISTS auth_users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT DEFAULT 'viewer',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Check if admin exists
        result = agent.execute_query("SELECT COUNT(*) as count FROM auth_users WHERE email = 'admin@example.com'")
        
        if result[0]['count'] == 0:
            # Create default admin user (password: admin123)
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256(("admin123" + salt).encode()).hexdigest()
            agent.execute_query("""
                INSERT INTO auth_users (email, password_hash, salt, role)
                VALUES (%s, %s, %s, 'admin')
            """, ("admin@example.com", password_hash, salt))
            print("✅ Admin user created")
        
        return True
    except Exception as e:
        st.error(f"Failed to init auth: {e}")
        return False

def verify_password(password, stored_hash, salt):
    """Verify password"""
    computed = hashlib.sha256((password + salt).encode()).hexdigest()
    return computed == stored_hash

def show_login_page(db_config):
    """Display login page"""
    
    # Initialize auth tables
    init_auth_tables(db_config)
    
    st.set_page_config(page_title="QueryPulse-AI Login", layout="centered")
    
    st.title("🔐 QueryPulse-AI")
    st.markdown("### PostgreSQL Performance Optimizer")
    
    # Simple tabs
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                if email and password:
                    try:
                        agent = SQLAgent(db_config)
                        result = agent.execute_query(
                            "SELECT password_hash, salt, role FROM auth_users WHERE email = %s",
                            (email,)
                        )
                        
                        if result and verify_password(password, result[0]['password_hash'], result[0]['salt']):
                            st.session_state["logged_in"] = True
                            st.session_state["user_email"] = email
                            st.session_state["user_role"] = result[0]['role']
                            st.rerun()
                        else:
                            st.error("Invalid email or password")
                    except Exception as e:
                        st.error(f"Login error: {e}")
                else:
                    st.warning("Please enter email and password")
        
        with col2:
            if st.button("Demo Login", use_container_width=True):
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = "demo@example.com"
                st.session_state["user_role"] = "viewer"
                st.rerun()
        
        st.info("Demo: admin@example.com / admin123")
    
    with tab2:
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        reg_confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
        
        if st.button("Register", type="primary", use_container_width=True):
            if reg_email and reg_password:
                if reg_password == reg_confirm:
                    try:
                        agent = SQLAgent(db_config)
                        
                        # Check if user exists
                        existing = agent.execute_query("SELECT COUNT(*) as count FROM auth_users WHERE email = %s", (reg_email,))
                        
                        if existing[0]['count'] > 0:
                            st.error("User already exists")
                        else:
                            # Create new user
                            salt = secrets.token_hex(16)
                            password_hash = hashlib.sha256((reg_password + salt).encode()).hexdigest()
                            agent.execute_query("""
                                INSERT INTO auth_users (email, password_hash, salt, role)
                                VALUES (%s, %s, %s, 'viewer')
                            """, (reg_email, password_hash, salt))
                            st.success("Registration successful! Please login.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Registration error: {e}")
                else:
                    st.error("Passwords don't match")
            else:
                st.warning("Please fill all fields")
    
    return False