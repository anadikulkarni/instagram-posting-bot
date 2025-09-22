import streamlit as st
from db.utils import SessionLocal
from db.models import Group

def load_groups_from_db():
    db = SessionLocal()
    groups = db.query(Group).all()
    res = {g.name: [acc.ig_id for acc in g.accounts] for g in groups}
    db.close()
    return res

def get_groups_cache(force=False):
    if force or "groups_cache" not in st.session_state:
        st.session_state["groups_cache"] = load_groups_from_db()
    return st.session_state["groups_cache"]