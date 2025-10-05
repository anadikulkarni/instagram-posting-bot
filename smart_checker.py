# smart_checker.py
"""
Lightweight script that checks if posts are due and triggers the heavy workflow.
This runs every 15 minutes but only takes 1-2 seconds.
Includes distributed locking to prevent concurrent workflow runs.
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Lock configuration using database
LOCK_TIMEOUT_MINUTES = 120  # Max time a lock can be held

def acquire_db_lock():
    """
    Try to acquire a database lock to prevent concurrent workflow runs.
    Returns True if lock acquired, False if another workflow is running.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set")
        return False
    
    try:
        engine = create_engine(database_url, poolclass=NullPool)
        
        with engine.connect() as conn:
            # Create lock table if it doesn't exist
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS workflow_locks (
                    lock_name VARCHAR(100) PRIMARY KEY,
                    locked_at TIMESTAMP NOT NULL,
                    locked_by VARCHAR(200)
                )
            """))
            conn.commit()
            
            # Check for existing lock
            result = conn.execute(text("""
                SELECT locked_at, locked_by 
                FROM workflow_locks 
                WHERE lock_name = 'instagram_poster'
            """)).fetchone()
            
            if result:
                locked_at, locked_by = result
                age = datetime.utcnow() - locked_at
                age_minutes = age.total_seconds() / 60
                
                if age_minutes < LOCK_TIMEOUT_MINUTES:
                    print(f"⏳ Lock held by '{locked_by}' for {age_minutes:.1f} minutes")
                    print(f"⏭️  Skipping - another workflow is running")
                    return False
                else:
                    # Stale lock (workflow probably failed), remove it
                    print(f"🧹 Removing stale lock ({age_minutes:.1f} minutes old)")
                    conn.execute(text("""
                        DELETE FROM workflow_locks 
                        WHERE lock_name = 'instagram_poster'
                    """))
                    conn.commit()
            
            # Acquire lock
            run_id = os.getenv("GITHUB_RUN_ID", "local_test")
            
            conn.execute(text("""
                INSERT INTO workflow_locks (lock_name, locked_at, locked_by) 
                VALUES ('instagram_poster', :now, :run_id)
                ON CONFLICT (lock_name) 
                DO UPDATE SET locked_at = :now, locked_by = :run_id
            """), {"now": datetime.utcnow(), "run_id": run_id})
            conn.commit()
            
            print(f"🔒 Lock acquired by run '{run_id}'")
            return True
            
    except Exception as e:
        print(f"❌ Error acquiring lock: {e}")
        # On error, allow workflow to proceed (fail-open for safety)
        return True

def release_db_lock():
    """
    Release the database lock after workflow completes.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return
    
    try:
        engine = create_engine(database_url, poolclass=NullPool)
        
        with engine.connect() as conn:
            run_id = os.getenv("GITHUB_RUN_ID", "local_test")
            
            conn.execute(text("""
                DELETE FROM workflow_locks 
                WHERE lock_name = 'instagram_poster' 
                AND locked_by = :run_id
            """), {"run_id": run_id})
            conn.commit()
            
            print("🔓 Lock released")
            
    except Exception as e:
        print(f"⚠️ Error releasing lock: {e}")

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
    
    # Try to acquire lock first
    if not acquire_db_lock():
        print("💤 Will check again in 15 minutes")
        print(f"{'='*60}\n")
        return  # Exit gracefully without triggering
    
    try:
        # Check if posts are due
        posts_due = check_for_due_posts()
        
        if posts_due:
            print("📬 Posts are due! Triggering heavy workflow...")
            success = trigger_heavy_workflow()
            
            if success:
                print("🚀 Heavy poster workflow will run shortly")
                print("⚠️  Lock will be held until heavy workflow completes")
            else:
                print("⚠️ Failed to trigger workflow, will retry next check")
                release_db_lock()  # Release lock on failure
                sys.exit(1)
        else:
            print("📭 No posts due. Skipping heavy workflow.")
            print("💤 Will check again in 15 minutes")
            release_db_lock()  # Release lock immediately if no posts
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        release_db_lock()  # Always release lock on error
        raise
    
    print(f"{'='*60}")
    print(f"✅ Smart Checker Complete")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()