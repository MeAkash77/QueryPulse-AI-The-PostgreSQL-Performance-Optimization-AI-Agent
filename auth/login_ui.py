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
    
    # Custom CSS for better styling
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
        .stButton > button {
            width: 100%;
            border-radius: 8px;
            font-weight: bold;
        }
        .stTextInput > div > div > input {
            border-radius: 8px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 2rem;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 1.2rem;
            font-weight: bold;
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
                    with st.spinner("Logging in..."):
                        result = auth.login(email, password)
                        if result["success"]:
                            st.session_state["authenticated"] = True
                            st.session_state["user"] = result["user"]
                            st.success(f"✅ Welcome back, {result['user']['name']}!")
                            st.rerun()
                        else:
                            st.error(f"❌ {result['error']}")
                else:
                    st.warning("⚠️ Please enter email and password")
        
        with col2:
            if st.button("👤 Demo Login", use_container_width=True):
                with st.spinner("Logging in with demo account..."):
                    result = auth.login("admin@example.com", "admin123")
                    if result["success"]:
                        st.session_state["authenticated"] = True
                        st.session_state["user"] = result["user"]
                        st.success("✅ Demo login successful!")
                        st.rerun()
                    else:
                        st.error(f"❌ Demo login failed: {result['error']}")
        
        st.info("💡 **Demo Credentials:** admin@example.com / admin123")
        
        # Add password reset hint
        st.caption("🔒 Forgot password? Contact your administrator.")
    
    with tab2:
        st.markdown("### Create New Account")
        
        name = st.text_input("👤 Full Name", placeholder="John Doe", key="reg_name")
        email = st.text_input("📧 Email", placeholder="you@example.com", key="reg_email")
        password = st.text_input("🔒 Password", type="password", placeholder="Choose a strong password", key="reg_password")
        confirm_password = st.text_input("✓ Confirm Password", type="password", placeholder="Confirm your password", key="reg_confirm")
        
        # Password strength indicator
        if password:
            strength = "Weak"
            color = "red"
            if len(password) >= 8:
                strength = "Good"
                color = "orange"
            if len(password) >= 8 and any(c.isdigit() for c in password) and any(c.isupper() for c in password):
                strength = "Strong"
                color = "green"
            st.markdown(f"<span style='color:{color}'>Password strength: {strength}</span>", unsafe_allow_html=True)
        
        if st.button("📝 Register", type="primary", use_container_width=True):
            if name and email and password:
                if password == confirm_password:
                    with st.spinner("Creating your account..."):
                        result = auth.register(name, email, password)
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                            st.balloons()
                            st.info("🔐 Please login with your new credentials")
                            # Clear form after successful registration
                            st.rerun()
                        else:
                            st.error(f"❌ {result['error']}")
                else:
                    st.error("❌ Passwords do not match")
            else:
                st.warning("⚠️ Please fill all fields")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: gray; font-size: 0.8rem;'>"
        "🔧 QueryPulse-AI | AI-Powered Database Performance Optimization<br>"
        "© 2024 | Supports PostgreSQL, MySQL, and MongoDB"
        "</p>", 
        unsafe_allow_html=True
    )
    
    return False
