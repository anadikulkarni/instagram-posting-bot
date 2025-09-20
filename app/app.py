import streamlit as st
import datetime

from utils.auth import login_form, require_auth
from services.scheduler import run_scheduled_posts_if_due

st.set_page_config(page_title="Instagram Bulk Poster", page_icon="📲")

# ==============================
# AUTH
# ==============================
if not st.session_state.get("authenticated", False):
    login_form()
    st.stop()

# ==============================
# NAVIGATION
# ==============================
PAGES = {
    "📤 Post to Instagram": "pages/post.py",
    "👥 Manage Groups": "pages/groups.py",
    "📜 Logs": "pages/logs.py",
}

st.sidebar.title("📲 Instagram Bulk Poster")
choice = st.sidebar.radio("Navigate", list(PAGES.keys()))

# ==============================
# SCHEDULED POSTS RUNNER
# ==============================
scheduled_results = run_scheduled_posts_if_due()
if scheduled_results:
    st.sidebar.subheader("⏰ Scheduled Posts Executed")
    for r in scheduled_results:
        st.sidebar.write(r)

# ==============================
# PAGE ROUTER
# ==============================
if choice == "📤 Post to Instagram":
    import pages.post
    pages.post.render()
elif choice == "👥 Manage Groups":
    import pages.groups
    pages.groups.render()
elif choice == "📜 Logs":
    import pages.logs
    pages.logs.render()
