import streamlit as st
from db.utils import SessionLocal
from db.models import Group, GroupAccount
from services.instagram_api import get_instagram_accounts
from utils.cache import get_groups_cache
from utils.auth import require_auth, logout_button, require_role

# Require authentication and admin role
require_auth()
require_role("admin")
logout_button()

st.title("👥 Manage Groups")
st.caption("Admin Only - Create and manage account groups")

# Get all Instagram accounts (this should ALWAYS work independently of groups)
ig_accounts = get_instagram_accounts()
if not ig_accounts:
    st.error("❌ No linked accounts.")
    st.stop()

# Get groups for display/management
groups_cache = get_groups_cache()

# Create group
st.subheader("➕ Create New Group")
with st.form("create_group_form", clear_on_submit=True):
    gname = st.text_input("New Group Name")
    gaccounts = st.multiselect(
        "Accounts", 
        list(ig_accounts.keys()), 
        format_func=lambda x: ig_accounts[x]
    )
    if st.form_submit_button("Create Group", use_container_width=True):
        if gname and gaccounts:
            db = SessionLocal()
            try:
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
                    get_groups_cache(force=True)
                    st.rerun()
            finally:
                db.close()
        else:
            st.warning("⚠️ Please provide a group name and select at least one account")

st.markdown("---")

# List groups
st.subheader("📋 Existing Groups")
if not groups_cache:
    st.info("No groups created yet")
else:
    for gname, members in groups_cache.items():
        # Show group with member names
        member_names = [ig_accounts.get(ig, f"Unknown ({ig})") for ig in members]
        
        with st.expander(f"📌 **{gname}** ({len(members)} accounts)"):
            st.write("**Accounts in this group:**")
            for name in member_names:
                st.write(f"  • {name}")
            
            if st.button(f"🗑️ Delete Group", key=f"del_{gname}", type="secondary"):
                db = SessionLocal()
                try:
                    grp = db.query(Group).filter_by(name=gname).first()
                    if grp:
                        db.delete(grp)
                        db.commit()
                        get_groups_cache(force=True)
                        st.success(f"🗑️ Deleted group '{gname}'")
                        st.info("ℹ️ Note: Individual accounts are still accessible for posting")
                        st.rerun()
                finally:
                    db.close()

# Show all available accounts for reference
st.markdown("---")
st.subheader("📱 All Available Instagram Accounts")
st.caption(f"Total: {len(ig_accounts)} accounts")
for ig_id, name in ig_accounts.items():
    st.write(f"✅ {name} (`{ig_id}`)")