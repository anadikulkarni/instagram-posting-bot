import streamlit as st
import requests
import cloudinary
import cloudinary.uploader

# ==============================
# CONFIG
# ==============================
ACCESS_TOKEN = "EAFj9NZBCpuFQBPVNP9K96VmF0YCvd20lsvidfWPTvi7ZBQvZB91dItskvgrfPkY1WMy3iI8naODmB2m834LZBGWsHXVYw70YBCrKefrlHibN1X5gLnRylVgtCjqbBLraWDdS6ZCeVt4EH7VioCVKgcyoQrIZCa9DZBm3WDyjrPainGgSjMAB9lVXvGqGUUI"

# Cloudinary configuration 
cloudinary.config(
    cloud_name="dvbiqmhoo",
    api_key="358538431434132",
    api_secret="MTnwuudPzdiDZ96_tpL_7A60zZ0"
)

st.set_page_config(page_title="Instagram Bulk Poster", page_icon="📲")
st.title("📲 Instagram Bulk Poster")
st.write("Upload an image or video and post it to selected Instagram Business Accounts.")

# ==============================
# FUNCTIONS
# ==============================
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
    """Upload a file to Cloudinary and return the direct URL."""
    try:
        result = cloudinary.uploader.upload(
            file,
            resource_type="auto"  # auto detects image or video
        )
        return result["secure_url"], result
    except Exception as e:
        return None, str(e)

def post_to_instagram(selected_ig_ids, media_url, caption):
    """Post media to selected Instagram business accounts."""
    results = []

    for ig_id in selected_ig_ids:
        # Step 1: Create media
        create_url = f"https://graph.facebook.com/v21.0/{ig_id}/media"
        create_params = {
            "caption": caption,
            "access_token": ACCESS_TOKEN
        }

        # Detect type based on file extension
        if media_url.lower().endswith((".mp4", ".mov", ".avi")):
            create_params["media_type"] = "VIDEO"
            create_params["video_url"] = media_url
        else:
            create_params["image_url"] = media_url

        create_resp = requests.post(create_url, params=create_params).json()

        if "id" not in create_resp:
            results.append(f"❌ {ig_id}: Media creation failed → {create_resp}")
            continue

        # Step 2: Publish media
        publish_url = f"https://graph.facebook.com/v21.0/{ig_id}/media_publish"
        publish_params = {
            "creation_id": create_resp["id"],
            "access_token": ACCESS_TOKEN
        }
        publish_resp = requests.post(publish_url, params=publish_params).json()

        if "id" in publish_resp:
            results.append(f"✅ {ig_id}: Post published successfully! (Post ID: {publish_resp['id']})")
        else:
            results.append(f"❌ {ig_id}: Publish failed → {publish_resp}")

    return results

# ==============================
# UI
# ==============================
# 1️⃣ Get IG accounts
with st.spinner("Fetching Instagram accounts..."):
    ig_accounts = get_instagram_accounts()

if not ig_accounts:
    st.error("❌ No linked Instagram accounts found.")
else:
    st.success(f"✅ Found {len(ig_accounts)} Instagram accounts.")
    selected_accounts = st.multiselect(
        "Select Instagram accounts to post to",
        options=list(ig_accounts.keys()),
        format_func=lambda x: ig_accounts[x]  # show page name in dropdown
    )

uploaded_file = st.file_uploader("Upload an image or video", type=["png", "jpg", "jpeg", "mp4", "mov", "avi"])
caption = st.text_area("Caption", placeholder="Write your caption here...")

if st.button("Post to Selected Accounts"):
    if not uploaded_file or not caption or not selected_accounts:
        st.error("⚠️ Please upload a media file, write a caption, and select at least one account.")
    else:
        with st.spinner("Uploading to Cloudinary..."):
            media_url, resp = upload_to_cloudinary(uploaded_file)

        if not media_url:
            st.error(f"❌ Cloudinary upload failed: {resp}")
        else:
            st.success(f"✅ Uploaded to Cloudinary: {media_url}")

            with st.spinner("Posting to Instagram..."):
                results = post_to_instagram(selected_accounts, media_url, caption)

            st.subheader("Results")
            for r in results:
                st.write(r)