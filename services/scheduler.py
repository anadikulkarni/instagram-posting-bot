import datetime
from db.utils import SessionLocal
from db.models import ScheduledPost
from services.instagram_api import post_to_instagram
import streamlit as st
from sqlalchemy import true, false
from sqlalchemy.exc import SQLAlchemyError

SCHEDULE_RUN_INTERVAL = 300  # 5 minutes

def schedule_post(ig_ids, caption, media_url, public_id, media_type, local_dt_tz, username):
    utc_dt = local_dt_tz.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    db.add(ScheduledPost(
        ig_ids=",".join(ig_ids),
        caption=caption,
        media_url=media_url,
        public_id=public_id,
        media_type=media_type,
        scheduled_time=utc_dt,
        username=username,
    ))
    db.commit()
    db.close()

def run_scheduled_posts():
    """
    Run scheduled posts that are due.
    Marks posts as in-progress to prevent duplicate execution.
    Passes the correct username (string) to post_to_instagram for proper logging.
    """
    db = SessionLocal()
    now = datetime.datetime.utcnow()
    results = []

    try:
        due_posts = (
            db.query(ScheduledPost)
            .filter(ScheduledPost.scheduled_time <= now)
            .filter(ScheduledPost.in_progress == false())
            .all()
        )

        for post in due_posts:
            # Mark as in-progress safely
            setattr(post, "in_progress", True)
            db.commit()

            try:
                ig_ids = post.ig_ids.split(",")
                username = str(post.username)  # This is the instance attribute, not the Column
                post_results = post_to_instagram(
                    ig_ids=ig_ids,
                    media_url=post.media_url,
                    caption=post.caption,
                    public_id=post.public_id,
                    media_type=post.media_type,
                    username=username  # ✅ pass actual string
                )
                results.extend(post_results)
            except Exception as e:
                results.append(f"Error processing scheduled post ID {post.id}: {e}")

            # Delete post after processing
            try:
                db.delete(post)
                db.commit()
            except SQLAlchemyError as e:
                db.rollback()
                results.append(f"Error deleting scheduled post ID {post.id}: {e}")

    except SQLAlchemyError as e:
        db.rollback()
        results.append(f"Database error fetching scheduled posts: {e}")
    finally:
        db.close()

    return results