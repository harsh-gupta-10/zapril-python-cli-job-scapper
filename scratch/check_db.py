import os
import sqlalchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def check_db():
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME", "postgres")
    
    import urllib.parse
    user = urllib.parse.quote_plus(db_user)
    password = urllib.parse.quote_plus(db_pass)
    
    engine_url = f"postgresql+pg8000://{user}:{password}@{db_host}:5432/{db_name}"
    engine = create_engine(engine_url)
    
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM jobs")).scalar()
        missing_ai = conn.execute(text("""
            SELECT count(*) FROM jobs 
            WHERE skills IS NULL 
               OR skills::text = '[]' 
               OR key_takeaways IS NULL 
               OR key_takeaways::text = '[]' 
               OR salary_expectation IS NULL 
               OR salary_expectation = 'Not specified'
        """)).scalar()
        
        print(f"Total jobs: {total}")
        print(f"Jobs needing AI enrichment: {missing_ai}")

if __name__ == "__main__":
    check_db()
