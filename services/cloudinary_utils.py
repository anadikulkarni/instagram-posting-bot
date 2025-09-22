import streamlit as st
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=st.secrets["cloudinary"]["cloud_name"],
    api_key=st.secrets["cloudinary"]["api_key"],
    api_secret=st.secrets["cloudinary"]["api_secret"],
)

def upload_to_cloudinary(file):
    try:
        res = cloudinary.uploader.upload(file, resource_type="auto")
        return res["secure_url"], res["public_id"], res["resource_type"]
    except Exception as e:
        return None, None, str(e)

def delete_from_cloudinary(public_id, media_type):
    try:
        cloudinary.uploader.destroy(public_id, resource_type=media_type)
    except Exception:
        pass