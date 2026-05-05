from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_config():
    return {
        "user": os.getenv("DB_USER", "postgres"),
        "pass": os.getenv("DB_PASS", "ZaprilPassword123!"),
        "name": os.getenv("DB_NAME", "job_data"),
        "type": os.getenv("DB_TYPE", "postgresql"),
        "host": os.getenv("DB_HOST", "34.100.255.74"),
        "instance": os.getenv("INSTANCE_CONNECTION_NAME")
    }

def get_engine():
    config = get_db_config()
    if config["instance"]:
        socket_path = f"/cloudsql/{config['instance']}"
        db_url = f"postgresql+pg8000://{config['user']}:{config['pass']}@/{config['name']}?unix_sock={socket_path}/.s.PGSQL.5432"
    else:
        db_url = f"{config['type']}+pg8000://{config['user']}:{config['pass']}@{config['host']}/{config['name']}"
    return create_engine(db_url)

try:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'jobs'"))
        for row in result:
            print(f"{row[0]}: {row[1]}")
except Exception as e:
    print(f"Error: {e}")
