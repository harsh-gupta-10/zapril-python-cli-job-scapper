import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
user = os.getenv("DB_USER")
pw = os.getenv("DB_PASS")
host = os.getenv("DB_HOST")
db = os.getenv("DB_NAME")

engine = create_engine(f'postgresql://{user}:{pw}@{host}/{db}')
with engine.connect() as conn:
    res = conn.execute(text("SELECT date_posted FROM jobs WHERE date_posted IS NOT NULL LIMIT 5"))
    for row in res:
        print(f"RAW: {row[0]} TYPE: {type(row[0])}")
