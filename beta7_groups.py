import streamlit as st
import requests
import cloudinary
import cloudinary.uploader
import time
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
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

# ==============================
# DATABASE (SQLAlchemy + SQLite)
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


Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
# FUNCTIONS
# ==============================
@st.cache_data(ttl=3600)
def get_instagram_accounts():
    """Return a dict of IG account IDs mapped to Page names."""
    accounts = {}
    pages_resp = requests.get(
        "https://graph.facebook.com/v21.0/me/accounts",
        params={"access_token": ACCESS_TOKEN}
    ).json()
    pages = pages_resp.get("data", [])

    for page in pages:
        page_id = page["id"]
        page_name = page["name"]

        ig_resp = requests.get(
            f"https://graph.facebook.com/v21.0/{page_id}",
            params={
                "fields": "instagram_business_account",
                "access_token": page["access_token"]
            }
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
    results = []
    for ig_id in selected_ig_ids:
        # Step 1: Create media container
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

        # Step 2: Poll until video is processed
        if media_type == "video":
            status_url = f"https://graph.facebook.com/v21.0/{creation_id}"
            for attempt in range(10):  # up to ~30s
                status_resp = requests.get(
                    status_url,
                    params={"fields": "status_code", "access_token": ACCESS_TOKEN}
                ).json()
                status = status_resp.get("status_code")
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    results.append(f"❌ {ig_id}: Video processing failed → {status_resp}")
                    creation_id = None
                    break
                time.sleep(3)

            if not creation_id:
                continue

        # Step 3: Publish
        publish_url = f"https://graph.facebook.com/v21.0/{ig_id}/media_publish"
        publish_params = {"creation_id": creation_id, "access_token": ACCESS_TOKEN}
        publish_resp = requests.post(publish_url, params=publish_params).json()

        if "id" in publish_resp:
            results.append(f"✅ {ig_id}: Post published successfully! (Post ID: {publish_resp['id']})")
            # Auto-clean Cloudinary
            try:
                cloudinary.uploader.destroy(public_id, resource_type=media_type)
            except Exception as e:
                results.append(f"⚠️ Failed to delete from Cloudinary: {e}")
        else:
            results.append(f"❌ {ig_id}: Publish failed → {publish_resp}")

    return results


# ==============================
# MAIN APP
# ==============================
st.title("📲 Instagram Bulk Poster")

with st.spinner("Fetching Instagram accounts..."):
    ig_accounts = get_instagram_accounts()

if not ig_accounts:
    st.error("❌ No linked Instagram accounts found.")
    st.stop()

# --- Groups Section ---
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

selected_groups = st.multiselect(
    "Or select groups",
    options=[g.name for g in groups]
)

# Resolve group members
db = SessionLocal()
expanded_group_accounts = []
for gname in selected_groups:
    g = db.query(Group).filter_by(name=gname).first()
    expanded_group_accounts.extend([acc.ig_id for acc in g.accounts])
db.close()

final_selected_accounts = list(set(selected_accounts + expanded_group_accounts))

uploaded_file = st.file_uploader(
    "Upload an image or video",
    type=["png", "jpg", "jpeg", "mp4", "mov", "avi"]
)
caption = st.text_area("Caption", placeholder="Write your caption here...")

if st.button("Post to Selected Accounts"):
    if not uploaded_file or not caption or not final_selected_accounts:
        st.error("⚠️ Please upload a media file, write a caption, and select at least one account or group.")
    else:
        with st.spinner("Uploading to Cloudinary..."):
            media_url, public_id, extra = upload_to_cloudinary(uploaded_file)

        if not media_url:
            st.error(f"❌ Cloudinary upload failed: {extra}")
        else:
            media_type = extra if extra in ["image", "video"] else "image"
            st.success(f"✅ Uploaded to Cloudinary: {media_url}")

            with st.spinner("Posting to Instagram..."):
                results = post_to_instagram(final_selected_accounts, media_url, caption, public_id, media_type)

            st.subheader("Results")
            for r in results:
                st.write(r)