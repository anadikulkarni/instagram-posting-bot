import streamlit as st
from utils.auth import require_auth, logout_button
from services.instagram_api import get_instagram_accounts
from utils.cache import get_groups_cache
from db import utils as db_rest  # our REST helper

require_auth()
logout_button()

st.title("👥 Manage Groups")
ig_accounts = get_instagram_accounts()
if not ig_accounts:
    st.error("❌ No linked accounts.")

groups_cache = get_groups_cache()


# ------------------------
# Create group
# ------------------------
with st.form("create_group_form", clear_on_submit=True):
    gname = st.text_input("New Group Name")
    gaccounts = st.multiselect(
        "Accounts", list(ig_accounts.keys()), format_func=lambda x: ig_accounts[x]
    )

    if st.form_submit_button("Create Group"):
        if gname and gaccounts:
            # Check if group already exists
            existing = db_rest.fetch_table("groups", filters=f"name=eq.{gname}")
            if existing:
                st.error("❌ Group exists.")
            else:
                # Insert group
                grp = db_rest.insert_row("groups", {"name": gname})[0]  # returns list of inserted rows
                grp_id = grp["id"]

                # Insert group accounts
                for acc in gaccounts:
                    db_rest.insert_row("group_accounts", {"group_id": grp_id, "ig_id": acc})

                st.success(f"✅ Created group {gname}")
                get_groups_cache(force=True)


# ------------------------
# List groups
# ------------------------
for gname, members in groups_cache.items():
    st.write(f"📌 {gname} → {', '.join([ig_accounts.get(ig, ig) for ig in members])}")

    if st.button(f"🗑️ Delete {gname}", key=f"del_{gname}"):
        # Fetch the group ID first
        grp = db_rest.fetch_table("groups", filters=f"name=eq.{gname}")
        if grp:
            grp_id = grp[0]["id"]

            # Delete all associated group accounts
            db_rest.delete_row("group_accounts", "group_id", grp_id)

            # Delete the group
            db_rest.delete_row("groups", "id", grp_id)

        get_groups_cache(force=True)
        st.success(f"🗑️ Deleted {gname}")
        st.rerun()