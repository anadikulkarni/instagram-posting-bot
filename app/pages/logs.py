import streamlit as st
from db.utils import SessionLocal
from db.models import PostLog

st.title("📜 Logs of Past Posts")
db = SessionLocal()
logs = db.query(PostLog).order_by(PostLog.timestamp.desc()).all()
if not logs:
    st.info("No logs yet.")
else:
    data = []
    for l in logs:
        data.append({
            "ID": l.id,
            "User": l.username,
            "Accounts": l.ig_ids,
            "Media": l.media_type,
            "Caption": l.caption[:100] + ("..." if len(l.caption) > 100 else ""), # type: ignore
            "Results": l.results,
            "Time (UTC)": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        })
    st.dataframe(data, width="stretch")
db.close()