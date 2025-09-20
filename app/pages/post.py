# pages/post.py
import streamlit as st
import datetime

from services.cloudinary_utils import upload_to_cloudinary
from services.instagram_api import get_instagram_accounts, post_to_instagram
from services.scheduler import schedule_post
from utils.cache import get_groups_cache

def render():
    st.title("📤 Post to Instagram")

    ig_accounts = get_instagram_accounts()
    if not ig_accounts:
        st.error("❌ No linked Instagram accounts found.")
        return

    groups_cache = get_groups_cache()

    # Account / Group selection
    selected_accounts = st.multiselect(
        "Select individual accounts",
        options=list(ig_accounts.keys()),
        format_func=lambda x: ig_accounts[x]
    )

    selected_groups = st.multiselect("Or select groups", options=list(groups_cache.keys()))

    # Resolve final accounts (dedupe)
    expanded_group_accounts = []
    for gname in selected_groups:
        expanded_group_accounts.extend(groups_cache.get(gname, []))
    final_accounts = list(dict.fromkeys(selected_accounts + expanded_group_accounts))

    # Upload + Caption
    uploaded_file = st.file_uploader("Upload an image or video", type=["png","jpg","jpeg","mp4","mov","avi"])
    caption = st.text_area("Caption", placeholder="Write your caption here...")

    # Schedule inputs
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

    # Buttons
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
                    local_dt = datetime.datetime.combine(schedule_date, schedule_time)
                    local_dt_tz = local_dt.replace(tzinfo=LOCAL_TZ)
                    # schedule_post will convert to UTC & insert into DB
                    schedule_post(final_accounts, caption, media_url, public_id, media_type, local_dt_tz)
                    st.success(f"✅ Scheduled for {local_dt_tz.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    with col2:
        if st.button("⚡ Post Now"):
            if not uploaded_file or not caption or not final_accounts:
                st.error("⚠️ Missing fields.")
            else:
                media_url, public_id, media_type = upload_to_cloudinary(uploaded_file)
                if not media_url:
                    st.error("❌ Cloudinary upload failed.")
                else:
                    results = post_to_instagram(final_accounts, media_url, caption, public_id, media_type)
                    st.subheader("Results")
                    for r in results:
                        st.write(r)