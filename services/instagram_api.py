import requests
import time
from services.aws_utils import delete_from_cloudinary
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

def create_and_process_container(ig_id, media_url, caption, media_type, wait_time=180):
    """
    Create a container and wait for it to process without excessive status checks.
    Returns container_id if successful, None otherwise.
    """
    # Step 1: Create container
    create_url = f"https://graph.facebook.com/v21.0/{ig_id}/media"
    params = {"caption": caption, "access_token": ACCESS_TOKEN}
    
    if media_type == "video":
        params["media_type"] = "REELS"
        params["video_url"] = media_url
    else:
        params["image_url"] = media_url
        params["media_type"] = "IMAGE"
    
    try:
        resp = requests.post(create_url, params=params).json()
        if "id" not in resp:
            print(f"❌ Failed to create container for {ig_id}: {resp}")
            return None
        
        container_id = resp["id"]
        print(f"✅ Container created for {ig_id}: {container_id}")
        
        # Step 2: Wait generously for processing (no status checks during wait)
        print(f"⏳ Waiting {wait_time} seconds for processing...")
        time.sleep(wait_time)
        
        # Step 3: Check status once after waiting
        status = requests.get(
            f"https://graph.facebook.com/v21.0/{container_id}",
            params={"fields": "status_code", "access_token": ACCESS_TOKEN},
        ).json()
        
        status_code = status.get("status_code")
        print(f"📊 Container {container_id} status after wait: {status_code}")
        
        if status_code in ("FINISHED", "READY"):
            return container_id
        elif status_code == "IN_PROGRESS":
            # Give it one more chance with additional wait (120 seconds for videos)
            additional_wait = 120 if media_type == "video" else 30
            print(f"⏳ Still processing, waiting additional {additional_wait} seconds...")
            time.sleep(additional_wait)
            
            # Final status check
            status = requests.get(
                f"https://graph.facebook.com/v21.0/{container_id}",
                params={"fields": "status_code", "access_token": ACCESS_TOKEN},
            ).json()
            
            status_code = status.get("status_code")
            print(f"📊 Final status: {status_code}")
            
            if status_code in ("FINISHED", "READY"):
                return container_id
        
        print(f"❌ Container failed or timed out: {status}")
        return None
        
    except Exception as e:
        print(f"❌ Exception creating/processing container: {e}")
        return None

def publish_container(ig_id, container_id):
    """
    Attempt to publish a ready container.
    Returns published media ID or None.
    """
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            publish_resp = requests.post(
                f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
                params={"creation_id": container_id, "access_token": ACCESS_TOKEN},
            ).json()
            
            if "id" in publish_resp:
                return publish_resp["id"]
            
            # Check for "media not ready" error
            err = publish_resp.get("error", {})
            if err.get("code") == 9007 and attempt < max_retries - 1:
                # Media not ready, wait and retry
                wait_time = 15 * (attempt + 1)
                print(f"⏳ Media not ready for publish, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            
            print(f"❌ Publish failed: {publish_resp}")
            return None
            
        except Exception as e:
            print(f"❌ Exception during publish: {e}")
            return None
    
    return None

def post_to_instagram(ig_ids, media_url, caption, public_id, media_type, username: str):
    """
    Post to Instagram by creating a warm-up container for EACH account.
    Each account gets its own container with generous processing time.
    """
    results = []
    
    if not ig_ids:
        return results
    
    # Get account names for user-friendly results
    all_accounts = get_instagram_accounts()
    
    print(f"\n{'='*60}")
    print(f"🚀 Starting Instagram posting for {len(ig_ids)} accounts")
    print(f"📹 Media type: {media_type}")
    print(f"⏱️  Strategy: Individual warm-up container per account")
    print(f"{'='*60}\n")
    
    # Determine wait times based on media type (tripled for better processing)
    if media_type == "video":
        initial_wait = 180  # 3 minutes for first video account
        subsequent_wait = 180  # 3 minutes for other video accounts
    else:
        initial_wait = 45  # 45 seconds for images
        subsequent_wait = 30  # 30 seconds for other images
    
    containers_created = {}
    
    # Phase 1: Create warm-up containers for all accounts sequentially
    print("📦 PHASE 1: Creating containers for all accounts")
    print("-" * 40)
    
    for index, ig_id in enumerate(ig_ids):
        account_name = all_accounts.get(ig_id, ig_id)  # Use name if available, fallback to ID
        print(f"\n🔄 Account {index + 1}/{len(ig_ids)}: {account_name}")
        
        # Add delay between container creations to avoid rate limiting
        if index > 0:
            delay = 5  # 5 seconds between container creations
            print(f"⏳ Waiting {delay} seconds before next container...")
            time.sleep(delay)
        
        # Determine wait time for this account
        wait_time = initial_wait if index == 0 else subsequent_wait
        
        # Create and process container with appropriate wait time
        container_id = create_and_process_container(
            ig_id, media_url, caption, media_type, wait_time
        )
        
        if container_id:
            containers_created[ig_id] = container_id
            print(f"✅ Container ready for {account_name}")
        else:
            print(f"❌ Container failed for {account_name}")
            results.append(f"❌ {account_name}: Container processing failed")
    
    # Phase 2: Publish all ready containers
    print(f"\n{'='*60}")
    print("📤 PHASE 2: Publishing ready containers")
    print("-" * 40)
    
    for ig_id, container_id in containers_created.items():
        account_name = all_accounts.get(ig_id, ig_id)  # Use name if available, fallback to ID
        print(f"\n📱 Publishing to {account_name}...")
        
        # Small delay between publishes
        time.sleep(2)
        
        publish_id = publish_container(ig_id, container_id)
        
        if publish_id:
            results.append(f"✅ {account_name}: Published (ID: {publish_id})")
            print(f"✅ Successfully published to {account_name}")
        else:
            results.append(f"❌ {account_name}: Publish failed")
            print(f"❌ Failed to publish to {account_name}")
    
    # Add results for accounts that didn't get containers created
    for ig_id in ig_ids:
        account_name = all_accounts.get(ig_id, ig_id)  # Use name if available, fallback to ID
        if ig_id not in containers_created and not any(account_name in r for r in results):
            results.append(f"❌ {account_name}: Container creation failed")
    
    # Cleanup media from AWS/Cloudinary
    delete_from_cloudinary(public_id, media_type)
    print(f"\n✅ Deleted from S3: {public_id}")
    
    # Log to DB
    log_post(username, ig_ids, caption, media_type, results)
    
    # Summary
    successful = len([r for r in results if "✅" in r])
    print(f"\n{'='*60}")
    print(f"📊 SUMMARY: {successful}/{len(ig_ids)} accounts posted successfully")
    if successful < len(ig_ids):
        print("💡 Tip: Failed accounts may have stricter processing limits")
        print("    Consider reducing video size/duration for better success")
    print(f"{'='*60}\n")
    
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