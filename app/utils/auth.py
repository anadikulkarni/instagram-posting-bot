import streamlit as st

USER_CREDENTIALS = {
    "admin": "nil@1234",
    "test": "nil@1234"
}

def login_form():
    st.title("🔒 Login Required")
    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if user in USER_CREDENTIALS and USER_CREDENTIALS[user] == pw:
            st.session_state.authenticated = True
            st.session_state.username = user
            st.success("✅ Login successful")
            st.rerun()
        else:
            st.error("❌ Invalid credentials")

def require_auth():
    if not st.session_state.get("authenticated", False):
        login_form()
        st.stop()