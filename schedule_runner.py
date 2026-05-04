import sys
import time
import subprocess
from datetime import datetime
from rich.console import Console

console = Console()

def load_list_from_file(filename, default_list):
    try:
        with open(filename, 'r') as f:
            # Read lines, strip whitespace, and filter out empty lines
            items = [line.strip() for line in f.readlines() if line.strip()]
            return items if items else default_list
    except Exception as e:
        console.print(f"[yellow]Warning: Could not read {filename}, using defaults. Error: {e}[/]")
        return default_list

# Load dynamic lists
JOB_TYPES = load_list_from_file("job_titles.txt", [
    "Software Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer",
    "Data Scientist", "Data Analyst", "Machine Learning Engineer", "DevOps Engineer",
    "Cloud Architect", "Product Manager", "UI/UX Designer", "QA Engineer",
    "Business Analyst", "System Administrator", "Cybersecurity Analyst"
])

CITIES = load_list_from_file("cities.txt", [
    "Mumbai", "Bangalore", "New Delhi", "Hyderabad", "Pune",
    "Chennai", "Kolkata", "Ahmedabad", "Gurgaon", "Noida",
    "Jaipur", "Chandigarh", "Lucknow", "Indore", "Kochi",
    "Thiruvananthapuram", "Bhopal", "Visakhapatnam", "Surat", "Nagpur"
])

def run_schedule():
    console.print(f"[bold cyan]Starting scheduled job scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]")
    console.print(f"Total combinations: {len(JOB_TYPES)} jobs x {len(CITIES)} cities = {len(JOB_TYPES) * len(CITIES)}")
    
    for job in JOB_TYPES:
        for city in CITIES:
            console.print(f"\n[bold yellow]>>> Scraping '{job}' in '{city}'...[/]")
            try:
                # We call main.py using subprocess to isolate memory and avoid global state issues
                cmd = [
                    sys.executable, "main.py", 
                    "--search", job, 
                    "--location", city, 
                    "--format", "sql", 
                    "--max-results", "20",
                    # Reduce verbosity to avoid filling up logs
                    "--verbose", "0" 
                ]
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error running scraper for {job} in {city}: {e}[/]")
            
            # Sleep between runs to avoid rate limits
            time.sleep(5)

    console.print(f"[bold green]Finished scheduled job scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]")

if __name__ == "__main__":
    run_schedule()
