from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import get_database_url

DATABASE_URL = get_database_url()

if not DATABASE_URL:
    raise ValueError("No database URL found. Set DATABASE_URL environment variable or configure Streamlit secrets.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)