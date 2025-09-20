import streamlit as st
from datetime import timezone, timedelta
from utils.auth import require_auth, logout_button
from db import utils as db_rest  # Supabase REST helper

require_auth()
logout_button()

st.title("📜 Logs of Past Posts")

IST = timezone(timedelta(hours=5, minutes=30))  # IST offset

# ------------------------
# Fetch logs from Supabase
# ------------------------
logs = db_rest.fetch_table("post_logs")

if not logs:
    st.info("No logs yet.")
else:
    data = []
    for l in logs:
        # Convert UTC timestamp string to datetime then to IST
        utc_time = l["timestamp"]
        if isinstance(utc_time, str):
            from datetime import datetime
            utc_dt = datetime.fromisoformat(utc_time.rstrip("Z"))
        else:
            utc_dt = utc_time

        ist_time = utc_dt.replace(tzinfo=timezone.utc).astimezone(IST)

        data.append({
            "ID": l["id"],
            "User": l["username"],
            "Time": ist_time.strftime("%Y-%m-%d %H:%M:%S"),  # IST display
            "Media": l["media_type"],
            "Caption": l["caption"][:100] + ("..." if len(l["caption"]) > 100 else ""),
            "Accounts": l["ig_ids"],
            "Results": l["results"],
        })

    st.dataframe(data, width="stretch")