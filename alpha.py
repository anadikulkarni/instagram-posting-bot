import requests

ACCESS_TOKEN = "EAFj9NZBCpuFQBPVNP9K96VmF0YCvd20lsvidfWPTvi7ZBQvZB91dItskvgrfPkY1WMy3iI8naODmB2m834LZBGWsHXVYw70YBCrKefrlHibN1X5gLnRylVgtCjqbBLraWDdS6ZCeVt4EH7VioCVKgcyoQrIZCa9DZBm3WDyjrPainGgSjMAB9lVXvGqGUUI"

# 1. Get all Pages
pages_resp = requests.get(
    "https://graph.facebook.com/v21.0/me/accounts",
    params={"access_token": ACCESS_TOKEN}
).json()

pages = pages_resp.get("data", [])

for page in pages:  
    page_id = page["id"]
    print(f"\nChecking page: {page['name']} ({page_id})")

    # 🔑 Fetch IG business account for this page
    ig_resp = requests.get(
        f"https://graph.facebook.com/v21.0/{page_id}",
        params={
            "fields": "instagram_business_account",
            "access_token": page["access_token"]  
        }
    ).json()
    print("IG lookup:", ig_resp)

    ig_id = ig_resp.get("instagram_business_account", {}).get("id")
    if not ig_id:
        print("❌ No IG linked here")
        continue

    print(f"✅ Found IG ID: {ig_id}")

    # Step 1: Create media
    create_url = f"https://graph.facebook.com/v21.0/{ig_id}/media"
    create_params = {
        "image_url": "https://www.nilons.com/upload/categories/1568195411_296649.png",
        "caption": "Hello from automation!",
        "access_token": ACCESS_TOKEN
    }
    create_resp = requests.post(create_url, params=create_params).json()
    print("Create response:", create_resp)

    if "id" not in create_resp:
        continue

    # Step 2: Publish media
    publish_url = f"https://graph.facebook.com/v21.0/{ig_id}/media_publish"
    publish_params = {
        "creation_id": create_resp["id"],
        "access_token": ACCESS_TOKEN
    }
    publish_resp = requests.post(publish_url, params=publish_params).json()
    print(f"Publish response for {page['name']}:", publish_resp)
