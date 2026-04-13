import streamlit as st
from auth.auth_system import AuthSystem

def show_login_page(db_config):
    """Display login page"""
    
    st.set_page_config(
        page_title="QueryPulse-AI Login",
        page_icon="🔐",
        layout="centered"
    )
    
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h1 style='text-align: center; color: white;'>🔐 QueryPulse-AI</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: white;'>PostgreSQL Performance Optimizer</p>", unsafe_allow_html=True)
    
    auth = AuthSystem(db_config)
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                if email and password:
                    result = auth.login(email, password)
                    if result["success"]:
                        st.session_state["authenticated"] = True
                        st.session_state["user"] = result["user"]
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
                else:
                    st.warning("Please enter email and password")
        
        with col2:
            if st.button("Demo Login", use_container_width=True):
                result = auth.login("admin@example.com", "admin123")
                if result["success"]:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = result["user"]
                    st.rerun()
                else:
                    st.error("Demo login failed")
        
        st.info("💡 **Demo Credentials:** admin@example.com / admin123")
    
    with tab2:
        name = st.text_input("Full Name", key="reg_name")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_password")
        confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
        
        if st.button("Register", type="primary", use_container_width=True):
            if name and email and password:
                if password == confirm:
                    result = auth.register(name, email, password)
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        st.balloons()
                    else:
                        st.error(f"❌ {result['error']}")
                else:
                    st.error("Passwords don't match")
            else:
                st.warning("Please fill all fields")
    
    return False
