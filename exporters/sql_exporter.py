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
        
    db_user = os.environ.get("DB_USER", "postgres")
    db_pass = os.environ.get("DB_PASS", "ZaprilPassword123!")
    db_name = os.environ.get("DB_NAME", "job_data")
    db_host = os.environ.get("DB_HOST", "34.100.255.74")
    db_port = os.environ.get("DB_PORT", "5432")
    db_type = os.environ.get("DB_TYPE", "postgresql")
    instance_conn_name = os.environ.get("INSTANCE_CONNECTION_NAME")

    if not all([db_user, db_pass, db_name]):
        console.print("[red]✗ Cloud SQL credentials missing in environment variables.[/]")
        return False

    try:
        if instance_conn_name:
            # Unix socket connection
            socket_path = f"/cloudsql/{instance_conn_name}"
            if db_type == "postgresql":
                engine_url = f"postgresql+pg8000://{db_user}:{db_pass}@/{db_name}?unix_sock={socket_path}/.s.PGSQL.5432"
            else:
                engine_url = f"mysql+pymysql://{db_user}:{db_pass}@/{db_name}?unix_socket={socket_path}"
        else:
            # IP connection
            if db_type == "postgresql":
                engine_url = f"postgresql+pg8000://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            else:
                engine_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            
        engine = create_engine(engine_url)

        
        # Prepare data: convert objects to strings
        df_sql = df.copy()
        for col in df_sql.columns:
            if df_sql[col].dtype == 'object':
                df_sql[col] = df_sql[col].astype(str)

        # Custom insertion with ON CONFLICT DO NOTHING for PostgreSQL
        if db_type == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
            from sqlalchemy import Table, MetaData
            
            metadata = MetaData()
            # Reflect the table schema
            table = Table(table_name, metadata, autoload_with=engine)
            
            with engine.connect() as conn:
                records = df_sql.to_dict(orient='records')
                stmt = insert(table).values(records)
                # This is the magic: skip if job_url already exists
                upsert_stmt = stmt.on_conflict_do_nothing(index_elements=['job_url'])
                conn.execute(upsert_stmt)
                conn.commit()
            
            console.print(f"[green]☁️ Successfully synchronized {len(df_sql)} jobs (skipped duplicates).[/]")
        else:
            # Fallback for non-postgres if needed, but we use postgres
            df_sql.to_sql(table_name, engine, if_exists="append", index=False)
            console.print(f"[green]☁️ Successfully exported {len(df_sql)} jobs to Cloud SQL.[/]")
            
        return True
    except Exception as e:
        console.print(f"[red]✗ Failed to export to Cloud SQL: {str(e)}[/]")
        return False
