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
        
        if available_cols:
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
            with st.expander(f"📧 {user['email']} - {user.get('name', 'No name')} ({user.get('role', 'viewer')})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**ID:** {user.get('id', 'N/A')}")
                    st.write(f"**Email:** {user.get('email', 'N/A')}")
                    st.write(f"**Name:** {user.get('name', 'N/A')}")
                with col2:
                    st.write(f"**Role:** {user.get('role', 'viewer')}")
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
                # Check if email already exists
                existing_users = auth_system.get_all_users()
                if existing_users and any(u.get('email') == new_email for u in existing_users):
                    st.error(f"❌ User with email {new_email} already exists")
                else:
                    result = auth_system.register(new_name, new_email, new_password)
                    if result["success"]:
                        # Update role if not viewer
                        if new_role != "viewer":
                            role_result = auth_system.update_user_role(new_email, new_role)
                            if role_result["success"]:
                                st.success(f"✅ User {new_email} created with role {new_role}!")
                            else:
                                st.warning(f"User created but role update failed: {role_result['error']}")
                        else:
                            st.success(f"✅ User {new_email} created successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
            else:
                st.warning("Please fill all fields")
    
    with tab3:
        st.subheader("⚙️ Manage User Roles")
        
        # Select user to manage
        user_options = {f"{u['email']} ({u.get('name', 'No name')})": u['email'] for u in users}
        
        if user_options:
            selected_user_display = st.selectbox("Select User", list(user_options.keys()))
            selected_user_email = user_options[selected_user_display]
            
            # Get current user
            current_user = next((u for u in users if u['email'] == selected_user_email), None)
            
            if current_user:
                st.write(f"**Current Role:** {current_user.get('role', 'viewer')}")
                
                # Get current role index
                role_options = ["viewer", "developer", "admin"]
                current_role = current_user.get('role', 'viewer')
                current_index = role_options.index(current_role) if current_role in role_options else 0
                
                new_role = st.selectbox(
                    "New Role",
                    role_options,
                    index=current_index
                )
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔄 Update Role"):
                        if selected_user_email == st.session_state.get('user', {}).get('email') and new_role != current_role:
                            st.warning("⚠️ You are changing your own role. Some features may change.")
                        
                        result = auth_system.update_user_role(selected_user_email, new_role)
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {result.get('error', 'Failed to update role')}")
                
                with col2:
                    if st.button("🗑️ Delete User", type="secondary"):
                        if selected_user_email == st.session_state.get('user', {}).get('email'):
                            st.error("❌ You cannot delete yourself")
                        else:
                            # Check if this is the last admin
                            admin_users = [u for u in users if u.get('role') == 'admin']
                            if current_user.get('role') == 'admin' and len(admin_users) <= 1:
                                st.error("❌ Cannot delete the last admin user")
                            else:
                                result = auth_system.delete_user(selected_user_email)
                                if result.get("success", False):
                                    st.success(f"✅ {result['message']}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result.get('error', 'Failed to delete user')}")
        else:
            st.info("No users available to manage")

def show_login_activity(auth_system):
    """Show user login activity"""
    
    st.subheader("📈 Login Activity Log")
    st.markdown("Track user login history and system access")
    
    # Get all users
    users = auth_system.get_all_users()
    
    if users:
        # Create activity data
        activity_data = []
        for user in users:
            # Get login activity for this user
            login_activity = auth_system.get_login_activity(limit=100)
            
            # Filter activity for this user
            user_activity = [act for act in login_activity if act.get('email') == user['email']] if login_activity else []
            
            if user_activity:
                for activity in user_activity[:5]:  # Show last 5 activities per user
                    activity_data.append({
                        "User": user['email'],
                        "Name": user.get('name', 'N/A'),
                        "Role": user.get('role', 'viewer'),
                        "Login Time": activity.get('login_time', 'N/A'),
                        "Status": activity.get('status', 'unknown'),
                        "IP Address": activity.get('ip_address', 'N/A')
                    })
            else:
                # User with no login activity
                activity_data.append({
                    "User": user['email'],
                    "Name": user.get('name', 'N/A'),
                    "Role": user.get('role', 'viewer'),
                    "Login Time": "Never logged in",
                    "Status": "inactive",
                    "IP Address": "N/A"
                })
        
        if activity_data:
            df = pd.DataFrame(activity_data)
            
            # Show recent logins
            st.markdown("### 🕐 User Login Activity")
            
            # Color code status
            def color_status(val):
                if val == 'success':
                    return 'background-color: #90EE90'
                elif val == 'failed':
                    return 'background-color: #FFB6C1'
                elif val == 'inactive':
                    return 'background-color: #FFE4B5'
                return ''
            
            st.dataframe(
                df,
                column_config={
                    "User": "Email",
                    "Name": "Name",
                    "Role": "Role",
                    "Login Time": "Last Login",
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["success", "failed", "inactive", "unknown"],
                        help="Login status"
                    ),
                    "IP Address": "IP Address"
                },
                use_container_width=True
            )
            
            # Stats
            total_logins = len([u for u in users if u.get('last_login')])
            active_users = len([u for u in users if u.get('last_login') and pd.to_datetime(u.get('last_login')) > pd.Timestamp.now() - pd.Timedelta(days=30)])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Users", len(users))
            with col2:
                st.metric("Users Who Logged In", total_logins)
            with col3:
                st.metric("Active Users (30 days)", active_users)
            
            # Summary chart
            st.markdown("### 📊 Login Summary")
            
            # Count by role
            role_counts = {}
            for user in users:
                role = user.get('role', 'viewer')
                role_counts[role] = role_counts.get(role, 0) + 1
            
            if role_counts:
                st.bar_chart(role_counts)
            
            # Recent successful logins
            st.markdown("### ✅ Recent Successful Logins")
            recent_success = [act for act in activity_data if act.get('Status') == 'success']
            if recent_success:
                st.dataframe(pd.DataFrame(recent_success[:10]), use_container_width=True)
            else:
                st.info("No successful logins recorded recently")
            
            # Failed login attempts
            st.markdown("### ❌ Failed Login Attempts")
            failed_logins = [act for act in activity_data if act.get('Status') == 'failed']
            if failed_logins:
                st.warning(f"⚠️ {len(failed_logins)} failed login attempts detected")
                st.dataframe(pd.DataFrame(failed_logins), use_container_width=True)
            else:
                st.success("✅ No failed login attempts recorded")
        
        else:
            st.info("No login activity recorded yet")
    else:
        st.info("No users found in the system")

# Optional: Add a function to show current session info
def show_session_info(auth_system):
    """Display current user session information"""
    st.subheader("🔐 Current Session Information")
    
    if st.session_state.get("authenticated"):
        user = st.session_state.get("user", {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Logged in as:** {user.get('email', 'Unknown')}")
            st.write(f"**Name:** {user.get('name', 'N/A')}")
        with col2:
            st.write(f"**Role:** {user.get('role', 'viewer')}")
            st.write(f"**Session Started:** {st.session_state.get('login_time', 'Unknown')}")
        
        # Option to change password
        st.markdown("---")
        st.markdown("### 🔒 Change Password")
        
        with st.form("change_password_form"):
            old_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Change Password"):
                if new_password != confirm_password:
                    st.error("❌ New passwords do not match")
                elif len(new_password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                else:
                    result = auth_system.change_password(user.get('email'), old_password, new_password)
                    if result.get("success"):
                        st.success("✅ Password changed successfully!")
                    else:
                        st.error(f"❌ {result.get('error', 'Failed to change password')}")
    else:
        st.warning("Not authenticated")
