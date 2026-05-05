import sys
import time
import subprocess
import json
import os
from datetime import datetime
from rich.console import Console

console = Console()

def load_settings():
    filename = "settings.json"
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "scraping_interval_hours": 48,
        "lookback_period_hours": 48,
        "max_results_per_scrape": 10,
        "enabled_platforms": ["linkedin", "indeed", "glassdoor", "naukri", "foundit"]
    }

def load_list_from_file(filename, default_list):
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                items = [line.strip() for line in f.readlines() if line.strip()]
                return items if items else default_list
    except Exception as e:
        console.print(f"[yellow]Warning: Could not read {filename}, using defaults. Error: {e}[/]")
    return default_list

def run_schedule():
    settings = load_settings()
    max_results = settings.get("max_results_per_scrape", 10)
    hours_old = settings.get("lookback_period_hours", 48)
    platforms = settings.get("enabled_platforms", [])

    JOB_TYPES = load_list_from_file("job_titles.txt", [
        "Software Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer",
        "Data Scientist", "Data Analyst", "Machine Learning Engineer", "DevOps Engineer",
        "Cloud Architect", "Product Manager", "UI/UX Designer", "QA Engineer",
        "Business Analyst", "System Administrator", "Cybersecurity Analyst"
    ])
    
    CITIES = load_list_from_file("cities.txt", [
        "Mumbai", "Bangalore", "New Delhi", "Hyderabad", "Pune",
        "Chennai", "Kolkata", "Ahmedabad", "Gurgaon", "Noida"
    ])

    console.print(f"[bold cyan]Starting scheduled job scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]")
    console.print(f"Config: Max Results: {max_results}, Lookback: {hours_old}h, Platforms: {', '.join(platforms)}")
    console.print(f"Total combinations: {len(JOB_TYPES)} jobs x {len(CITIES)} cities = {len(JOB_TYPES) * len(CITIES)}")
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    for job in JOB_TYPES:
        for city in CITIES:
            console.print(f"\n[bold yellow]>>> Scraping '{job}' in '{city}'...[/]")
            try:
                cmd = [
                    sys.executable, "main.py", 
                    "--search", job, 
                    "--location", city, 
                    "--format", "sql", 
                    "--max-results", str(max_results),
                    "--hours-old", str(hours_old),
                    "--verbose", "0" 
                ]
                # If we had platform selection in main.py, we would add it here
                # cmd.extend(["--platforms", ",".join(platforms)]) 

                subprocess.run(cmd, check=True, env=env)
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error running scraper for {job} in {city}: {e}[/]")
            
            time.sleep(2) # Brief pause between runs

    console.print(f"[bold green]Finished scheduled job scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]")

if __name__ == "__main__":
    run_schedule()
