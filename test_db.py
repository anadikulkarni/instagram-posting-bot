from sqlalchemy import create_engine, text

# Replace with your connection string from secrets.toml
DB_URL = "postgresql://postgres:Nilonsdatabase%401962@db.xltjimtqikfgfacryyef.supabase.co:5432/postgres"

def test_connection():
    try:
        engine = create_engine(DB_URL, echo=True, future=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT NOW();"))
            for row in result:
                print("✅ Database connected successfully! Current time:", row[0])
    except Exception as e:
        print("❌ Connection failed:", e)

if __name__ == "__main__":
    test_connection()