import os
import sqlalchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import pandas as pd
from processors.description_improver import DescriptionImprover
from rich.console import Console
from rich.progress import track
import json
import time

load_dotenv()
console = Console()

def reprocess():
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    
    if not all([db_user, db_pass, db_host]):
        console.print("[red]Missing DB credentials[/]")
        return

    import urllib.parse
    user = urllib.parse.quote_plus(db_user)
    password = urllib.parse.quote_plus(db_pass)
    
    engine_url = f"postgresql+pg8000://{user}:{password}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(engine_url)
    
    console.print("[cyan]Connecting to database...[/]")
    
    # Query for jobs missing AI content or having 'Not specified' for salary
    query = """
    SELECT job_url, description 
    FROM jobs 
    WHERE skills IS NULL 
       OR skills::text = '[]' 
       OR key_takeaways IS NULL 
       OR key_takeaways::text = '[]' 
       OR salary_expectation IS NULL 
       OR salary_expectation = 'Not specified'
    ORDER BY date_posted DESC
    """
    
    improver = DescriptionImprover()
    
    if not improver.enabled and not improver.google_enabled:
        console.print("[bold red]ERROR: No AI API keys found or working. Please check your .env file.[/]")
        console.print("[yellow]Hackclub-API and GOOGLE_API_KEY are both currently failing or missing.[/]")
        return

    total_processed = 0
    batch_size = 50
    
    while True:
        with engine.connect() as conn:
            # We use a subquery with LIMIT to avoid loading 10k rows at once
            batch_query = f"SELECT * FROM ({query}) as sub LIMIT {batch_size}"
            df = pd.read_sql(text(batch_query), conn)
        
        if df.empty:
            console.print("[green]No more jobs found that need reprocessing![/]")
            break
            
        console.print(f"[yellow]Processing batch of {len(df)} jobs...[/]")
        
        batch_count = 0
        for idx, row in track(df.iterrows(), total=len(df), description=f"Total: {total_processed}"):
            job_url = row['job_url']
            description = row['description']
            
            if not description:
                # Mark as processed with defaults to avoid infinite loop
                res = {"skills": [], "key_takeaways": [], "cleaned_description": "", "salary_expectation": "None"}
            else:
                try:
                    # The improver now automatically checks if the cache entry is complete
                    res = improver.improve_description(description)
                except Exception as e:
                    console.print(f"[red]Error processing {job_url}: {e}[/]")
                    continue
            
            # Update the database
            update_query = text("""
                UPDATE jobs 
                SET skills = :skills, 
                    key_takeaways = :key_takeaways, 
                    description = :cleaned_desc,
                    salary_expectation = :salary
                WHERE job_url = :job_url
            """)
            
            try:
                with engine.connect() as conn:
                    conn.execute(update_query, {
                        "skills": json.dumps(res.get("skills", [])),
                        "key_takeaways": json.dumps(res.get("key_takeaways", [])),
                        "cleaned_desc": res.get("cleaned_description", description if description else ""),
                        "salary": res.get("salary_expectation", "Not specified"),
                        "job_url": job_url
                    })
                    conn.commit()
                batch_count += 1
            except Exception as e:
                console.print(f"[red]DB Update Error: {e}[/]")
            
            # Increase delay to avoid rate limits
            time.sleep(3.0)
            
        total_processed += batch_count
        console.print(f"[bold green]Batch finished. Total reprocessed: {total_processed}[/]")
        
        if batch_count == 0:
            console.print("[red]Could not process any jobs in this batch. Stopping to avoid infinite loop.[/]")
            break
            
    console.print(f"[bold green]✅ All done! Successfully reprocessed {total_processed} jobs.[/]")

if __name__ == "__main__":
    reprocess()
