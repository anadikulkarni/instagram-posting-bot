import streamlit as st
import requests
import cloudinary
import cloudinary.uploader
import time
import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# ==============================
# CONFIG
# ==============================
ACCESS_TOKEN = "EAFj9NZBCpuFQBPVNP9K96VmF0YCvd20lsvidfWPTvi7ZBQvZB91dItskvgrfPkY1WMy3iI8naODmB2m834LZBGWsHXVYw70YBCrKefrlHibN1X5gLnRylVgtCjqbBLraWDdS6ZCeVt4EH7VioCVKgcyoQrIZCa9DZBm3WDyjrPainGgSjMAB9lVXvGqGUUI"

cloudinary.config(
    cloud_name="dvbiqmhoo",
    api_key="358538431434132",
    api_secret="MTnwuudPzdiDZ96_tpL_7A60zZ0"
)

st.set_page_config(page_title="Instagram Bulk Poster", page_icon="📲")

# detect user's local tz for display / conversion
LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo

# ==============================
# DATABASE
# ==============================
Base = declarative_base()
engine = create_engine("sqlite:///groups.db")
SessionLocal = sessionmaker(bind=engine)


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    accounts = relationship("GroupAccount", back_populates="group", cascade="all, delete")


class GroupAccount(Base):
    __tablename__ = "group_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    ig_id = Column(String, nullable=False)
    group = relationship("Group", back_populates="accounts")


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ig_ids = Column(Text, nullable=False)  # comma-separated IDs
    caption = Column(Text, nullable=False)
    media_url = Column(String, nullable=False)
    public_id = Column(String, nullable=False)
    media_type = Column(String, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)  # stored as naive UTC


Base.metadata.create_all(engine)


# ==============================
# SIMPLE AUTH
# ==============================
USER_CREDENTIALS = {"admin": "nil@1234",
                    "test": "nil@1234"}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Login Required")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
            st.session_state.authenticated = True
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")
    st.stop()


# ==============================
# HELPERS
# ==============================
@st.cache_data(ttl=3600)
def get_instagram_accounts():
    accounts = {}
    pages_resp = requests.get(
        "https://graph.facebook.com/v21.0/me/accounts",
        params={"access_token": ACCESS_TOKEN}
    ).json()
    for page in pages_resp.get("data", []):
        page_id = page["id"]
        page_name = page["name"]
        ig_resp = requests.get(
            f"https://graph.facebook.com/v21.0/{page_id}",
            params={"fields": "instagram_business_account", "access_token": page["access_token"]}
        ).json()
        ig_id = ig_resp.get("instagram_business_account", {}).get("id")
        if ig_id:
            accounts[ig_id] = page_name
    return accounts


def upload_to_cloudinary(file):
    try:
        result = cloudinary.uploader.upload(file, resource_type="auto")
        return result["secure_url"], result["public_id"], result["resource_type"]
    except Exception as e:
        return None, None, str(e)


def post_to_instagram(selected_ig_ids, media_url, caption, public_id, media_type):
    """Create+publish a media container per account. Return list of result messages.
       NOTE: Does NOT delete Cloudinary asset until all accounts are processed.
    """
    results = []
    for ig_id in selected_ig_ids:
        # Step 1: Create media container (per account)
        create_url = f"https://graph.facebook.com/v21.0/{ig_id}/media"
        create_params = {"caption": caption, "access_token": ACCESS_TOKEN}

        if media_type == "video":
            create_params["media_type"] = "REELS"
            create_params["video_url"] = media_url
        else:
            create_params["image_url"] = media_url
            create_params["media_type"] = "image"

        create_resp = requests.post(create_url, params=create_params).json()
        if "id" not in create_resp:
            results.append(f"❌ {ig_id}: Media creation failed → {create_resp}")
            continue

        creation_id = create_resp["id"]

        # Step 2: Poll until processed (images are usually instant; videos may take time)
        status_url = f"https://graph.facebook.com/v21.0/{creation_id}"
        for attempt in range(15):  # up to ~45s
            status_resp = requests.get(
                status_url,
                params={"fields": "status_code", "access_token": ACCESS_TOKEN}
            ).json()
            status = status_resp.get("status_code")
            if status in ("FINISHED", "READY"):
                break
            elif status == "ERROR":
                results.append(f"❌ {ig_id}: Processing failed → {status_resp}")
                creation_id = None
                break
            time.sleep(3)

        if not creation_id:
            continue

        # Step 3: Publish
        publish_url = f"https://graph.facebook.com/v21.0/{ig_id}/media_publish"
        publish_resp = requests.post(
            publish_url,
            params={"creation_id": creation_id, "access_token": ACCESS_TOKEN}
        ).json()
        if "id" in publish_resp:
            results.append(f"✅ {ig_id}: Post published! (Post ID: {publish_resp['id']})")
        else:
            results.append(f"❌ {ig_id}: Publish failed → {publish_resp}")

    # Cleanup Cloudinary AFTER all accounts processed
    try:
        cloudinary.uploader.destroy(public_id, resource_type=media_type)
    except Exception as e:
        results.append(f"⚠️ Cloudinary delete failed: {e}")

    return results


def run_scheduled_posts():
    db = SessionLocal()
    now = datetime.datetime.now(datetime.timezone.utc)
    due_posts = db.query(ScheduledPost).filter(ScheduledPost.scheduled_time <= now).all()
    results = []
    for post in due_posts:
        ig_ids = post.ig_ids.split(",")
        results.extend(post_to_instagram(ig_ids, post.media_url, post.caption, post.public_id, post.media_type))
        db.delete(post)
        db.commit()
    db.close()
    return results


# ==============================
# MAIN APP
# ==============================
st.title("📲 Instagram Bulk Poster")

# Execute scheduled posts due now (runs at page load)
scheduled_results = run_scheduled_posts()
if scheduled_results:
    st.subheader("⏰ Scheduled Posts Executed")
    for r in scheduled_results:
        st.write(r)

with st.spinner("Fetching Instagram accounts..."):
    ig_accounts = get_instagram_accounts()

if not ig_accounts:
    st.error("❌ No linked Instagram accounts found.")
    st.stop()

# --- Groups Section (kept on main page; you can move it to pages/ if desired) ---
st.subheader("👥 Manage Account Groups")

with st.form("create_group_form", clear_on_submit=True):
    group_name = st.text_input("New Group Name")
    group_accounts = st.multiselect(
        "Select accounts to include",
        options=list(ig_accounts.keys()),
        format_func=lambda x: ig_accounts[x]
    )
    if st.form_submit_button("Create Group"):
        if group_name and group_accounts:
            db = SessionLocal()
            if db.query(Group).filter_by(name=group_name).first():
                st.error("❌ Group name already exists.")
            else:
                new_group = Group(name=group_name)
                db.add(new_group)
                db.commit()
                for acc in group_accounts:
                    db.add(GroupAccount(group_id=new_group.id, ig_id=acc))
                db.commit()
                st.success(f"✅ Group '{group_name}' created.")
            db.close()

# Show existing groups
db = SessionLocal()
groups = db.query(Group).all()
if groups:
    for g in groups:
        members = [ig_accounts.get(acc.ig_id, acc.ig_id) for acc in g.accounts]
        st.write(f"📌 **{g.name}** → {', '.join(members)}")
        if st.button(f"Delete Group '{g.name}'", key=f"del_{g.id}"):
            db.delete(g)
            db.commit()
            st.success(f"🗑️ Deleted group {g.name}")
            st.rerun()
db.close()

# --- Posting Section ---
st.subheader("📤 Post to Instagram")

selected_accounts = st.multiselect(
    "Select individual Instagram accounts",
    options=list(ig_accounts.keys()),
    format_func=lambda x: ig_accounts[x]
)

selected_groups = st.multiselect("Or select groups", options=[g.name for g in groups])

# Resolve group members (expand selected groups to IG ids)
db = SessionLocal()
expanded_group_accounts = []
for gname in selected_groups:
    g = db.query(Group).filter_by(name=gname).first()
    if g:
        expanded_group_accounts.extend([acc.ig_id for acc in g.accounts])
db.close()

# Deduplicate (account may be in multiple groups + manually selected) while preserving order
final_selected_accounts = list(dict.fromkeys(selected_accounts + expanded_group_accounts))

uploaded_file = st.file_uploader("Upload an image or video", type=["png", "jpg", "jpeg", "mp4", "mov", "avi"])
caption = st.text_area("Caption", placeholder="Write your caption here...")

# ---------- schedule default initialization in session_state (fix resets) ----------
now_local = datetime.datetime.now()
if "schedule_date" not in st.session_state:
    st.session_state.schedule_date = now_local.date()
if "schedule_time" not in st.session_state:
    # default to a few minutes from now rounded to minute
    default_dt = (now_local + datetime.timedelta(minutes=5)).replace(second=0, microsecond=0)
    st.session_state.schedule_time = default_dt.time()

# Widgets with keys so Streamlit preserves selected values across reruns
col_date, col_time = st.columns([1, 1])
with col_date:
    schedule_date = st.date_input("📅 Schedule Date", key="schedule_date")
with col_time:
    schedule_time = st.time_input("⏰ Schedule Time", key="schedule_time")

# Buttons: Post Later, Post Now, View Scheduled
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📅 Post Later"):
        if not uploaded_file or not caption or not final_selected_accounts:
            st.error("⚠️ Please provide all fields before scheduling.")
        else:
            media_url, public_id, extra = upload_to_cloudinary(uploaded_file)
            if not media_url:
                st.error(f"❌ Cloudinary upload failed: {extra}")
            else:
                media_type = extra if extra in ["image", "video"] else "image"
                # interpret chosen date/time as user's local time, convert to UTC for storage
                local_dt = datetime.datetime.combine(schedule_date, schedule_time)
                # attach local tz and convert to UTC, then store naive UTC
                local_dt_tz = local_dt.replace(tzinfo=LOCAL_TZ)
                utc_dt = local_dt_tz.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                db = SessionLocal()
                db.add(ScheduledPost(
                    ig_ids=",".join(final_selected_accounts),
                    caption=caption,
                    media_url=media_url,
                    public_id=public_id,
                    media_type=media_type,
                    scheduled_time=utc_dt
                ))
                db.commit()
                db.close()
                st.success(f"✅ Post scheduled for {local_dt_tz.strftime('%Y-%m-%d %H:%M:%S %Z')} (stored as UTC {utc_dt})")

with col2:
    if st.button("⚡ Post Now"):
        if not uploaded_file or not caption or not final_selected_accounts:
            st.error("⚠️ Please upload a media file, write a caption, and select at least one account or group.")
        else:
            with st.spinner("Uploading to Cloudinary..."):
                media_url, public_id, extra = upload_to_cloudinary(uploaded_file)
            if not media_url:
                st.error(f"❌ Cloudinary upload failed: {extra}")
            else:
                media_type = extra if extra in ["image", "video"] else "image"
                with st.spinner("Posting to Instagram..."):
                    results = post_to_instagram(final_selected_accounts, media_url, caption, public_id, media_type)
                st.subheader("Results")
                for r in results:
                    st.write(r)

with col3:
    if st.button("📋 View Scheduled Posts"):
        db = SessionLocal()
        scheduled = db.query(ScheduledPost).order_by(ScheduledPost.scheduled_time).all()
        if not scheduled:
            st.info("No scheduled posts.")
        else:
            st.subheader("📅 Scheduled Posts")
            for idx, post in enumerate(scheduled):
                # display local time for readability
                scheduled_local = post.scheduled_time.replace(tzinfo=datetime.timezone.utc).astimezone(LOCAL_TZ)
                st.markdown("---")
                st.write(f"📌 **ID:** {post.id}")
                st.write(f"👥 **Accounts:** {post.ig_ids}")
                st.write(f"📝 **Caption:** {post.caption[:200]}{'...' if len(post.caption) > 200 else ''}")
                st.write(f"🕒 **Scheduled for (local):** {scheduled_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                st.write(f"📁 **Media Type:** {post.media_type}")

                # Buttons in two columns
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"🗑️ Delete {post.id}", key=f"del_{post.id}_{idx}"):
                        try:
                            cloudinary.uploader.destroy(post.public_id, resource_type=post.media_type)
                        except Exception:
                            pass
                        db.delete(post)
                        db.commit()
                        st.success(f"🗑️ Deleted scheduled post {post.id}")
                        st.rerun()
                with c2:
                    if st.button(f"⚡ Post Now {post.id}", key=f"now_{post.id}_{idx}"):
                        results = post_to_instagram(
                            post.ig_ids.split(","), post.media_url, post.caption, post.public_id, post.media_type
                        )
                        db.delete(post)
                        db.commit()
                        st.subheader("Results")
                        for r in results:
                            st.write(r)
                        st.rerun()
        db.close()
