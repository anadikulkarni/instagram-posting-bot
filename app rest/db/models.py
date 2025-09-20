# db/models_rest.py
import datetime
import requests
import secrets
from typing import Optional, List, Dict

import streamlit as st

# ---------------------------
# Supabase REST configuration
# ---------------------------
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["service_key"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ---------------------------
# Groups
# ---------------------------
def get_groups() -> List[Dict]:
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/groups?select=*", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def get_group_accounts(group_id: int) -> List[str]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/group_accounts?group_id=eq.{group_id}",
        headers=HEADERS
    )
    resp.raise_for_status()
    return [acc["ig_id"] for acc in resp.json()]

# ---------------------------
# Scheduled Posts
# ---------------------------
def create_scheduled_post(ig_ids: str, caption: str, media_url: str, public_id: str,
                          media_type: str, scheduled_time: datetime.datetime,
                          username: str) -> Dict:
    payload = {
        "ig_ids": ig_ids,
        "caption": caption,
        "media_url": media_url,
        "public_id": public_id,
        "media_type": media_type,
        "scheduled_time": scheduled_time.isoformat(),
        "username": username,
        "in_progress": False
    }
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/scheduled_posts", json=payload, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def fetch_due_scheduled_posts() -> List[Dict]:
    now = datetime.datetime.utcnow().isoformat()
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/scheduled_posts?scheduled_time=lte.{now}&in_progress=eq.false",
        headers=HEADERS
    )
    resp.raise_for_status()
    return resp.json()

def mark_post_in_progress(post_id: int) -> None:
    payload = {"in_progress": True}
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/scheduled_posts?id=eq.{post_id}",
        json=payload,
        headers=HEADERS
    )
    resp.raise_for_status()

# ---------------------------
# Post Logs
# ---------------------------
def log_post(username: str, ig_ids: str, caption: str, media_type: str, results: str) -> None:
    payload = {
        "username": username,
        "ig_ids": ig_ids,
        "caption": caption,
        "media_type": media_type,
        "results": results,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/post_logs", json=payload, headers=HEADERS)
    resp.raise_for_status()

def fetch_post_logs(limit: int = 50) -> List[Dict]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/post_logs?order=timestamp.desc&limit={limit}",
        headers=HEADERS
    )
    resp.raise_for_status()
    return resp.json()

# ---------------------------
# Sessions
# ---------------------------
def create_session(username: str, duration_minutes: int = 60) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.datetime.utcnow() + datetime.timedelta(minutes=duration_minutes)).isoformat()
    payload = {
        "username": username,
        "session_token": token,
        "expires_at": expires
    }
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/sessions", json=payload, headers=HEADERS)
    resp.raise_for_status()
    return token

def validate_session(token: str) -> Optional[str]:
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/sessions?session_token=eq.{token}", headers=HEADERS)
    resp.raise_for_status()
    sessions = resp.json()
    if not sessions:
        return None
    session = sessions[0]
    expires_at = datetime.datetime.fromisoformat(session["expires_at"])
    if expires_at > datetime.datetime.utcnow():
        return session["username"]
    return None

def delete_session(token: str) -> None:
    resp = requests.delete(f"{SUPABASE_URL}/rest/v1/sessions?session_token=eq.{token}", headers=HEADERS)
    resp.raise_for_status()