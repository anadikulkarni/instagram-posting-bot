import sys
import datetime
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from db.utils import SessionLocal
from db.models import ScheduledPost
from services.instagram_api import post_to_instagram
from sqlalchemy import false

def run_scheduled_posts_cron():
    """
    Standalone function to run scheduled posts.
    Can be triggered by external cron services.
    """    
    db = SessionLocal()
    now = datetime.datetime.utcnow()
    results = []
    
    try:
        # Get all due posts
        due_posts = (
            db.query(ScheduledPost)
            .filter(ScheduledPost.scheduled_time <= now)
            .filter(ScheduledPost.in_progress == false())
            .all()
        )
        
        print(f"Found {len(due_posts)} posts to process at {now}")
        
        for post in due_posts:
            try:
                # Mark as in-progress
                setattr(post, "in_progress", True)
                db.commit()
                
                # Process the post using existing instagram_api function
                ig_ids = post.ig_ids.split(",")
                username = str(post.username)
                
                # Use the existing post_to_instagram function that now uses hybrid config
                post_results = post_to_instagram(
                    ig_ids=ig_ids,
                    media_url=post.media_url,
                    caption=post.caption,
                    public_id=post.public_id,
                    media_type=post.media_type,
                    username=username
                )
                
                results.extend(post_results)
                print(f"Posted: {post_results}")
                
                # Delete after successful processing
                db.delete(post)
                db.commit()
                
            except Exception as e:
                print(f"Error processing post {post.id}: {e}")
                db.rollback()
                # Reset in_progress flag if failed
                setattr(post, "in_progress", False)
                db.commit()
                
    except Exception as e:
        print(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()
    
    return results

if __name__ == "__main__":
    # When run directly, process scheduled posts
    results = run_scheduled_posts_cron()
    print(f"Processed {len(results)} posts")
    for r in results:
        print(r)