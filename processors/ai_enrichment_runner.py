import os
import sys
from pathlib import Path

# Add root directory to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

import json
import pandas as pd
from sqlalchemy import create_engine, text
import urllib.parse
from dotenv import load_dotenv
from rich.console import Console

# Now we can import from processors because root_dir is in sys.path
from processors.description_improver import DescriptionImprover

load_dotenv()
console = Console()

def get_engine():
    user = urllib.parse.quote_plus(os.getenv("DB_USER", "postgres"))
    password = urllib.parse.quote_plus(os.getenv("DB_PASS", ""))
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "postgres")
    db_type = os.getenv("DB_TYPE", "postgresql")
    
    db_url = f"{db_type}+pg8000://{user}:{password}@{host}:{port}/{name}"
    return create_engine(db_url)

def run_ai_enrichment(limit=100):
    try:
        engine = get_engine()
        improver = DescriptionImprover()
        
        if not improver.enabled and not improver.google_enabled:
            console.print("[bold red]Error: AI processing is disabled in settings or no API keys found.[/]")
            return
            
        console.print(f"[bold cyan]🔍 Fetching the last {limit} jobs from database...[/]")
        
        with engine.connect() as conn:
            # Check if table exists
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                console.print("[red]Error: 'jobs' table does not exist.[/]")
                return

            # Fetch last N jobs
            # Note: We fetch jobs that might NOT have been processed yet or just the last ones.
            # Usually, jobs with empty skills/key_takeaways are the ones needing processing.
            # But we follow user instruction: "last hundred jobs"
            query = text("""
                SELECT id, title, company, location, date_posted, source, job_url, description, skills, key_takeaways 
                FROM jobs 
                ORDER BY date_posted DESC 
                LIMIT :limit
            """)
            result = conn.execute(query, {"limit": limit})
            rows = [dict(row._mapping) for row in result]
            
            if not rows:
                console.print("[yellow]No jobs found in database.[/]")
                return
                
            df = pd.DataFrame(rows)
            console.print(f"[green]Found {len(df)} jobs.[/]")
            
            # Process with AI
            console.print(f"[cyan]✨ Enhancing {len(df)} job descriptions using AI (Hackclub API)...[/]")
            
            skills_list = []
            takeaways_list = []
            cleaned_desc_list = []
            
            for idx, row in df.iterrows():
                console.print(f"[dim]Processing {idx+1}/{len(df)}: {row['title']} @ {row['company']}[/]")
                res = improver.improve_description(row["description"])
                
                skills_list.append(json.dumps(res.get("skills", [])))
                takeaways_list.append(json.dumps(res.get("key_takeaways", [])))
                cleaned_desc_list.append(res.get("cleaned_description", row["description"]))
                
                if (idx + 1) % 5 == 0:
                    console.print(f"[green]Completed {idx+1} jobs...[/]")
            
            df["skills"] = skills_list
            df["key_takeaways"] = takeaways_list
            df["description"] = cleaned_desc_list
            
            console.print("[bold cyan]💾 Updating database with enriched data...[/]")
            
            # Update each row in the database
            # We use the 'id' (which is the primary key) to update
            update_query = text("""
                UPDATE jobs 
                SET description = :description, 
                    skills = :skills, 
                    key_takeaways = :key_takeaways 
                WHERE id = :id
            """)
            
            update_count = 0
            with engine.begin() as update_conn:
                for _, row in df.iterrows():
                    update_conn.execute(update_query, {
                        "description": row["description"],
                        "skills": row["skills"],
                        "key_takeaways": row["key_takeaways"],
                        "id": row["id"]
                    })
                    update_count += 1
            
            console.print(f"[bold green]✅ Successfully enriched and updated {update_count} jobs in the database.[/]")

    except Exception as e:
        console.print(f"[bold red]Error during AI enrichment: {str(e)}[/]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # If a limit is provided as an argument, use it
    limit = 100
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
            
    run_ai_enrichment(limit=limit)
