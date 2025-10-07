import datetime
import secrets
import hashlib
from typing import Optional, cast

import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import get_database_url

from db.models import Session as DBSession, User, UserRole

# --- DB connection using hybrid config ---
DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# session lifetime
SESSION_DURATION_MINUTES = 1440

# ----------------------------
# Password hashing utilities
# ----------------------------
def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = "instagram_poster_salt_2024"  # In production, use env variable
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == password_hash

# ----------------------------
# Internal DB helpers
# ----------------------------
def _create_session(username: str) -> str:
    """Create a DB session row and return the token."""
    db = SessionLocal()
    try:
        token = secrets.token_urlsafe(32)
        expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=SESSION_DURATION_MINUTES)
        db_row = DBSession(username=username, session_token=token, expires_at=expires)
        db.add(db_row)
        db.commit()
        return token
    finally:
        db.close()

def _validate_session(token: str) -> Optional[tuple[str, str]]:
    """
    Return (username, role) if token exists and is not expired, else None.
    """
    if not token:
        return None
    db = SessionLocal()
    try:
        db_row = db.query(DBSession).filter_by(session_token=token).first()
        if db_row is None:
            return None

        # Check expiration
        expires_at = getattr(db_row, "expires_at", None)
        if expires_at is None or expires_at <= datetime.datetime.utcnow():
            return None

        # Get user details
        username = getattr(db_row, "username", None)
        if not username:
            return None
        
        # Fetch user to get role
        user = db.query(User).filter_by(username=username).first()
        if not user or not getattr(user, "is_active", True):
            return None
        
        role = getattr(user, "role", UserRole.INTERN)
        role_str = role.value if isinstance(role, UserRole) else str(role)
        
        return cast(tuple[str, str], (username, role_str))
    finally:
        db.close()

def _delete_session(token: str) -> None:
    """Delete a session DB row (no-op if not found)."""
    if not token:
        return
    db = SessionLocal()
    try:
        db.query(DBSession).filter_by(session_token=token).delete()
        db.commit()
    finally:
        db.close()

def _authenticate_user(username: str, password: str) -> Optional[str]:
    """
    Authenticate user against database.
    Returns role if successful, None otherwise.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username).first()
        if not user:
            return None
        
        # Check if user is active
        if not getattr(user, "is_active", True):
            return None
        
        # Verify password
        password_hash = getattr(user, "password_hash", "")
        if not verify_password(password, password_hash):
            return None
        
        # Return role
        role = getattr(user, "role", UserRole.INTERN)
        return role.value if isinstance(role, UserRole) else str(role)
    finally:
        db.close()

# ----------------------------
# Streamlit-facing functions
# ----------------------------
def login_form() -> None:
    st.title("🔒 Login Required")
    
    with st.form("login_form"):
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            if not user or not pw:
                st.error("❌ Please enter both username and password")
                return
            
            role = _authenticate_user(user, pw)
            if role:
                token = _create_session(user)
                st.session_state["session_token"] = token
                st.session_state["username"] = user
                st.session_state["role"] = role
                st.success("✅ Login successful")
                st.rerun()
            else:
                st.error("❌ Invalid credentials or account disabled")

def require_auth() -> bool:
    """
    Enforce authentication. If session_token exists and is valid, restore username and role.
    Otherwise show login_form() and stop execution.
    Call this at the top of every page that needs auth.
    """
    token = st.session_state.get("session_token")
    if token:
        result = _validate_session(token)
        if result:
            username, role = result
            # persist username and role in session_state for convenience
            st.session_state["username"] = username
            st.session_state["role"] = role
            return True

        # invalid/expired token: clear and prompt to login
        _delete_session(token)
        for k in ("session_token", "username", "role"):
            st.session_state.pop(k, None)
        st.warning("Session expired or invalid – please log in again.")

    login_form()
    st.stop()

def require_role(required_role: str) -> bool:
    """
    Check if current user has the required role.
    Call after require_auth() to enforce role-based access.
    
    Args:
        required_role: Either "admin" or "intern"
    
    Returns:
        True if user has required role or higher
    """
    current_role = st.session_state.get("role", "intern")
    
    # Admin has access to everything
    if current_role == "admin":
        return True
    
    # Check specific role requirement
    if required_role == "intern" and current_role in ["admin", "intern"]:
        return True
    
    # Access denied
    st.error("🚫 Access Denied: You don't have permission to access this page")
    st.info(f"Required role: {required_role.upper()}")
    st.info(f"Your role: {current_role.upper()}")
    st.stop()

def logout() -> None:
    """Logout the current user (delete DB session + clear session_state)."""
    token = st.session_state.get("session_token")
    if token:
        _delete_session(token)
    for k in ("session_token", "username", "role"):
        st.session_state.pop(k, None)

def logout_button() -> None:
    """Render current username, role, and a logout button in the sidebar."""
    username = st.session_state.get("username")
    role = st.session_state.get("role", "intern")
    
    if username:
        st.sidebar.markdown(f"**Logged in as:** {username}")
        
        # Show role badge with color
        role_color = "🔴" if role == "admin" else "🟢"
        st.sidebar.markdown(f"{role_color} **Role:** {role.upper()}")
        
    if st.sidebar.button("🚪 Logout"):
        logout()
        st.sidebar.success("✅ Logged out")
        st.rerun()

def get_current_username() -> Optional[str]:
    return st.session_state.get("username")

def get_current_role() -> str:
    return st.session_state.get("role", "intern")

def is_admin() -> bool:
    """Check if current user is an admin."""
    return get_current_role() == "admin"