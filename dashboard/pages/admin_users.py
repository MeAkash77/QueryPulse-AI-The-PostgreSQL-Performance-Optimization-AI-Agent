import streamlit as st
import pandas as pd
from datetime import datetime

def show_admin_users(auth_system):
    """Display all users for admin"""
    
    st.title("👥 User Management")
    st.markdown("View and manage all registered users")
    
    # Check if user is admin
    if st.session_state.get("user", {}).get("role") != "admin":
        st.error("❌ Access denied. Admin privileges required.")
        return
    
    # Get all users
    users = auth_system.get_all_users()
    
    if not users:
        st.info("No users found in the system")
        return
    
    # Convert to DataFrame for better display
    df = pd.DataFrame(users)
    
    # Format dates
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    if 'last_login' in df.columns:
        df['last_login'] = pd.to_datetime(df['last_login']).dt.strftime('%Y-%m-%d %H:%M')
        df['last_login'] = df['last_login'].fillna('Never')
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Users", len(users))
    with col2:
        admin_count = len([u for u in users if u.get('role') == 'admin'])
        st.metric("Admins", admin_count)
    with col3:
        viewer_count = len([u for u in users if u.get('role') == 'viewer'])
        st.metric("Viewers", viewer_count)
    with col4:
        developer_count = len([u for u in users if u.get('role') == 'developer'])
        st.metric("Developers", developer_count)
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📋 All Users", "➕ Add User", "⚙️ Manage Roles"])
    
    with tab1:
        st.subheader("All Registered Users")
        
        # Display users table
        display_cols = ['id', 'email', 'name', 'role', 'created_at', 'last_login']
        available_cols = [col for col in display_cols if col in df.columns]
        
        st.dataframe(
            df[available_cols],
            column_config={
                "id": "ID",
                "email": "Email",
                "name": "Name",
                "role": st.column_config.SelectboxColumn(
                    "Role",
                    options=["admin", "developer", "viewer"],
                    help="User role"
                ),
                "created_at": "Joined",
                "last_login": "Last Active"
            },
            use_container_width=True
        )
        
        # User details expander
        st.subheader("📊 User Details")
        for user in users:
            with st.expander(f"📧 {user['email']} - {user['name']} ({user['role']})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**ID:** {user['id']}")
                    st.write(f"**Email:** {user['email']}")
                    st.write(f"**Name:** {user['name']}")
                with col2:
                    st.write(f"**Role:** {user['role']}")
                    st.write(f"**Joined:** {user.get('created_at', 'N/A')}")
                    st.write(f"**Last Login:** {user.get('last_login', 'Never')}")
    
    with tab2:
        st.subheader("➕ Add New User")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_name = st.text_input("Full Name", key="new_name")
            new_email = st.text_input("Email", key="new_email")
        
        with col2:
            new_password = st.text_input("Password", type="password", key="new_password")
            new_role = st.selectbox("Role", ["viewer", "developer", "admin"], key="new_role")
        
        if st.button("➕ Create User", type="primary"):
            if new_name and new_email and new_password:
                result = auth_system.register(new_name, new_email, new_password)
                if result["success"]:
                    # Update role if not viewer
                    if new_role != "viewer":
                        auth_system.update_user_role(new_email, new_role)
                    st.success(f"✅ User {new_email} created successfully!")
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
            else:
                st.warning("Please fill all fields")
    
    with tab3:
        st.subheader("⚙️ Manage User Roles")
        
        # Select user to manage
        user_options = {f"{u['email']} ({u['name']})": u['email'] for u in users}
        selected_user_display = st.selectbox("Select User", list(user_options.keys()))
        selected_user_email = user_options[selected_user_display]
        
        # Get current user
        current_user = next((u for u in users if u['email'] == selected_user_email), None)
        
        if current_user:
            st.write(f"**Current Role:** {current_user['role']}")
            
            new_role = st.selectbox(
                "New Role",
                ["viewer", "developer", "admin"],
                index=["viewer", "developer", "admin"].index(current_user['role']) if current_user['role'] in ["viewer", "developer", "admin"] else 0
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 Update Role"):
                    if selected_user_email == st.session_state['user']['email'] and new_role != current_user['role']:
                        st.warning("⚠️ You are changing your own role. Some features may change.")
                    
                    result = auth_system.update_user_role(selected_user_email, new_role)
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
            
            with col2:
                if st.button("🗑️ Delete User", type="secondary"):
                    if selected_user_email == st.session_state['user']['email']:
                        st.error("❌ You cannot delete yourself")
                    else:
                        result = auth_system.delete_user(selected_user_email)
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {result['error']}")

def show_login_activity(auth_system):
    """Show user login activity"""
    
    st.subheader("📈 Login Activity")
    
    users = auth_system.get_all_users()
    
    if users:
        # Create activity data
        activity_data = []
        for user in users:
            activity_data.append({
                "User": user['email'],
                "Name": user['name'],
                "Role": user['role'],
                "Last Login": user.get('last_login', 'Never'),
                "Joined": user.get('created_at', 'N/A')
            })
        
        df = pd.DataFrame(activity_data)
        
        # Show recent logins
        st.markdown("### 🕐 Recent User Activity")
        st.dataframe(df, use_container_width=True)
        
        # Stats
        total_logins = len([u for u in users if u.get('last_login')])
        st.info(f"📊 **Total Active Users:** {total_logins} out of {len(users)} users have logged in")