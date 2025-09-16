import requests

# Replace with your IG business account IDs + long-lived tokens
accounts = [
    {"ig_id": "IG_ID_1", "token": "TOKEN_1"},
    {"ig_id": "IG_ID_2", "token": "TOKEN_2"},
    {"ig_id": "IG_ID_3", "token": "TOKEN_3"},
    {"ig_id": "IG_ID_4", "token": "TOKEN_4"},
    {"ig_id": "IG_ID_5", "token": "TOKEN_5"},
]

IMAGE_URL = "https://www.nilons.com/upload/categories/1568195411_296649.png"
CAPTION = "Hello from automation! 🚀"

def post_to_instagram(ig_id, token, image_url, caption):
    try:
        # Step 1: Create media object
        create_url = f"https://graph.facebook.com/v21.0/{ig_id}/media"
        create_params = {
            "image_url": image_url,
            "caption": caption,
            "access_token": token
        }
        create_resp = requests.post(create_url, params=create_params).json()
        
        if "id" not in create_resp:
            print(f"[ERROR] Failed creating media for {ig_id}: {create_resp}")
            return
        
        creation_id = create_resp["id"]

        # Step 2: Publish media
        publish_url = f"https://graph.facebook.com/v21.0/{ig_id}/media_publish"
        publish_params = {
            "creation_id": creation_id,
            "access_token": token
        }
        publish_resp = requests.post(publish_url, params=publish_params).json()
        
        if "id" in publish_resp:
            print(f"[SUCCESS] Posted to IG {ig_id}: {publish_resp['id']}")
        else:
            print(f"[ERROR] Failed publishing for {ig_id}: {publish_resp}")
    
    except Exception as e:
        print(f"[EXCEPTION] {ig_id}: {e}")

# Loop through all accounts
for acc in accounts:
    post_to_instagram(acc["ig_id"], acc["token"], IMAGE_URL, CAPTION)
