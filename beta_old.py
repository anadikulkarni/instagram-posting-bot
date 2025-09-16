"""
Instagram Graph API bulk poster
- Flask OAuth to obtain tokens and connect Pages+IG accounts
- Stores Page records + long-lived tokens in local SQLite database
- Token refresh handling (exchanges tokens to get new long-lived tokens)
- Safe bulk posting with retries, exponential backoff, concurrency limit, and error handling

How to use (quick):
1. Set environment variables:
   - FB_APP_ID
   - FB_APP_SECRET
   - FB_REDIRECT_URI  (e.g. http://localhost:5000/callback)
2. Start the server: python instagram_graph_api_bulk_poster.py server
   - Open http://localhost:5000/login and complete OAuth with a Facebook user who is admin of all Pages.
   - After callback, the script will save Pages, IG IDs and long-lived tokens to the SQLite DB.
3. Post: python instagram_graph_api_bulk_poster.py post --image-url <url> --caption "My caption"

Notes:
- Each IG account must be a Business/Creator account linked to a unique FB Page.
- Long-lived tokens expire (≈60 days). Use the `refresh_tokens` command regularly (cron) to renew them.
- This script demonstrates a safe, production-minded approach but should be tested carefully before running at scale.

Requirements: pip install flask requests python-dotenv tqdm

"""

import os
import sqlite3
import threading
import time
import math
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import requests
from flask import Flask, redirect, request, jsonify

# ---------- Configuration ----------
FB_APP_ID = os.environ.get("FB_APP_ID")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET")
FB_REDIRECT_URI = os.environ.get("FB_REDIRECT_URI", "http://localhost:5000/callback")
FB_API_VERSION = os.environ.get("FB_API_VERSION", "v21.0")  # adjust if needed
DB_PATH = os.environ.get("IG_DB_PATH", "ig_accounts.db")
CONCURRENCY = int(os.environ.get("IG_CONCURRENCY", "5"))
MAX_RETRIES = int(os.environ.get("IG_MAX_RETRIES", "5"))
BACKOFF_BASE = float(os.environ.get("IG_BACKOFF_BASE", "1.5"))

if not FB_APP_ID or not FB_APP_SECRET:
    logging.warning("FB_APP_ID or FB_APP_SECRET not set. OAuth will fail until you set them.")

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------- Database helpers ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pages (
            page_id TEXT PRIMARY KEY,
            page_name TEXT,
            ig_id TEXT,
            access_token TEXT,
            token_obtained_at INTEGER,
            token_expires_at INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def upsert_page(page_id: str, page_name: str, ig_id: Optional[str], access_token: str, expires_at_ts: Optional[int]):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now_ts = int(time.time())
    cur.execute(
        "INSERT OR REPLACE INTO pages (page_id, page_name, ig_id, access_token, token_obtained_at, token_expires_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (page_id, page_name, ig_id, access_token, now_ts, expires_at_ts),
    )
    conn.commit()
    conn.close()


def get_all_pages() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT page_id, page_name, ig_id, access_token, token_obtained_at, token_expires_at FROM pages")
    rows = cur.fetchall()
    conn.close()
    pages = []
    for r in rows:
        pages.append({
            "page_id": r[0],
            "page_name": r[1],
            "ig_id": r[2],
            "access_token": r[3],
            "token_obtained_at": r[4],
            "token_expires_at": r[5],
        })
    return pages


def update_page_token(page_id: str, new_token: str, expires_at_ts: Optional[int]):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now_ts = int(time.time())
    cur.execute(
        "UPDATE pages SET access_token = ?, token_obtained_at = ?, token_expires_at = ? WHERE page_id = ?",
        (new_token, now_ts, expires_at_ts, page_id),
    )
    conn.commit()
    conn.close()

# ---------- FB / IG API helpers ----------

def build_oauth_url():
    params = {
        "client_id": FB_APP_ID,
        "redirect_uri": FB_REDIRECT_URI,
        "scope": ",".join(["instagram_basic", "instagram_content_publish", "pages_show_list"]),
        "response_type": "code",
    }
    return f"https://www.facebook.com/{FB_API_VERSION}/dialog/oauth?{urlencode(params)}"


def exchange_code_for_short_token(code: str) -> Dict[str, Any]:
    url = f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token"
    params = {
        "client_id": FB_APP_ID,
        "redirect_uri": FB_REDIRECT_URI,
        "client_secret": FB_APP_SECRET,
        "code": code,
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()


def exchange_for_long_lived_token(short_token: str) -> Dict[str, Any]:
    url = f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": short_token,
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()


def refresh_long_lived_token(long_token: str) -> Dict[str, Any]:
    # Meta allows re-exchanging a long-lived token for a new long-lived token using the same endpoint
    # Note: API behavior changes sometimes — test this for your app.
    return exchange_for_long_lived_token(long_token)


def get_user_pages(user_access_token: str) -> List[Dict[str, Any]]:
    url = f"https://graph.facebook.com/{FB_API_VERSION}/me/accounts"
    params = {"access_token": user_access_token}
    pages = []
    while url:
        r = requests.get(url, params=params if url.endswith('/me/accounts') else None)
        r.raise_for_status()
        data = r.json()
        pages.extend(data.get("data", []))
        paging = data.get("paging", {})
        url = paging.get("next")
        params = None
    return pages


def get_instagram_account_id(page_id: str, page_access_token: str) -> Optional[str]:
    url = f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}"
    params = {"fields": "instagram_business_account", "access_token": page_access_token}
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    ig = data.get("instagram_business_account")
    return ig.get("id") if ig else None

# ---------- Posting helpers ----------

def _api_post_with_retries(url: str, params: Dict[str, Any], max_retries=MAX_RETRIES) -> Dict[str, Any]:
    attempt = 0
    while True:
        try:
            r = requests.post(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            # handle transient server errors
            if r.status_code in (500, 502, 503, 504):
                raise requests.HTTPError(f"Server error {r.status_code}")
            # parse body for Graph API error
            try:
                body = r.json()
            except Exception:
                body = {"error": {"message": r.text, "code": r.status_code}}
            error = body.get("error")
            if error:
                code = error.get("code")
                # rate limit / throttling codes vary, apply backoff
                if code in (4, 17, 32, 613):
                    raise requests.HTTPError(f"Rate limit / throttled: {error}")
                # permanent errors should raise
                raise requests.HTTPError(f"Graph API error: {error}")
            r.raise_for_status()
        except Exception as e:
            attempt += 1
            if attempt > max_retries:
                logger.exception("Max retries reached for %s", url)
                raise
            backoff = (BACKOFF_BASE ** attempt) + (attempt * 0.1)
            logger.warning("Request failed (attempt %s/%s): %s. Backing off %.1fs", attempt, max_retries, e, backoff)
            time.sleep(backoff)


def create_media(ig_user_id: str, image_url: str, caption: str, page_access_token: str) -> str:
    url = f"https://graph.facebook.com/{FB_API_VERSION}/{ig_user_id}/media"
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": page_access_token,
    }
    res = _api_post_with_retries(url, params)
    creation_id = res.get("id")
    if not creation_id:
        raise RuntimeError(f"Failed to create media: {res}")
    return creation_id


def publish_media(ig_user_id: str, creation_id: str, page_access_token: str) -> Dict[str, Any]:
    url = f"https://graph.facebook.com/{FB_API_VERSION}/{ig_user_id}/media_publish"
    params = {"creation_id": creation_id, "access_token": page_access_token}
    return _api_post_with_retries(url, params)


def post_to_one(page: Dict[str, Any], image_url: str, caption: str) -> Dict[str, Any]:
    page_name = page.get("page_name")
    page_id = page.get("page_id")
    ig_id = page.get("ig_id")
    token = page.get("access_token")
    if not ig_id:
        raise RuntimeError(f"Page {page_name} ({page_id}) has no linked Instagram account")
    try:
        creation_id = create_media(ig_id, image_url, caption, token)
        publish_res = publish_media(ig_id, creation_id, token)
        logger.info("Posted to %s (page %s): %s", page_name, page_id, publish_res)
        return {"page_id": page_id, "page_name": page_name, "success": True, "detail": publish_res}
    except Exception as e:
        logger.exception("Failed to post to %s (%s)", page_name, page_id)
        return {"page_id": page_id, "page_name": page_name, "success": False, "error": str(e)}

# ---------- Token maintenance ----------

def token_expires_in_seconds(expires_at_ts: Optional[int]) -> Optional[int]:
    if expires_at_ts is None:
        return None
    return expires_at_ts - int(time.time())


def refresh_expiring_tokens(threshold_days: int = 7):
    """Refresh tokens that expire within threshold_days (default 7 days)."""
    pages = get_all_pages()
    for p in pages:
        exp = p.get("token_expires_at")
        if exp is None:
            continue
        secs_left = token_expires_in_seconds(exp)
        if secs_left is None:
            continue
        if secs_left < threshold_days * 24 * 3600:
            try:
                logger.info("Refreshing token for page %s (expires in %ds)", p['page_id'], secs_left)
                new = refresh_long_lived_token(p['access_token'])
                new_token = new.get("access_token")
                # API returns 'expires_in' seconds for new token
                expires_in = new.get("expires_in")
                new_expires_at = int(time.time()) + int(expires_in) if expires_in else None
                if new_token:
                    update_page_token(p['page_id'], new_token, new_expires_at)
                    logger.info("Token refreshed for %s, new expiry in %s seconds", p['page_name'], expires_in)
            except Exception as e:
                logger.exception("Failed to refresh token for %s: %s", p['page_name'], e)

# ---------- Flask OAuth server (for obtaining initial long-lived tokens + pages) ----------
app = Flask(__name__)

@app.route('/')
def index():
    return "Instagram Graph API bulk poster\nGo to /login to connect your Facebook user (who is admin of all Pages)."

@app.route('/login')
def login():
    if not FB_APP_ID or not FB_REDIRECT_URI:
        return "Set FB_APP_ID and FB_REDIRECT_URI environment variables first", 400
    oauth_url = build_oauth_url()
    return redirect(oauth_url)

@app.route('/callback')
def callback():
    error = request.args.get('error')
    if error:
        return f"OAuth error: {error}", 400
    code = request.args.get('code')
    if not code:
        return "No code found in callback", 400
    try:
        short_token_resp = exchange_code_for_short_token(code)
        short_token = short_token_resp.get('access_token')
        if not short_token:
            return jsonify(short_token_resp), 500
        # exchange for long-lived
        long_resp = exchange_for_long_lived_token(short_token)
        long_token = long_resp.get('access_token')
        expires_in = long_resp.get('expires_in')  # seconds
        expires_at_ts = int(time.time()) + int(expires_in) if expires_in else None

        # now use the long token to list pages the user manages
        pages = get_user_pages(long_token)
        saved = 0
        for p in pages:
            page_id = p.get('id')
            page_name = p.get('name')
            page_access_token = p.get('access_token')
            # get instagram_business_account id from the Page
            ig_id = None
            try:
                ig_id = get_instagram_account_id(page_id, page_access_token)
            except Exception:
                logger.exception('Failed to get IG id for page %s', page_id)
            # store with page_access_token (pages tokens can be used to manage IG)
            upsert_page(page_id, page_name, ig_id, page_access_token, None)
            saved += 1

        return f"Connected and saved {saved} pages. You can close this window.", 200
    except Exception as e:
        logger.exception("OAuth callback failed")
        return f"Error during OAuth: {e}", 500

# ---------- CLI functionality ----------

def post_bulk(image_url: str, caption: str, concurrency: int = CONCURRENCY) -> List[Dict[str, Any]]:
    pages = get_all_pages()
    if not pages:
        raise RuntimeError("No pages found in DB. Run OAuth flow first (start server and /login).")
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(post_to_one, p, image_url, caption): p for p in pages}
        for fut in as_completed(futures):
            try:
                res = fut.result()
            except Exception as e:
                res = {"success": False, "error": str(e)}
            results.append(res)
    return results

# ---------- Entrypoint ----------
if __name__ == '__main__':
    import argparse

    init_db()

    parser = argparse.ArgumentParser(description='Instagram Graph API bulk poster utility')
    sub = parser.add_subparsers(dest='cmd')

    server_p = sub.add_parser('server', help='Run Flask OAuth server (visit /login)')
    server_p.add_argument('--host', default='0.0.0.0')
    server_p.add_argument('--port', default=5000, type=int)

    post_p = sub.add_parser('post', help='Post an image to all connected IG accounts')
    post_p.add_argument('--image-url', required=True)
    post_p.add_argument('--caption', default='')
    post_p.add_argument('--concurrency', default=CONCURRENCY, type=int)

    refresh_p = sub.add_parser('refresh_tokens', help='Refresh long-lived tokens that are near expiry')
    refresh_p.add_argument('--threshold-days', default=7, type=int)

    args = parser.parse_args()

    if args.cmd == 'server':
        logger.info("Starting Flask server on %s:%s", args.host, args.port)
        app.run(host=args.host, port=args.port, debug=False)
    elif args.cmd == 'post':
        logger.info("Posting to all pages: image=%s", args.image_url)
        results = post_bulk(args.image_url, args.caption, concurrency=args.concurrency)
        success = sum(1 for r in results if r.get('success'))
        logger.info("Posting complete: %d/%d successful", success, len(results))
        print(json.dumps(results, indent=2))
    elif args.cmd == 'refresh_tokens':
        logger.info("Refreshing tokens with threshold %s days", args.threshold_days)
        refresh_expiring_tokens(args.threshold_days)
        logger.info("Token refresh complete")
    else:
        parser.print_help()
