import cloudinary
import cloudinary.uploader
from config import get_cloudinary_config

# Configure Cloudinary using hybrid config
config = get_cloudinary_config()
cloudinary.config(
    cloud_name=config["cloud_name"],
    api_key=config["api_key"],
    api_secret=config["api_secret"],
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