from app import get_engine
from sqlalchemy import text

try:
    engine = get_engine()
    with engine.connect() as conn:
        print("Columns in 'jobs' table:")
        result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'jobs'"))
        for row in result:
            print(f"- {row[0]} ({row[1]})")
        
        # Also check if there's data
        count = conn.execute(text("SELECT count(*) FROM jobs")).scalar()
        print(f"Total rows: {count}")
        
except Exception as e:
    print(f"Error: {e}")
