import os
import pandas as pd
from sqlalchemy import create_engine
from rich.console import Console
from dotenv import load_dotenv

load_dotenv()

console = Console()

def export_to_cloud_sql(df: pd.DataFrame, table_name: str = "jobs"):
    """
    Export the jobs DataFrame to Google Cloud SQL.
    Requires environment variables:
    DB_USER, DB_PASS, DB_NAME, DB_HOST (or INSTANCE_CONNECTION_NAME)
    """
    if df.empty:
        return False
        
    db_user = os.environ.get("DB_USER")
    db_pass = os.environ.get("DB_PASS")
    db_name = os.environ.get("DB_NAME")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_type = os.environ.get("DB_TYPE", "postgresql") # postgresql or mysql

    if not all([db_user, db_pass, db_name]):
        console.print("[red]⚠ Cloud SQL credentials missing in environment variables. Need DB_USER, DB_PASS, DB_NAME.[/]")
        return False

    try:
        instance_conn_name = os.environ.get("INSTANCE_CONNECTION_NAME")
        
        if instance_conn_name:
            if db_type == "postgresql":
                engine_url = f"postgresql+pg8000://{db_user}:{db_pass}@/{db_name}?unix_sock=/cloudsql/{instance_conn_name}/.s.PGSQL.5432"
            else:
                engine_url = f"mysql+pymysql://{db_user}:{db_pass}@/{db_name}?unix_socket=/cloudsql/{instance_conn_name}"
        else:
            if db_type == "postgresql":
                engine_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            else:
                engine_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            
        engine = create_engine(engine_url)
        
        # We need to make sure lists/dicts are strings for SQL
        df_sql = df.copy()
        for col in df_sql.columns:
            if df_sql[col].dtype == 'object':
                df_sql[col] = df_sql[col].astype(str)
                
        # To avoid duplicates in SQL, you could implement an upsert or just append.
        # For simplicity, we append.
        df_sql.to_sql(table_name, engine, if_exists="append", index=False)
        console.print(f"[green]☁️ Successfully exported {len(df_sql)} jobs to Cloud SQL table '{table_name}'.[/]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Failed to export to Cloud SQL: {str(e)}[/]")
        return False
