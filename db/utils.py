from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from config import get_database_url

DATABASE_URL = get_database_url()

if not DATABASE_URL:
    raise ValueError("No database URL found. Set DATABASE_URL environment variable or configure Streamlit secrets.")

# Use NullPool to avoid connection timeout issues
# This creates a new connection each time instead of pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # Don't pool connections - create fresh ones
    pool_pre_ping=True,  # Test connections before using them
    connect_args={
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000"  # 30 second statement timeout
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)