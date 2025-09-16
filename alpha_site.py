import streamlit as st
import requests

# ==============================
# CONFIG
# ==============================
ACCESS_TOKEN = "EAFj9NZBCpuFQBPVNP9K96VmF0YCvd20lsvidfWPTvi7ZBQvZB91dItskvgrfPkY1WMy3iI8naODmB2m834LZBGWsHXVYw70YBCrKefrlHibN1X5gLnRylVgtCjqbBLraWDdS6ZCeVt4EH7VioCVKgcyoQrIZCa9DZBm3WDyjrPainGgSjMAB9lVXvGqGUUI"

st.set_page_config(page_title="Instagram Bulk Poster", page_icon="📷")

st.title("📷 Instagram Bulk Poster")
st.write("Post an image with a caption to all linked Instagram Business Accounts.")

# ==============================
# INPUTS
# ==============================
image_url = st.text_input("Image URL", placeholder="https://example.com/image.png")
caption = st.text_area("Caption", placeholder="Write your caption here...")

if st.button("Post to Instagram"):
    if not image_url or not caption:
        st.error("⚠️ Please provide both an image URL and a caption.")
    else:
        with st.spinner("Posting to Instagram..."):
            results = []
            
            # 1. Get all Pages
            pages_resp = requests.get(
                "https://graph.facebook.com/v21.0/me/accounts",
                params={"access_token": ACCESS_TOKEN}
            ).json()

            pages = pages_resp.get("data", [])

            if not pages:
                st.error("❌ No pages found. Check your access token.")
            else:
                for page in pages:
                    page_id = page["id"]
                    page_name = page["name"]

                    # 🔑 Fetch IG business account for this page
                    ig_resp = requests.get(
                        f"https://graph.facebook.com/v21.0/{page_id}",
                        params={
                            "fields": "instagram_business_account",
                            "access_token": page["access_token"]
                        }
                    ).json()

                    ig_id = ig_resp.get("instagram_business_account", {}).get("id")
                    if not ig_id:
                        results.append(f"❌ {page_name}: No IG linked.")
                        continue

                    # Step 1: Create media
                    create_url = f"https://graph.facebook.com/v21.0/{ig_id}/media"
                    create_params = {
                        "image_url": image_url,
                        "caption": caption,
                        "access_token": ACCESS_TOKEN
                    }
                    create_resp = requests.post(create_url, params=create_params).json()

                    if "id" not in create_resp:
                        results.append(f"❌ {page_name}: Media creation failed → {create_resp}")
                        continue

                    # Step 2: Publish media
                    publish_url = f"https://graph.facebook.com/v21.0/{ig_id}/media_publish"
                    publish_params = {
                        "creation_id": create_resp["id"],
                        "access_token": ACCESS_TOKEN
                    }
                    publish_resp = requests.post(publish_url, params=publish_params).json()

                    if "id" in publish_resp:
                        results.append(f"✅ {page_name}: Post published successfully! (Post ID: {publish_resp['id']})")
                    else:
                        results.append(f"❌ {page_name}: Publish failed → {publish_resp}")

                # Display results
                st.subheader("Results")
                for r in results:
                    st.write(r)