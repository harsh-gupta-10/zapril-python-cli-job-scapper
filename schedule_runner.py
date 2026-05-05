import sys
import time
import subprocess
import json
import os
from datetime import datetime
from rich.console import Console

import argparse

console = Console()

def load_state():
    filename = os.path.join("cache", "scraper_state.json")
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_job_index": 0, "last_city_index": 0}

def save_state(state):
    os.makedirs("cache", exist_ok=True)
    filename = os.path.join("cache", "scraper_state.json")
    with open(filename, "w") as f:
        json.dump(state, f)

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

def load_config_list(filename, default_list):
    """Loads a list from JSON (with enabled status) or TXT (simple list)."""
    # Try JSON first
    json_file = filename.replace(".txt", ".json")
    if os.path.exists(json_file):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                # If it's a list of objects with 'name' and 'enabled'
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    return [item["name"] for item in data if item.get("enabled", True)]
                # If it's just a list of strings
                return data
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {json_file}, falling back to defaults. Error: {e}[/]")

    # Fallback to TXT
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {filename}, using defaults. Error: {e}[/]")
    return default_list

def run_schedule(phase_mode=False, jobs_per_phase=3, cities_per_phase=3):
    settings = load_settings()
    max_results = settings.get("max_results_per_scrape", 10)
    hours_old = settings.get("lookback_period_hours", 48)
    platforms = settings.get("enabled_platforms", [])

    JOB_TYPES = load_config_list("job_titles.txt", [
        "Software Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer",
        "Data Scientist", "Data Analyst", "Machine Learning Engineer", "DevOps Engineer",
        "Cloud Architect", "Product Manager", "UI/UX Designer", "QA Engineer",
        "Business Analyst", "System Administrator", "Cybersecurity Analyst"
    ])
    
    CITIES = load_config_list("cities.txt", [
        "Mumbai", "Bangalore", "New Delhi", "Hyderabad", "Pune",
        "Chennai", "Kolkata", "Ahmedabad", "Gurgaon", "Noida"
    ])

    state = load_state()
    
    if phase_mode:
        start_job = state["last_job_index"]
        start_city = state["last_city_index"]
        
        # Select subset
        selected_jobs = JOB_TYPES[start_job : start_job + jobs_per_phase]
        selected_cities = CITIES[start_city : start_city + cities_per_phase]
        
        # Handle wrap around if needed
        if len(selected_jobs) < jobs_per_phase and start_job + jobs_per_phase >= len(JOB_TYPES):
            # We reached the end of jobs, maybe start from 0 next time?
            # For now just take what's left
            pass
            
        console.print(f"[bold cyan]Starting PHASED job scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]")
        console.print(f"Phase: Jobs {start_job}-{start_job+len(selected_jobs)} | Cities {start_city}-{start_city+len(selected_cities)}")
        
        jobs_to_process = selected_jobs
        cities_to_process = selected_cities
        
        # Update state for next time
        new_city_index = start_city + cities_per_phase
        new_job_index = start_job
        
        if new_city_index >= len(CITIES):
            new_city_index = 0
            new_job_index = start_job + jobs_per_phase
            
        if new_job_index >= len(JOB_TYPES):
            new_job_index = 0
            
        save_state({"last_job_index": new_job_index, "last_city_index": new_city_index})
    else:
        jobs_to_process = JOB_TYPES
        cities_to_process = CITIES
        console.print(f"[bold cyan]Starting FULL job scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]")

    console.print(f"Config: Max Results: {max_results}, Lookback: {hours_old}h, Platforms: {', '.join(platforms)}")
    console.print(f"Total combinations in this run: {len(jobs_to_process)} jobs x {len(cities_to_process)} cities = {len(jobs_to_process) * len(cities_to_process)}")
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    for job in jobs_to_process:
        for city in cities_to_process:
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
                subprocess.run(cmd, check=True, env=env)
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error running scraper for {job} in {city}: {e}[/]")
            
            time.sleep(2) # Brief pause between runs

    console.print(f"[bold green]Finished job scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", action="store_true", help="Run in phased mode")
    parser.add_argument("--jobs", type=int, default=3, help="Jobs per phase")
    parser.add_argument("--cities", type=int, default=3, help="Cities per phase")
    args = parser.parse_args()
    
    run_schedule(phase_mode=args.phase, jobs_per_phase=args.jobs, cities_per_phase=args.cities)
