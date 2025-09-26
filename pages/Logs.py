import streamlit as st
from db.utils import SessionLocal
from db.models import PostLog
from datetime import timezone, timedelta
from utils.auth import require_auth, logout_button

require_auth()
logout_button()

st.title("📜 Logs of Past Posts")

IST = timezone(timedelta(hours=5, minutes=30))  # IST offset

db = SessionLocal()
logs = db.query(PostLog).order_by(PostLog.timestamp.desc()).all()

if not logs:
    st.info("No logs yet.")
else:
    data = []
    for l in logs:
        # Convert UTC timestamp to IST
        ist_time = l.timestamp.replace(tzinfo=timezone.utc).astimezone(IST)
        data.append({
            "ID": l.id,
            "User": l.username,
            "Time": ist_time.strftime("%Y-%m-%d %H:%M:%S"),  # IST display
            "Media": l.media_type,
            "Caption": l.caption[:100] + ("..." if len(l.caption) > 100 else ""), # type: ignore
            "Results": l.results,
        })
    st.dataframe(data, width="stretch")

db.close()