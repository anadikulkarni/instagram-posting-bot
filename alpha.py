import requests

ACCESS_TOKEN = "YOUR_LONG_LIVED_TOKEN"

# 1. Get all Pages + IG IDs
pages = requests.get(
    f"https://graph.facebook.com/v21.0/me/accounts",
    params={"access_token": ACCESS_TOKEN}
).json()["data"]

# 2. Loop through IG accounts
for page in pages:
    ig_id = page.get("instagram_business_account", {}).get("id")
    if not ig_id:
        continue

    # Step 1: Create media
    create_url = f"https://graph.facebook.com/v21.0/{ig_id}/media"
    create_params = {
        "image_url": "https://example.com/photo.jpg",
        "caption": "Hello from automation!",
        "access_token": ACCESS_TOKEN
    }
    creation_id = requests.post(create_url, params=create_params).json()["id"]

    # Step 2: Publish media
    publish_url = f"https://graph.facebook.com/v21.0/{ig_id}/media_publish"
    publish_params = {
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN
    }
    r = requests.post(publish_url, params=publish_params)
    print(f"Posted to {page['name']}: {r.json()}")
