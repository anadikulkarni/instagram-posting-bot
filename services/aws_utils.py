import boto3
import uuid
import os
from botocore.exceptions import ClientError
from config import get_config_value

# AWS Configuration
AWS_ACCESS_KEY_ID = get_config_value(["aws", "access_key_id"], "AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = get_config_value(["aws", "secret_access_key"], "AWS_SECRET_ACCESS_KEY")
AWS_BUCKET_NAME = get_config_value(["aws", "bucket_name"], "AWS_BUCKET_NAME", "instagram-media-uploads")
AWS_REGION = get_config_value(["aws", "region"], "AWS_REGION", "eu-north-1")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def upload_to_s3(file, folder="uploads"):
    """
    Upload file to AWS S3
    
    Args:
        file: Streamlit uploaded file or file-like object
        folder: S3 folder/prefix (default: "uploads")
    
    Returns:
        tuple: (public_url, s3_key, file_type) or (None, None, error_message)
    """
    try:
        # Generate unique filename
        file_extension = file.name.split('.')[-1].lower() if hasattr(file, 'name') and '.' in file.name else 'bin'
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        s3_key = f"{folder}/{unique_filename}"
        
        # Determine file type
        file_type = "video" if file_extension in ['mp4', 'mov', 'avi', 'mkv'] else "image"
        
        # Set content type for better browser handling
        content_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg', 
            'png': 'image/png',
            'gif': 'image/gif',
            'mp4': 'video/mp4',
            'mov': 'video/quicktime',
            'avi': 'video/x-msvideo'
        }
        content_type = content_type_map.get(file_extension, 'application/octet-stream')
        
        # Upload to S3
        s3_client.upload_fileobj(
            file,
            AWS_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                'ContentType': content_type,
                'ACL': 'public-read'  # Make file publicly accessible
            }
        )
        
        # Generate public URL
        public_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        
        print(f"✅ Uploaded to S3: {s3_key}")
        return public_url, s3_key, file_type
        
    except ClientError as e:
        error_msg = f"S3 upload failed: {e}"
        print(f"❌ {error_msg}")
        return None, None, error_msg
    except Exception as e:
        error_msg = f"Upload error: {e}"
        print(f"❌ {error_msg}")
        return None, None, error_msg

def delete_from_s3(s3_key):
    """
    Delete file from AWS S3
    
    Args:
        s3_key: S3 object key to delete
    """
    try:
        s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=s3_key)
        print(f"✅ Deleted from S3: {s3_key}")
    except Exception as e:
        print(f"⚠️ S3 delete error: {e}")

def check_s3_setup():
    """
    Check if S3 is properly configured
    """
    try:
        # Test connection by listing bucket
        s3_client.head_bucket(Bucket=AWS_BUCKET_NAME)
        print(f"✅ S3 bucket '{AWS_BUCKET_NAME}' is accessible")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"❌ S3 bucket '{AWS_BUCKET_NAME}' does not exist")
        elif error_code == '403':
            print(f"❌ Access denied to S3 bucket '{AWS_BUCKET_NAME}'")
        else:
            print(f"❌ S3 error: {e}")
        return False
    except Exception as e:
        print(f"❌ S3 configuration error: {e}")
        return False

# Backwards compatibility - drop-in replacement for cloudinary functions
def upload_to_cloudinary(file):
    """Drop-in replacement for cloudinary upload"""
    return upload_to_s3(file)

def delete_from_cloudinary(s3_key, media_type):
    """Drop-in replacement for cloudinary delete"""
    delete_from_s3(s3_key)