import datetime
import secrets
from typing import Optional, cast
import streamlit as st
import requests

# ----------------------------
# Supabase configuration
# ----------------------------
SUPABASE_URL = st.secrets["supabase"]["url"]          # e.g., "https://xyz.supabase.co"
SUPABASE_KEY = st.secrets["supabase"]["service_key"]  # service_role key for full access
SUPABASE_SESSION_TABLE = "sessions"                  # your table name

# --- demo users (replace with your own auth system if needed)
USER_CREDENTIALS = {"admin": "nil@1234", "test": "nil@1234"}
SESSION_DURATION_MINUTES = 60

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ----------------------------
# Internal helpers
# ----------------------------
def _create_session(username: str) -> str:
    """Create a session row in Supabase via REST and return the token."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(minutes=SESSION_DURATION_MINUTES)).isoformat()
    payload = {
        "username": username,
        "session_token": token,
        "expires_at": expires_at
    }
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/{SUPABASE_SESSION_TABLE}", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return token


def _validate_session(token: str) -> Optional[str]:
    """Return username if session is valid, else None."""
    if not token:
        return None
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{SUPABASE_SESSION_TABLE}?session_token=eq.{token}",
        headers=HEADERS
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        return None
    row = rows[0]
    expires_at = datetime.datetime.fromisoformat(row["expires_at"])
    if expires_at > datetime.datetime.utcnow():
        return cast(Optional[str], row["username"])
    return None


def _delete_session(token: str) -> None:
    """Delete a session row in Supabase via REST."""
    if not token:
        return
    resp = requests.delete(f"{SUPABASE_URL}/rest/v1/{SUPABASE_SESSION_TABLE}?session_token=eq.{token}", headers=HEADERS)
    resp.raise_for_status()

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
    """Enforce authentication for the main app pages."""
    token = st.session_state.get("session_token")
    if token:
        username = _validate_session(token)
        if username:
            st.session_state["username"] = username
            return True
        # expired or invalid session
        _delete_session(token)
        for k in ("session_token", "username"):
            st.session_state.pop(k, None)
        st.warning("Session expired — please log in again.")
    login_form()
    st.stop()


def logout() -> None:
    """Logout the current user."""
    token = st.session_state.get("session_token")
    if token:
        _delete_session(token)
    for k in ("session_token", "username"):
        st.session_state.pop(k, None)


def logout_button() -> None:
    """Render current username and logout button in sidebar."""
    username = st.session_state.get("username")
    if username:
        st.sidebar.markdown(f"**Logged in as:** {username}")
    if st.sidebar.button("🚪 Logout"):
        logout()
        st.sidebar.success("✅ Logged out")
        st.rerun()


def get_current_username() -> Optional[str]:
    return st.session_state.get("username")