import datetime
import secrets
from typing import Optional, Any, cast

import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import get_database_url

# import your ORM model class (make sure the model class name is not colliding with SQLAlchemy Session)
from db.models import Session as DBSession  # DBSession is the ORM model class for the "sessions" table

# --- DB connection using hybrid config ---
DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- simple demo users (replace with real user store as needed) ---
USER_CREDENTIALS = {"admin": "nil@1234", "test": "nil@1234"}

# session lifetime
SESSION_DURATION_MINUTES = 60

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
        # refresh not strictly necessary if not using the returned object
        return token
    finally:
        db.close()

def _validate_session(token: str) -> Optional[str]:
    """
    Return the username if token exists and is not expired, else None.
    Important: use getattr(...) to read instance attributes (avoids static typing issues).
    """
    if not token:
        return None
    db = SessionLocal()
    try:
        db_row = db.query(DBSession).filter_by(session_token=token).first()
        if db_row is None:
            return None

        # read instance attribute (a real datetime) and compare to now
        expires_at = getattr(db_row, "expires_at", None)
        if expires_at is None:
            return None

        if expires_at > datetime.datetime.utcnow():
            # read username from instance and cast to str for type checkers
            username = getattr(db_row, "username", None)
            return cast(Optional[str], username)
        return None
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

# ----------------------------
# Streamlit-facing functions
# ----------------------------
def login_form() -> None:
    st.title("🔒 Login Required")
    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if user in USER_CREDENTIALS and USER_CREDENTIALS[user] == pw:
            token = _create_session(user)
            st.session_state["session_token"] = token
            st.session_state["username"] = user
            st.success("✅ Login successful")
            st.rerun()
        else:
            st.error("❌ Invalid credentials")

def require_auth() -> bool:
    """
    Enforce authentication. If session_token exists and is valid, restore username.
    Otherwise show login_form() and stop execution.
    Call this at the top of every page that needs auth.
    """
    token = st.session_state.get("session_token")
    if token:
        username = _validate_session(token)
        if username:
            # persist username in session_state for convenience
            st.session_state["username"] = username
            return True

        # invalid/expired token: clear and prompt to login
        _delete_session(token)
        for k in ("session_token", "username"):
            st.session_state.pop(k, None)
        st.warning("Session expired or invalid – please log in again.")

    login_form()
    st.stop()

def logout() -> None:
    """Logout the current user (delete DB session + clear session_state)."""
    token = st.session_state.get("session_token")
    if token:
        _delete_session(token)
    for k in ("session_token", "username"):
        st.session_state.pop(k, None)

def logout_button() -> None:
    """Render current username and a logout button in the sidebar."""
    username = st.session_state.get("username")
    if username:
        st.sidebar.markdown(f"**Logged in as:** {username}")
    if st.sidebar.button("🚪 Logout"):
        logout()
        st.sidebar.success("✅ Logged out")
        st.rerun()

def get_current_username() -> Optional[str]:
    return st.session_state.get("username")