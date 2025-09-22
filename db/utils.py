import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base

engine = create_engine(st.secrets["supabase"]["db_url"])
SessionLocal = sessionmaker(bind=engine)

# Initialize DB tables only once
if "db_initialized" not in st.session_state:
    Base.metadata.create_all(engine)
    st.session_state["db_initialized"] = True