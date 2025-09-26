# smart_checker.py
"""
Lightweight script that checks if posts are due and triggers the heavy workflow.
This runs every 5 minutes but only takes 1-2 seconds.
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

def check_for_due_posts():
    """
    Quick database check for posts due in the next 10 minutes.
    Returns True if posts are due, False otherwise.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set")
        return False
    
    try:
        # Create lightweight connection (no pool)
        engine = create_engine(database_url, poolclass=NullPool)
        
        # Quick query to check for due posts
        with engine.connect() as conn:
            # Check for posts due in the next 10 minutes that aren't in progress
            check_time = datetime.utcnow() + timedelta(minutes=10)
            
            query = text("""
                SELECT COUNT(*) as count 
                FROM scheduled_posts 
                WHERE scheduled_time <= :check_time 
                AND in_progress = false
            """)
            
            result = conn.execute(query, {"check_time": check_time}).fetchone()
            count = result[0] if result else 0
            
            print(f"📊 Found {count} posts due by {check_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            return count > 0
            
    except Exception as e:
        print(f"❌ Database check error: {e}")
        # On error, trigger the workflow anyway to be safe
        return True

def trigger_heavy_workflow():
    """
    Trigger the heavy posting workflow via GitHub API.
    """
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")  # Format: owner/repo
    
    if not token or not repository:
        print("❌ Missing GITHUB_TOKEN or GITHUB_REPOSITORY")
        return False
    
    # GitHub API endpoint for workflow dispatch
    url = f"https://api.github.com/repos/{repository}/actions/workflows/instagram-poster-heavy.yml/dispatches"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    data = {
        "ref": "main",  # or "master" - your default branch
        "inputs": {
            "triggered_by": "smart_checker",
            "check_time": datetime.utcnow().isoformat()
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 204:
            print("✅ Heavy workflow triggered successfully")
            return True
        else:
            print(f"❌ Failed to trigger workflow: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error triggering workflow: {e}")
        return False

def main():
    """
    Main function - check and trigger if needed.
    """
    print(f"\n{'='*60}")
    print(f"🔍 Smart Checker Started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}")
    
    # Check if posts are due
    posts_due = check_for_due_posts()
    
    if posts_due:
        print("📬 Posts are due! Triggering heavy workflow...")
        success = trigger_heavy_workflow()
        
        if success:
            print("🚀 Heavy poster workflow will run shortly")
            # Log this trigger to avoid duplicate triggers
            log_trigger()
        else:
            print("⚠️ Failed to trigger workflow, will retry next check")
            sys.exit(1)  # Exit with error
    else:
        print("📭 No posts due. Skipping heavy workflow.")
        print("💤 Will check again in 5 minutes")
    
    print(f"{'='*60}")
    print(f"✅ Smart Checker Complete")
    print(f"{'='*60}\n")

def log_trigger():
    """
    Optional: Log that we triggered the workflow to prevent duplicate triggers.
    """
    try:
        # Create a timestamp file to track last trigger
        trigger_file = "/tmp/last_trigger.txt"
        with open(trigger_file, 'w') as f:
            f.write(datetime.utcnow().isoformat())
        print(f"📝 Logged trigger at {datetime.utcnow()}")
    except:
        pass  # Not critical

if __name__ == "__main__":
    main()