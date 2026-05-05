from sqlalchemy import create_engine, text
import os

def cleanup():
    # Use environment variables if possible, otherwise hardcoded for this one-off
    db_url = "postgresql+pg8000://postgres:ZaprilPassword123!@34.100.255.74/job_data"
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("Cleaning up duplicates...")
        # Remove duplicates keeping the first occurrence
        conn.execute(text("DELETE FROM jobs WHERE ctid NOT IN (SELECT min(ctid) FROM jobs GROUP BY job_url)"))
        
        print("Adding unique constraint...")
        # Add unique constraint to prevent future duplicates
        try:
            conn.execute(text("ALTER TABLE jobs ADD CONSTRAINT unique_job_url UNIQUE (job_url)"))
        except Exception as e:
            print(f"Constraint might already exist or error: {e}")
            
        conn.commit()
        print("Database cleaned and constraint added!")

if __name__ == "__main__":
    cleanup()
