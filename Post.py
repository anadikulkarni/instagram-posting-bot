import streamlit as st
import datetime
import threading
import time
import pytz

from utils.auth import login_form, require_auth, logout_button
from services.cloudinary_utils import upload_to_cloudinary
from services.instagram_api import get_instagram_accounts, post_to_instagram
from services.scheduler import schedule_post, run_scheduled_posts
from utils.cache import get_groups_cache

st.set_page_config(page_title="Instagram Bulk Poster", page_icon="📲")

IST = pytz.timezone("Asia/Kolkata")

# ============================== AUTH
require_auth()
logout_button()

# ============================== CACHED IG ACCOUNTS
if "ig_accounts" not in st.session_state:
    st.session_state.ig_accounts = get_instagram_accounts()

ig_accounts = st.session_state.ig_accounts
if not ig_accounts:
    st.error("❌ No linked Instagram accounts found.")

# ============================== CACHED GROUPS
if "groups_cache" not in st.session_state:
    st.session_state.groups_cache = get_groups_cache()
groups_cache = st.session_state.groups_cache

# ============================== BACKGROUND SCHEDULED POSTS WORKER
SCHEDULE_INTERVAL_SECONDS = 300  # 5 minutes
if "scheduler_thread_started" not in st.session_state:
    def scheduled_runner():
        while True:
            try:
                results = run_scheduled_posts()
                if results:
                    if "scheduled_results" not in st.session_state:
                        st.session_state.scheduled_results = []
                    st.session_state.scheduled_results.extend(results)
            except Exception as e:
                print("Scheduler thread error:", e)
            time.sleep(SCHEDULE_INTERVAL_SECONDS)

    thread = threading.Thread(target=scheduled_runner, daemon=True)
    thread.start()
    st.session_state.scheduler_thread_started = True

# ============================== MAIN APP
st.title("📤 Post to Instagram")

# --- Account / Group selection ---
selected_accounts = st.multiselect(
    "Select individual accounts",
    options=list(ig_accounts.keys()),
    format_func=lambda x: ig_accounts[x]
)

selected_groups = st.multiselect(
    "Or select groups",
    options=list(groups_cache.keys())
)

# Resolve final accounts (deduplicate)
expanded_group_accounts = []
for gname in selected_groups:
    expanded_group_accounts.extend(groups_cache.get(gname, []))
final_accounts = list(dict.fromkeys(selected_accounts + expanded_group_accounts))

# --- Upload + Caption ---
uploaded_file = st.file_uploader("Upload an image or video", type=["png","jpg","jpeg","mp4","mov","avi"])
caption = st.text_area("Caption", placeholder="Write your caption here...")

# --- Schedule inputs ---
LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo
now_local = datetime.datetime.now()
if "schedule_date" not in st.session_state:
    st.session_state.schedule_date = now_local.date()
if "schedule_time" not in st.session_state:
    default_dt = (now_local + datetime.timedelta(minutes=5)).replace(second=0, microsecond=0)
    st.session_state.schedule_time = default_dt.time()

col_date, col_time = st.columns(2)
with col_date:
    schedule_date = st.date_input("📅 Schedule Date", key="schedule_date")
with col_time:
    schedule_time = st.time_input("⏰ Schedule Time", key="schedule_time")

# --- Buttons ---
col1, col2 = st.columns(2)
with col1:
    if st.button("📅 Post Later"):
        if not uploaded_file or not caption or not final_accounts:
            st.error("⚠️ Provide all fields.")
        else:
            media_url, public_id, media_type = upload_to_cloudinary(uploaded_file)
            if not media_url:
                st.error("❌ Cloudinary upload failed.")
            else:
                # Combine date + time from picker
                naive_local = datetime.datetime.combine(schedule_date, schedule_time)

                # Localize in IST
                local_dt_tz = IST.localize(naive_local)

                # Convert to UTC (naive)
                utc_dt = local_dt_tz.astimezone(datetime.timezone.utc).replace(tzinfo=None)

                # Save UTC datetime to DB
                schedule_post(
                    final_accounts,
                    caption,
                    media_url,
                    public_id,
                    media_type,
                    utc_dt,
                    st.session_state.username,
                )

                st.success(
                    f"✅ Scheduled for {local_dt_tz.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                    f"(will run at {utc_dt.strftime('%Y-%m-%d %H:%M:%S UTC')})"
                )

with col2:
    if st.button("⚡ Post Now"):
        if not uploaded_file or not caption or not final_accounts:
            st.error("⚠️ Missing fields.")
        else:
            media_url, public_id, media_type = upload_to_cloudinary(uploaded_file)
            if not media_url:
                st.error("❌ Cloudinary upload failed.")
            else:
                results = post_to_instagram(final_accounts, media_url, caption, public_id, media_type, username=st.session_state.username)
                st.subheader("Results")
                for r in results:
                    st.write(r)

# ============================== OPTIONAL: Show recent scheduled results
if "scheduled_results" in st.session_state and st.session_state.scheduled_results:
    st.sidebar.subheader("⏰ Recent Scheduled Posts")
    for r in st.session_state.scheduled_results[-10:]:  # last 10
        st.sidebar.write(r)