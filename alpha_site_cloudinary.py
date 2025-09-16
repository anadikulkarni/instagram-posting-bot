"""
Streamlit Instagram Bulk Poster (Cloudinary-backed)

Features:
- Upload an image or video from the browser
- Automatically upload the file to Cloudinary (resource_type='auto')
- Detect image vs video with python-magic and Cloudinary's response
- Post the uploaded media URL to all Instagram Business accounts the logged-in user manages
- Uses the Page access token for per-page operations and fetches IG IDs via the Page object

Environment variables required:
- IG_USER_ACCESS_TOKEN  : long-lived user access token with pages_show_list, pages_read_engagement, instagram_basic, instagram_content_publish
- CLOUDINARY_CLOUD_NAME : your Cloudinary cloud name (or set CLOUDINARY_URL instead)
- CLOUDINARY_API_KEY    : Cloudinary API key
- CLOUDINARY_API_SECRET : Cloudinary API secret

Usage:
1) pip install -r requirements.txt
   (requirements.txt: streamlit cloudinary python-magic requests)
2) export IG_USER_ACCESS_TOKEN="..."
   export CLOUDINARY_CLOUD_NAME="..."
   export CLOUDINARY_API_KEY="..."
   export CLOUDINARY_API_SECRET="..."
3) streamlit run streamlit_ig_poster_cloudinary.py

Notes:
- Cloudinary's free tier supports image+video uploads and provides a secure public URL for the uploaded asset.
- Instagram Graph API requires a publicly reachable HTTPS URL for the media (Cloudinary provides that).

"""

import os
import tempfile
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import requests
import cloudinary
import cloudinary.uploader

# ---------- Configuration / env ----------
IG_USER_ACCESS_TOKEN = "EAFj9NZBCpuFQBPVNP9K96VmF0YCvd20lsvidfWPTvi7ZBQvZB91dItskvgrfPkY1WMy3iI8naODmB2m834LZBGWsHXVYw70YBCrKefrlHibN1X5gLnRylVgtCjqbBLraWDdS6ZCeVt4EH7VioCVKgcyoQrIZCa9DZBm3WDyjrPainGgSjMAB9lVXvGqGUUI"
CLOUD_NAME = "dvbiqmhoo"
CLOUD_API_KEY = "358538431434132"
CLOUD_API_SECRET = "MTnwuudPzdiDZ96_tpL_7A60zZ0"

# Configure Cloudinary - allow CLOUDINARY_URL or explicit vars
if os.getenv("CLOUDINARY_URL"):
    cloudinary.config(url=os.getenv("CLOUDINARY_URL"))
else:
    cloudinary.config(
        cloud_name=CLOUD_NAME,
        api_key=CLOUD_API_KEY,
        api_secret=CLOUD_API_SECRET,
        secure=True,
    )

FB_API_VERSION = os.getenv("FB_API_VERSION", "v21.0")
CONCURRENCY = int(os.getenv("IG_CONCURRENCY", "6"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "150"))  # warn above this (Cloudinary free has limits)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Helper functions ----------

def upload_to_cloudinary(path: str) -> dict:
    """Uploads file to Cloudinary using resource_type='auto'. Returns Cloudinary upload result dict.
    """
    try:
        # resource_type='auto' lets Cloudinary decide image vs video
        res = cloudinary.uploader.upload(path, resource_type='auto')
        return res
    except Exception as e:
        logger.exception("Cloudinary upload failed")
        raise


def get_pages(user_token: str) -> list:
    url = f"https://graph.facebook.com/{FB_API_VERSION}/me/accounts"
    r = requests.get(url, params={"access_token": user_token}, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def get_instagram_id_for_page(page_id: str, page_token: str) -> str:
    url = f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}"
    params = {"fields": "instagram_business_account", "access_token": page_token}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("instagram_business_account", {}).get("id")


def create_media_and_publish(ig_id: str, page_token: str, media_url: str, mime: str, caption: str) -> dict:
    """Create media container then publish; returns dict with results or errors."""
    # Step 1: create media container
    create_url = f"https://graph.facebook.com/{FB_API_VERSION}/{ig_id}/media"
    if mime.startswith("image"):
        payload = {
            "image_url": media_url,
            "caption": caption,
            "access_token": page_token,
        }
    elif mime.startswith("video"):
        payload = {
            "media_type": "VIDEO",
            "video_url": media_url,
            "caption": caption,
            "access_token": page_token,
        }
    else:
        return {"success": False, "error": "Unsupported MIME type"}

    r1 = requests.post(create_url, data=payload, timeout=60)
    try:
        r1j = r1.json()
    except Exception:
        return {"success": False, "error": f"Create media non-JSON response: {r1.text}", "status_code": r1.status_code}

    if "id" not in r1j:
        return {"success": False, "error": "Failed to create media", "detail": r1j}

    creation_id = r1j["id"]

    # Step 2: publish
    publish_url = f"https://graph.facebook.com/{FB_API_VERSION}/{ig_id}/media_publish"
    publish_payload = {"creation_id": creation_id, "access_token": page_token}
    r2 = requests.post(publish_url, data=publish_payload, timeout=60)
    try:
        r2j = r2.json()
    except Exception:
        return {"success": False, "error": f"Publish non-JSON response: {r2.text}", "status_code": r2.status_code}

    if "id" in r2j:
        return {"success": True, "post_id": r2j["id"], "raw": r2j}
    else:
        return {"success": False, "error": "Failed to publish", "detail": r2j}


# ---------- Streamlit UI ----------

st.set_page_config(page_title="Instagram Bulk Poster", layout="wide")
st.header("📲 Instagram Bulk Poster — Cloudinary upload")

if not IG_USER_ACCESS_TOKEN:
    st.error("Set the IG_USER_ACCESS_TOKEN environment variable before running the app.")
    st.stop()

if not (CLOUD_NAME or os.getenv("CLOUDINARY_URL")):
    st.error("Set Cloudinary credentials (CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET) or CLOUDINARY_URL.")
    st.stop()

col1, col2 = st.columns([1, 2])
with col1:
    uploaded_file = st.file_uploader("Upload image or video", type=["jpg", "jpeg", "png", "gif", "mp4", "mov", "webm", "avi"], help="Images and videos will be uploaded to Cloudinary")
    caption = st.text_area("Caption (optional)", height=120)
    concurrency = st.slider("Concurrent posts", min_value=1, max_value=12, value=CONCURRENCY)
    dry_run = st.checkbox("Dry run (don't publish, just create media)")
    post_button = st.button("Post to all connected IG accounts")

with col2:
    st.markdown("**Instructions:**\n1. Ensure your IG_USER_ACCESS_TOKEN has the required permissions.\n2. Cloudinary credentials set in environment.\n3. Upload a file and click Post.\n")
    status_area = st.empty()

if post_button:
    if not uploaded_file:
        st.warning("Please upload a media file first.")
    else:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        # Check file size
        size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            st.warning(f"File is large ({size_mb:.1f} MB). Cloudinary free tier may limit video sizes. Proceeding anyway.")

        # Detect MIME type
        try:
            # Streamlit's uploaded_file already knows the type
            if uploaded_file.type.startswith("image/"):
                media_type = "IMAGE"
            elif uploaded_file.type.startswith("video/"):
                media_type = "VIDEO"
            else:
                st.error("Unsupported file type")
                st.stop()
        except Exception:
            mime = "application/octet-stream"

        status_area.info(f"Uploading to Cloudinary (detected: {mime}, {size_mb:.1f} MB)")

        try:
            upload_res = upload_to_cloudinary(tmp_path)
        except Exception as e:
            status_area.error(f"Cloudinary upload failed: {e}")
            os.unlink(tmp_path)
            st.stop()

        media_url = upload_res.get("secure_url") or upload_res.get("url")
        resource_type = upload_res.get("resource_type")
        st.success(f"Uploaded to Cloudinary: {media_url} (resource_type={resource_type})")

        # Get pages
        status_area.info("Fetching Pages from Graph API...")
        try:
            pages = get_pages(IG_USER_ACCESS_TOKEN)
        except Exception as e:
            status_area.error(f"Failed to fetch pages: {e}")
            os.unlink(tmp_path)
            st.stop()

        if not pages:
            status_area.warning("No Pages found for this user token.")
            os.unlink(tmp_path)
            st.stop()

        status_area.info(f"Found {len(pages)} Pages. Posting...")

        results = []
        # concurrent posting
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {}
            for page in pages:
                futures[ex.submit(
                    lambda p: post_single_page_task(p, media_url, mime, caption, dry_run),
                    page
                )] = page

            for fut in as_completed(futures):
                page = futures[fut]
                try:
                    res = fut.result()
                except Exception as e:
                    res = {"success": False, "error": str(e), "page": page.get('name')}
                results.append(res)

        # show results
        for r in results:
            if r.get("success"):
                st.success(f"{r.get('page_name')} — posted (id: {r.get('post_id')})")
            else:
                st.error(f"{r.get('page_name', 'unknown')} — failed: {r.get('error') or r.get('detail')}")

        os.unlink(tmp_path)


# ---------- helper task function (defined after main UI to keep readability) ----------

def post_single_page_task(page: dict, media_url: str, mime: str, caption: str, dry_run: bool) -> dict:
    """Task to upload to a single Page's connected IG account."""
    page_id = page.get("id")
    page_name = page.get("name")
    page_token = page.get("access_token")

    out = {"page_id": page_id, "page_name": page_name}

    if not page_token:
        out.update({"success": False, "error": "No page access token"})
        return out

    # Fetch IG id
    try:
        ig_id = get_instagram_id_for_page(page_id, page_token)
    except requests.HTTPError as e:
        try:
            err = e.response.json()
        except Exception:
            err = str(e)
        out.update({"success": False, "error": "Failed to get IG id", "detail": err})
        return out
    except Exception as e:
        out.update({"success": False, "error": f"Failed to get IG id: {e}"})
        return out

    if not ig_id:
        out.update({"success": False, "error": "No IG account linked"})
        return out

    out.update({"ig_id": ig_id})

    if dry_run:
        # create media but do not publish (use create endpoint only)
        try:
            create_url = f"https://graph.facebook.com/{FB_API_VERSION}/{ig_id}/media"
            payload = {
                "image_url": media_url if mime.startswith('image') else None,
                "media_type": 'VIDEO' if mime.startswith('video') else None,
                "video_url": media_url if mime.startswith('video') else None,
                "caption": caption,
                "access_token": page_token,
            }
            # remove None entries
            payload = {k: v for k, v in payload.items() if v is not None}
            r = requests.post(create_url, data=payload, timeout=60).json()
            out.update({"success": True, "detail": r, "note": "dry_run created media (not published)"})
            return out
        except Exception as e:
            out.update({"success": False, "error": f"Dry-run create failed: {e}"})
            return out

    # normal create + publish
    res = create_media_and_publish(ig_id, page_token, media_url, mime, caption)
    out.update(res)
    return out

# End of file
