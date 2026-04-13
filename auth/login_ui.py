import streamlit as st
from auth.auth_system import AuthSystem

def show_login_page(db_config):
    """Display beautiful login/register page"""
    
    # Page config
    st.set_page_config(
        page_title="QueryPulse-AI Login",
        page_icon="🔐",
        layout="centered"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        }
        .main-header {
            text-align: center;
            color: white;
            padding: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
        <div class="main-header">
            <h1>🔐 QueryPulse-AI</h1>
            <p>PostgreSQL Performance Optimizer</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialize auth system
    auth = AuthSystem(db_config)
    
    # Create tabs
    tab1, tab2 = st.tabs(["📝 Login", "📋 Register"])
    
    with tab1:
        st.markdown("### Welcome Back!")
        
        email = st.text_input("📧 Email", placeholder="admin@example.com", key="login_email")
        password = st.text_input("🔒 Password", type="password", placeholder="Enter your password", key="login_password")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔓 Login", type="primary", use_container_width=True):
                if email and password:
                    result = auth.login(email, password)
                    if result["success"]:
                        st.session_state["authenticated"] = True
                        st.session_state["user"] = result["user"]
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
                else:
                    st.warning("⚠️ Please enter email and password")
        
        with col2:
            if st.button("👤 Demo Login", use_container_width=True):
                result = auth.login("admin@example.com", "admin123")
                if result["success"]:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = result["user"]
                    st.rerun()
        
        st.info("💡 **Demo Credentials:** admin@example.com / admin123")
    
    with tab2:
        st.markdown("### Create New Account")
        
        name = st.text_input("👤 Full Name", placeholder="John Doe", key="reg_name")
        email = st.text_input("📧 Email", placeholder="you@example.com", key="reg_email")
        password = st.text_input("🔒 Password", type="password", placeholder="Choose a strong password", key="reg_password")
        confirm_password = st.text_input("✓ Confirm Password", type="password", placeholder="Confirm your password", key="reg_confirm")
        
        if st.button("📝 Register", type="primary", use_container_width=True):
            if name and email and password:
                if password == confirm_password:
                    result = auth.register(name, email, password)
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        st.balloons()
                    else:
                        st.error(f"❌ {result['error']}")
                else:
                    st.error("❌ Passwords do not match")
            else:
                st.warning("⚠️ Please fill all fields")
    
    return False