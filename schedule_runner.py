import sys
import time
import subprocess
import json
import os
import random
import threading
import psutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows console encoding for Rich emoji output
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
import argparse

console = Console()
state_lock = threading.Lock()

def load_state():
    filename = os.path.join("cache", "scraper_state.json")
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                state = json.load(f)
                # Ensure new fields exist
                if "completed_indices" not in state:
                    state["completed_indices"] = []
                if "running_tasks" not in state:
                    state["running_tasks"] = []
                return state
        except Exception:
            pass
    return {
        "last_search_index": 0, 
        "completed_indices": [], 
        "running_tasks": [],
        "status": "idle"
    }

def save_state(state):
    with state_lock:
        os.makedirs("cache", exist_ok=True)
        filename = os.path.join("cache", "scraper_state.json")
        state["last_updated"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(filename, "w") as f:
            json.dump(state, f, indent=4)

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
        "enabled_platforms": ["linkedin", "indeed", "glassdoor", "naukri", "foundit"],
        "max_parallel_searches": 3
    }

def load_config_list(filename, default_list):
    json_file = filename if filename.endswith(".json") else filename + ".json"
    if os.path.exists(json_file):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    return [item["name"] for item in data if item.get("enabled", True)]
                return data
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {json_file}, falling back to defaults. Error: {e}[/]")
    return default_list

def load_searches():
    filename = "searches.json"
    searches = []
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    searches = [s for s in data if s.get("enabled", True)]
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {filename}. Error: {e}[/]")

    # Fallback to Cartesian product if no searches defined
    if not searches:
        JOB_TYPES = load_config_list("job_titles.json", ["Software Engineer"])
        CITIES = load_config_list("cities.json", ["Bangalore"])
        
        for job in JOB_TYPES:
            for city in CITIES:
                searches.append({
                    "name": f"{job} in {city}",
                    "job_title": job,
                    "location": city,
                    "enabled": True
                })
    
    return searches

# Global list to track active child processes for cleanup
active_child_processes = []
child_processes_lock = threading.Lock()

def run_single_search(idx, search, settings, env, resume):
    global active_child_processes
    
    job = search["job_title"]
    city = search["location"]
    search_name = search.get("name", f"{job} in {city}")
    
    global_max_results = settings.get("max_results_per_scrape", 10)
    hours_old = settings.get("lookback_period_hours", 48)
    global_platforms = settings.get("enabled_platforms", [])
    
    # Update state: Task is now running
    state = load_state()
    task_info = {
        "idx": idx,
        "name": search_name,
        "start_time": datetime.now().strftime('%H:%M:%S')
    }
    if task_info not in state["running_tasks"]:
        state["running_tasks"].append(task_info)
    state["status"] = "running"
    save_state(state)
    
    console.print(f"[bold green]▶ Starting Task [{idx+1}]: {search_name}[/]")
    
    try:
        max_results = search.get("max_results", global_max_results)
        platforms = search.get("platforms", global_platforms)
        
        cmd = [
            sys.executable, "main.py", 
            "--search", job, 
            "--location", city, 
            "--format", "sql", 
            "--max-results", str(max_results),
            "--hours-old", str(hours_old),
            "--verbose", "1" 
        ]
        if resume:
            cmd.append("--resume-state")
        if not settings.get("ai_processing_enabled", True):
            cmd.append("--skip-ai")
        if platforms:
            cmd.extend(["--platforms"] + platforms)
        if search.get("remote"):
            cmd.append("--remote")
        
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            
        process = subprocess.Popen(cmd, env=env, **kwargs)
        
        with child_processes_lock:
            active_child_processes.append(process)
            
        try:
            # 1 hour timeout for a single search/city combo (safety valve)
            process.wait(timeout=3600)
        except subprocess.TimeoutExpired:
            console.print(f"[bold red]✖ Task [{idx+1}] TIMED OUT: {search_name}. Terminating...[/]")
            process.kill()
            process.wait() # Ensure it's reaped
        
        with child_processes_lock:
            if process in active_child_processes:
                active_child_processes.remove(process)
        
        # Mark as completed
        state = load_state()
        if idx not in state["completed_indices"]:
            state["completed_indices"].append(idx)
        # Remove from running
        state["running_tasks"] = [t for t in state["running_tasks"] if t["idx"] != idx]
        save_state(state)
        
        console.print(f"[bold blue]✔ Completed Task [{idx+1}]: {search_name}[/]")
        
        # Optional delay after each task to spread platform load
        delay = random.uniform(5, 15)
        time.sleep(delay)
        
    except Exception as e:
        console.print(f"[red]Error in Task [{idx+1}] {search_name}: {e}[/]")
        state = load_state()
        state["running_tasks"] = [t for t in state["running_tasks"] if t["idx"] != idx]
        save_state(state)

def check_stop_flag():
    if os.path.exists(os.path.join("cache", "stop_scraper.flag")):
        return True
    return False

def run_pipeline(resume=True):
    settings = load_settings()
    max_parallel = settings.get("max_parallel_searches", 3)
    all_searches = load_searches()

    if not all_searches:
        console.print("[red]Error: No enabled searches found.[/]")
        return

    state = load_state() if resume else {
        "last_search_index": 0, 
        "completed_indices": [], 
        "running_tasks": [],
        "status": "idle"
    }
    
    # If starting fresh, clear completed
    if not resume:
        state["completed_indices"] = []
        state["running_tasks"] = []
        save_state(state)

    console.print(f"[bold cyan]🚀 Starting Parallel Pipeline at {datetime.now().strftime('%H:%M:%S')}[/]")
    console.print(f"Total Tasks: {len(all_searches)} searches | Concurrency: {max_parallel}")
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["RUNNING_IN_PIPELINE"] = "1"

    pending_indices = [i for i in range(len(all_searches)) if i not in state.get("completed_indices", [])]
    
    if not pending_indices:
        console.print("[yellow]All tasks already completed. Use --new to start fresh.[/]")
        return

    try:
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = {}
            
            for idx in pending_indices:
                if check_stop_flag():
                    console.print("[bold red]Stop flag detected. Halting new task submission...[/]")
                    break

                # Memory Safety: Don't start new tasks if memory is extremely high (>85%)
                mem = psutil.virtual_memory()
                if mem.percent > 85:
                    console.print(f"[bold yellow]⚠️ High Memory Usage ({mem.percent}%). Waiting for tasks to finish...[/]")
                    # Wait for one of the currently running tasks to finish
                    # This is a simple backoff - we'll check again in 30 seconds
                    time.sleep(30)
                    while psutil.virtual_memory().percent > 85:
                        time.sleep(30)
                        if check_stop_flag(): break

                search = all_searches[idx]
                future = executor.submit(run_single_search, idx, search, settings, env, resume)
                futures[future] = idx
                
                # Small stagger between submissions to avoid overwhelming OS scheduler
                time.sleep(random.uniform(2.0, 5.0))

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    future.result()
                except Exception as e:
                    console.print(f"[red]Task {idx} generated an exception: {e}[/]")

        # Final state check
        state = load_state()
        if len(state.get("completed_indices", [])) >= len(all_searches):
            state["status"] = "completed"
            state["last_search_index"] = 0
            state["completed_indices"] = [] # Reset for next run
        else:
            state["status"] = "partially_completed"
            
        state["running_tasks"] = []
        save_state(state)
        console.print(f"\n[bold green]✅ Pipeline Finished at {datetime.now().strftime('%H:%M:%S')}[/]")

    except KeyboardInterrupt:
        console.print(f"\n[bold red]Interrupted! Cleaning up...[/]")
        # Signal stop
        with open(os.path.join("cache", "stop_scraper.flag"), "w") as f:
            f.write("stop")
            
        # Kill active processes
        with child_processes_lock:
            for p in active_child_processes:
                try:
                    p.terminate()
                except:
                    pass
                    
        state = load_state()
        state["status"] = "interrupted"
        state["running_tasks"] = []
        save_state(state)
        sys.exit(0)

def handle_sigint(signum, frame):
    # If flag already exists, force quit
    if os.path.exists(os.path.join("cache", "stop_scraper.flag")):
        console.print("\n[bold red]Force quitting...[/]")
        sys.exit(1)
        
    console.print()
    console.print("[bold yellow]⚠️ Parallel pipeline is running.[/]")
    try:
        ans = input("Are you sure you want to stop? (y/n): ").strip().lower()
        if ans == 'y':
            console.print("[bold red]Initiating graceful shutdown... Finishing current tasks and exiting.[/]")
            os.makedirs("cache", exist_ok=True)
            with open(os.path.join("cache", "stop_scraper.flag"), "w") as f:
                f.write("stop")
            
            # Note: ThreadPoolExecutor will wait for active threads unless we forcefully exit
            # But the workers check for the stop flag or we kill child processes in run_pipeline's catch
        else:
            console.print("[bold green]Resuming pipeline...[/]")
    except (EOFError, KeyboardInterrupt):
        console.print("\n[bold red]Force quitting...[/]")
        sys.exit(1)

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, handle_sigint)

    parser = argparse.ArgumentParser()
    parser.add_argument("--new", action="store_true", help="Start fresh (ignore saved state)")
    args = parser.parse_args()
    
    run_pipeline(resume=not args.new)


