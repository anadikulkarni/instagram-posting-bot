import streamlit as st
from db.utils import SessionLocal
from db.models import User, UserRole
from utils.auth import require_auth, logout_button, require_role, hash_password

st.set_page_config(page_title="User Management", page_icon="👥")

# Require authentication and admin role
require_auth()
require_role("admin")
logout_button()

st.title("👥 User Management")
st.caption("Admin Only - Manage user accounts and permissions")

# Get current users
db = SessionLocal()
users = db.query(User).order_by(User.created_at.desc()).all()
db.close()

# Display statistics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Users", len(users))
with col2:
    active_users = len([u for u in users if getattr(u, "is_active", False)])
    st.metric("Active Users", active_users)
with col3:
    admin_users = len([u for u in users if getattr(u, "role", None) == UserRole.ADMIN])
    st.metric("Admins", admin_users)

st.markdown("---")

# Create new user
st.subheader("➕ Create New User")

with st.form("create_user_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        new_username = st.text_input("Username", key="new_username")
        new_password = st.text_input("Password", type="password", key="new_password")
    
    with col2:
        new_role = st.selectbox("Role", options=["intern", "admin"], key="new_role")
        new_active = st.checkbox("Active", value=True, key="new_active")
    
    if st.form_submit_button("Create User", use_container_width=True):
        if not new_username or not new_password:
            st.error("❌ Username and password are required")
        elif len(new_password) < 6:
            st.error("❌ Password must be at least 6 characters")
        else:
            db = SessionLocal()
            try:
                # Check if username exists
                existing = db.query(User).filter_by(username=new_username).first()
                if existing:
                    st.error(f"❌ Username '{new_username}' already exists")
                else:
                    # Create new user
                    new_user = User(
                        username=new_username,
                        password_hash=hash_password(new_password),
                        role=UserRole.ADMIN if new_role == "admin" else UserRole.INTERN,
                        is_active=new_active
                    )
                    db.add(new_user)
                    db.commit()
                    st.success(f"✅ User '{new_username}' created successfully")
                    st.rerun()
            except Exception as e:
                db.rollback()
                st.error(f"❌ Error creating user: {e}")
            finally:
                db.close()

st.markdown("---")

# List existing users
st.subheader("📋 Existing Users")

if not users:
    st.info("No users found")
else:
    for user in users:
        username = getattr(user, "username", "Unknown")
        role = getattr(user, "role", UserRole.INTERN)
        is_active = getattr(user, "is_active", False)
        created_at = getattr(user, "created_at", None)
        
        # Create expandable section for each user
        with st.expander(f"{'✅' if is_active else '❌'} **{username}** - {role.value.upper()}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Username:** {username}")
                st.write(f"**Role:** {role.value.upper()}")
                st.write(f"**Status:** {'Active' if is_active else 'Inactive'}")
                if created_at:
                    st.write(f"**Created:** {created_at.strftime('%Y-%m-%d %H:%M')}")
            
            with col2:
                st.write("**Actions:**")
                
                # Toggle active status
                new_status = not is_active
                if st.button(
                    f"{'Deactivate' if is_active else 'Activate'}",
                    key=f"toggle_{username}",
                    type="secondary"
                ):
                    db = SessionLocal()
                    try:
                        user_to_update = db.query(User).filter_by(username=username).first()
                        if user_to_update:
                            setattr(user_to_update, "is_active", new_status)
                            db.commit()
                            st.success(f"✅ User {'deactivated' if not new_status else 'activated'}")
                            st.rerun()
                    finally:
                        db.close()
                
                # Change role
                current_role = role.value
                new_role_select = "admin" if current_role == "intern" else "intern"
                if st.button(
                    f"Change to {new_role_select.upper()}",
                    key=f"role_{username}",
                    type="secondary"
                ):
                    db = SessionLocal()
                    try:
                        user_to_update = db.query(User).filter_by(username=username).first()
                        if user_to_update:
                            new_role_enum = UserRole.ADMIN if new_role_select == "admin" else UserRole.INTERN
                            setattr(user_to_update, "role", new_role_enum)
                            db.commit()
                            st.success(f"✅ Role changed to {new_role_select.upper()}")
                            st.rerun()
                    finally:
                        db.close()
            
            # Change password section
            st.markdown("---")
            st.write("**Change Password:**")
            with st.form(f"reset_password_{username}"):
                new_pwd = st.text_input("New Password", type="password", key=f"pwd_{username}")
                if st.form_submit_button("Change Password"):
                    if not new_pwd:
                        st.error("❌ Password cannot be empty")
                    elif len(new_pwd) < 6:
                        st.error("❌ Password must be at least 6 characters")
                    else:
                        db = SessionLocal()
                        try:
                            user_to_update = db.query(User).filter_by(username=username).first()
                            if user_to_update:
                                setattr(user_to_update, "password_hash", hash_password(new_pwd))
                                db.commit()
                                st.success(f"✅ Password reset for {username}")
                        finally:
                            db.close()
            
            # Delete user (with confirmation)
            st.markdown("---")
            st.write("**Delete User:**")
            if st.button(f"🗑️ Delete User", key=f"delete_{username}", type="secondary"):
                # Don't allow deleting yourself
                if username == st.session_state.get("username"):
                    st.error("❌ You cannot delete your own account")
                else:
                    db = SessionLocal()
                    try:
                        user_to_delete = db.query(User).filter_by(username=username).first()
                        if user_to_delete:
                            db.delete(user_to_delete)
                            db.commit()
                            st.success(f"🗑️ User '{username}' deleted")
                            st.rerun()
                    finally:
                        db.close()

st.markdown("---")
st.caption("💡 Tip: Inactive users cannot log in but their data is preserved")