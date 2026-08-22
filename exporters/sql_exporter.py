import os
import ast
import json
import pandas as pd
from sqlalchemy import create_engine, text
from rich.console import Console
from dotenv import load_dotenv

load_dotenv()

console = Console()


def _normalize_json_value(value):
    """Normalize incoming JSON/JSONB values so pg8000 can serialize them safely."""
    if value is None:
        return []
    if isinstance(value, (list, dict)):
        return value
    try:
        if pd.isna(value):
            return []
    except TypeError:
        pass
    if isinstance(value, str):
        raw = value.strip()
        if not raw or raw.lower() in {"nan", "none", "null"}:
            return []

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (list, dict)):
                return parsed
        except json.JSONDecodeError:
            pass

        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, dict)):
                return parsed
        except (ValueError, SyntaxError):
            pass

        if "," in raw:
            return [part.strip() for part in raw.split(",") if part.strip()]
        return [raw]
    return value


def _normalize_text_value(value):
    """Normalize non-JSON values while preserving SQL NULLs."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return str(value)

def export_to_sql(df: pd.DataFrame, table_name: str = "jobs"):
    """
    Export the jobs DataFrame to a SQL database (Supabase/Postgres).
    Requires environment variables:
    DB_USER, DB_PASS, DB_NAME, DB_HOST, DB_PORT
    """
    if df.empty:
        return False
        
    import urllib.parse
    
    db_user = os.environ.get("DB_USER")
    db_pass = os.environ.get("DB_PASS")
    db_name = os.environ.get("DB_NAME", "postgres")
    db_host = os.environ.get("DB_HOST")
    db_port = os.environ.get("DB_PORT", "5432")
    db_type = os.environ.get("DB_TYPE", "postgresql")

    if not all([db_user, db_pass, db_name, db_host]):
        console.print("[red]✗ Database credentials missing in environment variables.[/]")
        console.print(f"[dim]Required: DB_USER, DB_PASS, DB_NAME, DB_HOST. Found: USER={bool(db_user)}, PASS={bool(db_pass)}, NAME={bool(db_name)}, HOST={bool(db_host)}[/]")
        return False

    try:
        user = urllib.parse.quote_plus(db_user)
        password = urllib.parse.quote_plus(db_pass)
        
        # IP connection (Standard for Supabase)
        engine_url = f"{db_type}+pg8000://{user}:{password}@{db_host}:{db_port}/{db_name}"
            
        engine = create_engine(engine_url)

        # Custom insertion with ON CONFLICT DO NOTHING for PostgreSQL (Supabase)
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy import Table, MetaData
        from sqlalchemy.types import JSON
        from sqlalchemy.dialects.postgresql import JSONB
        
        metadata = MetaData()
        # Reflect the table schema
        table = Table(table_name, metadata, autoload_with=engine)

        # Prepare data
        df_sql = df.copy()
        valid_columns = [
            'title', 'company', 'location', 'date_posted', 'source', 'job_url', 'description',
            'skills', 'key_takeaways', 'salary', 'work_experience', 'salary_expectation', 'job_type', 'location_status',
            'resolved_location', 'company_size', 'company_industry'
        ]
        table_columns = set(table.columns.keys())
        export_columns = [col for col in valid_columns if col in df_sql.columns and col in table_columns]
        df_sql = df_sql[export_columns]

        json_columns = {
            col.name
            for col in table.columns
            if isinstance(col.type, (JSON, JSONB))
        }

        for col in df_sql.columns:
            if col in json_columns:
                df_sql[col] = df_sql[col].apply(_normalize_json_value)
            else:
                df_sql[col] = df_sql[col].apply(_normalize_text_value)
        
        with engine.connect() as conn:
            records = df_sql.to_dict(orient='records')
            if not records:
                return True
                
            stmt = insert(table).values(records)
            # Upsert logic: skip if job_url already exists
            upsert_stmt = stmt.on_conflict_do_nothing(index_elements=['job_url'])
            conn.execute(upsert_stmt)
            conn.commit()
        
        console.print(f"[green]☁️ Successfully synchronized {len(df_sql)} jobs to Supabase (skipped duplicates).[/]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Failed to export to SQL: {str(e)}[/]")
        return False

# Maintain backward compatibility alias
def export_to_cloud_sql(df: pd.DataFrame, table_name: str = "jobs"):
    return export_to_sql(df, table_name)
