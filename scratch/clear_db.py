import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "ZaprilPassword123!")
DB_NAME = os.getenv("DB_NAME", "job_data")
DB_HOST = os.getenv("DB_HOST", "34.100.255.74")
DB_TYPE = os.getenv("DB_TYPE", "postgresql")

db_url = f"{DB_TYPE}+pg8000://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
engine = create_engine(db_url)

try:
    with engine.begin() as conn:
        print("Connecting to database...")
        # Check if table exists
        table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
        if table_exists:
            print("Truncating 'jobs' table...")
            conn.execute(text("TRUNCATE TABLE jobs"))
            print("Successfully cleared all job data.")
        else:
            print("Table 'jobs' does not exist. Nothing to clear.")
except Exception as e:
    print(f"Error: {e}")
