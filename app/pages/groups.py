import streamlit as st
from db.utils import SessionLocal
from db.models import Group, GroupAccount
from services.instagram_api import get_instagram_accounts
from utils.cache import get_groups_cache
from utils.auth import require_auth, logout_button

require_auth()
logout_button()

st.title("👥 Manage Groups")
ig_accounts = get_instagram_accounts()
if not ig_accounts:
    st.error("❌ No linked accounts.")


groups_cache = get_groups_cache()

# Create group
with st.form("create_group_form", clear_on_submit=True):
    gname = st.text_input("New Group Name")
    gaccounts = st.multiselect("Accounts", list(ig_accounts.keys()), format_func=lambda x: ig_accounts[x])
    if st.form_submit_button("Create Group"):
        if gname and gaccounts:
            db = SessionLocal()
            if db.query(Group).filter_by(name=gname).first():
                st.error("❌ Group exists.")
            else:
                grp = Group(name=gname)
                db.add(grp)
                db.commit()
                for acc in gaccounts:
                    db.add(GroupAccount(group_id=grp.id, ig_id=acc))
                db.commit()
                st.success(f"✅ Created group {gname}")
            db.close()
            get_groups_cache(force=True)

# List groups
for gname, members in groups_cache.items():
    st.write(f"📌 {gname} → {', '.join([ig_accounts.get(ig, ig) for ig in members])}")
    if st.button(f"🗑️ Delete {gname}", key=f"del_{gname}"):
        db = SessionLocal()
        grp = db.query(Group).filter_by(name=gname).first()
        if grp:
            db.delete(grp)
            db.commit()
        db.close()
        get_groups_cache(force=True)
        st.success(f"🗑️ Deleted {gname}")
        st.rerun()