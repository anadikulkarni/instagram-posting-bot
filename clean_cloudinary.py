import streamlit as st
import cloudinary
import cloudinary.api
import cloudinary.uploader

# Configure Cloudinary
cloudinary.config(
    cloud_name="dvbiqmhoo",
    api_key="358538431434132",
    api_secret="MTnwuudPzdiDZ96_tpL_7A60zZ0"
)

st.title("🧹 Cloudinary Cleaner")

# Option 1: Delete all assets
if st.button("Delete ALL files"):
    try:
        result = cloudinary.api.delete_all_resources()
        st.success(f"Deleted all assets: {result}")
    except Exception as e:
        st.error(str(e))

# Option 2: Delete by folder
folder = st.text_input("Folder name to delete")
if st.button("Delete folder"):
    try:
        result = cloudinary.api.delete_resources_by_prefix(folder + "/")
        st.success(f"Deleted files in folder {folder}: {result}")
    except Exception as e:
        st.error(str(e))

# Option 3: Delete specific file
public_id = st.text_input("Public ID of file")
if st.button("Delete file"):
    try:
        result = cloudinary.uploader.destroy(public_id)
        st.success(f"Deleted file {public_id}: {result}")
    except Exception as e:
        st.error(str(e))
