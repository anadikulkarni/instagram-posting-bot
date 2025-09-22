import requests
import time
from services.cloudinary_utils import delete_from_cloudinary
from db.utils import SessionLocal
from db.models import PostLog
import datetime
from config import get_fb_access_token

# Get access token using hybrid config
ACCESS_TOKEN = get_fb_access_token()

def get_instagram_accounts():
    accounts = {}
    pages = requests.get("https://graph.facebook.com/v21.0/me/accounts",
                         params={"access_token": ACCESS_TOKEN}).json()
    for page in pages.get("data", []):
        pid, pname = page["id"], page["name"]
        ig_resp = requests.get(f"https://graph.facebook.com/v21.0/{pid}",
                               params={"fields": "instagram_business_account", "access_token": page["access_token"]}).json()
        igid = ig_resp.get("instagram_business_account", {}).get("id")
        if igid:
            accounts[igid] = pname
    return accounts

def post_to_instagram(ig_ids, media_url, caption, public_id, media_type, username: str):
    results = []
    for ig in ig_ids:
        create_url = f"https://graph.facebook.com/v21.0/{ig}/media"
        params = {"caption": caption, "access_token": ACCESS_TOKEN}
        if media_type == "video":
            params["media_type"] = "REELS"
            params["video_url"] = media_url
        else:
            params["image_url"] = media_url
            params["media_type"] = "IMAGE"

        resp = requests.post(create_url, params=params).json()
        if "id" not in resp:
            results.append(f"❌ {ig}: Creation failed → {resp}")
            continue
        cid = resp["id"]

        # Poll status
        for _ in range(15):
            status = requests.get(f"https://graph.facebook.com/v21.0/{cid}",
                                  params={"fields":"status_code","access_token":ACCESS_TOKEN}).json()
            if status.get("status_code") in ("FINISHED","READY"):
                break
            elif status.get("status_code") == "ERROR":
                results.append(f"❌ {ig}: Processing error → {status}")
                cid = None
                break
            time.sleep(3)

        if not cid:
            continue

        publish = requests.post(f"https://graph.facebook.com/v21.0/{ig}/media_publish",
                                params={"creation_id": cid,"access_token":ACCESS_TOKEN}).json()
        if "id" in publish:
            results.append(f"✅ {ig}: Published (ID: {publish['id']})")
        else:
            results.append(f"❌ {ig}: Publish failed → {publish}")

    delete_from_cloudinary(public_id, media_type)
    log_post(username, ig_ids, caption, media_type, results)
    return results

def log_post(username, ig_ids, caption, media_type, results):
    db = SessionLocal()
    entry = PostLog(
        username=username,
        ig_ids=",".join(ig_ids),
        caption=caption,
        media_type=media_type,
        results="\n".join(results),
        timestamp=datetime.datetime.utcnow()
    )
    db.add(entry)
    db.commit()
    db.close()