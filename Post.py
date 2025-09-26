import streamlit as st
import datetime
import pytz
from db.utils import SessionLocal
from db.models import ScheduledPost

from utils.auth import require_auth, logout_button
from services.aws_utils import upload_to_cloudinary
from services.instagram_api import get_instagram_accounts, post_to_instagram
from services.scheduler import schedule_post
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

# ============================== MAIN APP
st.title("📤 Post to Instagram")

# --- Account / Group selection ---
selected_accounts = st.multiselect(
    "Select individual accounts",
    options=list(ig_accounts.keys()),
    format_func=lambda x: ig_accounts[x]
)

selected_groups = st.multiselect(
    "Select groups",
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
                st.error("❌ AWS upload failed.")
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
                    f"✅ Scheduled for {local_dt_tz.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                )
                st.info("📝 Note: Posts are processed every 20 minutes. Scheduled posts only run from 9am to 8pm.")

with col2:
    if st.button("⚡ Post Now"):
        if not uploaded_file or not caption or not final_accounts:
            st.error("⚠️ Missing fields.")
        else:
            media_url, public_id, media_type = upload_to_cloudinary(uploaded_file)
            if not media_url:
                st.error("❌ AWS upload failed.")
            else:
                with st.spinner(f"Posting to {len(final_accounts)} accounts... Do not refresh or close the tab."):
                    results = post_to_instagram(final_accounts, media_url, caption, public_id, media_type, username=st.session_state.username)
                st.subheader("Results")
                for r in results:
                    st.write(r)

# ============================== Show Upcoming Scheduled Posts
def show_upcoming_scheduled_posts():
    """Display upcoming scheduled posts in the sidebar"""
    db = SessionLocal()
    try:
        # Get upcoming scheduled posts
        upcoming = db.query(ScheduledPost).filter(
            ScheduledPost.scheduled_time > datetime.datetime.utcnow()
        ).order_by(ScheduledPost.scheduled_time).limit(10).all()
        
        if upcoming:
            st.sidebar.subheader("📅 Upcoming Scheduled Posts")
            st.sidebar.caption("(May take a few minutes to process)")
            
            for post in upcoming:
                # Convert UTC to IST for display
                utc_time = post.scheduled_time.replace(tzinfo=datetime.timezone.utc)
                ist_time = utc_time.astimezone(IST)
                
                # Get account names
                account_ids = post.ig_ids.split(',')
                account_names = []
                for ig_id in account_ids:
                    name = ig_accounts.get(ig_id, ig_id)
                    account_names.append(name)
                
                # Display post info
                st.sidebar.write("---")
                st.sidebar.write(f"⏰ **{ist_time.strftime('%Y-%m-%d %H:%M IST')}**")
                st.sidebar.write(f"📱 {', '.join(account_names[:2])}{'...' if len(account_names) > 2 else ''}")
                st.sidebar.write(f"💬 {post.caption[:50]}{'...' if len(post.caption) > 50 else ''}") # type: ignore
        else:
            st.sidebar.info("No upcoming scheduled posts")
            
    except Exception as e:
        st.sidebar.error(f"Error loading scheduled posts: {e}")
    finally:
        db.close()

# Show upcoming posts
show_upcoming_scheduled_posts()

# Add scheduler status in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Scheduler Status")
st.sidebar.success("✅ Active via GitHub Actions")
st.sidebar.caption("Posts are processed every 20 minutes")
st.sidebar.caption("Check GitHub Actions tab for logs")