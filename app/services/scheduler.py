import datetime
from db.utils import SessionLocal
from db.models import ScheduledPost
from services.instagram_api import post_to_instagram
from services.cloudinary_utils import delete_from_cloudinary
import streamlit as st

SCHEDULE_RUN_INTERVAL = 60

def schedule_post(ig_ids, caption, media_url, public_id, media_type, local_dt_tz):
    utc_dt = local_dt_tz.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    db.add(ScheduledPost(
        ig_ids=",".join(ig_ids),
        caption=caption,
        media_url=media_url,
        public_id=public_id,
        media_type=media_type,
        scheduled_time=utc_dt
    ))
    db.commit()
    db.close()

def run_scheduled_posts():
    db = SessionLocal()
    now = datetime.datetime.utcnow()
    due = db.query(ScheduledPost).filter(ScheduledPost.scheduled_time <= now).all()
    results = []
    for post in due:
        igs = post.ig_ids.split(",")
        results.extend(post_to_instagram(igs, post.media_url, post.caption, post.public_id, post.media_type))
        try:
            db.delete(post)
            db.commit()
        except:
            pass
    db.close()
    return results

def run_scheduled_posts_if_due():
    now = datetime.datetime.utcnow()
    last = st.session_state.get("last_scheduled_run")
    if last and (now - last).total_seconds() < SCHEDULE_RUN_INTERVAL:
        return []
    st.session_state["last_scheduled_run"] = now
    return run_scheduled_posts()