# config.py - Create this new file
import os

def get_config_value(streamlit_path: list, env_var: str, default=None):
    """
    Get configuration value from Streamlit secrets or environment variables.
    
    Args:
        streamlit_path: List representing the path in st.secrets (e.g., ["supabase", "db_url"])
        env_var: Environment variable name
        default: Default value if neither source has the value
    
    Returns:
        Configuration value
    """
    try:
        # Try Streamlit secrets first (when running in Streamlit)
        import streamlit as st
        value = st.secrets
        for key in streamlit_path:
            value = value[key]
        return value
    except (ImportError, KeyError, AttributeError):
        # Fall back to environment variables (when running in GitHub Actions)
        return os.getenv(env_var, default)

# Configuration getters
def get_database_url():
    return get_config_value(["supabase", "db_url"], "DATABASE_URL")

def get_fb_access_token():
    return get_config_value(["fb_access_token", "ACCESS_TOKEN"], "FB_ACCESS_TOKEN")

def get_cloudinary_config():
    return {
        "cloud_name": get_config_value(["cloudinary", "cloud_name"], "CLOUDINARY_CLOUD_NAME"),
        "api_key": get_config_value(["cloudinary", "api_key"], "CLOUDINARY_API_KEY"), 
        "api_secret": get_config_value(["cloudinary", "api_secret"], "CLOUDINARY_API_SECRET")
    }