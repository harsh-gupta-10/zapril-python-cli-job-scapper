import os
import json
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

LOCATION_GROUPS = {
    'Remote': ['Remote', 'Work from home', 'WFH', 'Anywhere'],
    'Maharashtra': ['Maharashtra', 'Mumbai', 'Pune', 'Nagpur', 'Nashik', 'Thane', 'Navi Mumbai', 'Andheri', 'Bandra', 'Borivali', 'Dadar', 'Goregaon', 'Juhu', 'Kurla', 'Malad', 'Powai', 'Vashi', 'Worli', 'Hinjewadi', 'Kharadi', 'Baner', 'Aundh', 'Viman Nagar', 'Magarpatta', 'Kalyani Nagar', 'Wakad'],
    'Mumbai': ['Mumbai', 'Andheri', 'Bandra', 'Borivali', 'Dadar', 'Goregaon', 'Juhu', 'Kurla', 'Malad', 'Navi Mumbai', 'Thane', 'Powai', 'Vashi', 'Worli'],
    'Delhi NCR': ['Delhi', 'New Delhi', 'Gurgaon', 'Gurugram', 'Noida', 'Faridabad', 'Ghaziabad'],
    'Bangalore': ['Bangalore', 'Bengaluru', 'Koramangala', 'Indiranagar', 'Whitefield', 'Electronic City', 'HSR Layout', 'Jayanagar', 'JP Nagar', 'Bellandur', 'Marathahalli'],
    'Hyderabad': ['Hyderabad', 'Secunderabad', 'HITEC City', 'Gachibowli', 'Madhapur', 'Banjara Hills', 'Jubilee Hills', 'Kondapur'],
    'Chennai': ['Chennai', 'Adyar', 'Anna Nagar', 'T Nagar', 'Velachery', 'Guindy', 'OMR', 'Porur', 'Tambaram'],
    'Pune': ['Pune', 'Hinjewadi', 'Kharadi', 'Baner', 'Aundh', 'Viman Nagar', 'Magarpatta', 'Kalyani Nagar', 'Wakad'],
}

load_dotenv()

app = Flask(__name__, static_folder="admin/dist")
# Restrict CORS to allowed origins in production
if os.getenv("FLASK_ENV") == "production":
    CORS(app, origins=["https://zapril.com", "https://*.run.app"]) # Update with your domain
else:
    CORS(app) # Enable CORS for development

import urllib.parse

def get_db_config():
    return {
        "user": os.getenv("DB_USER", "postgres"),
        "pass": os.getenv("DB_PASS"),
        "name": os.getenv("DB_NAME", "postgres"),
        "type": os.getenv("DB_TYPE", "postgresql"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT", "5432")
    }

def get_engine():
    config = get_db_config()
    user = urllib.parse.quote_plus(config["user"])
    password = urllib.parse.quote_plus(config["pass"]) if config["pass"] else ""
    host = config["host"]
    port = config["port"]
    name = config["name"]
    db_type = config["type"]
    
    db_url = f"{db_type}+pg8000://{user}:{password}@{host}:{port}/{name}"
    return create_engine(db_url)

def load_state():
    filename = os.path.join("cache", "scraper_state.json")
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_search_index": 0, "status": "idle"}

def load_settings():
    filename = "settings.json"
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "scraping_interval_hours": 24,
        "lookback_period_hours": 48,
        "max_results_per_scrape": 20,
        "phased_scraping": True,
        "jobs_per_phase": 3,
        "cities_per_phase": 3,
        "enabled_platforms": ["linkedin", "indeed", "glassdoor", "naukri", "foundit", "internshala", "google"],
        "ai_processing_enabled": True
    }

def rotate_logs(filename="job_scraper.log", max_size_mb=10, backup_count=5):
    """Rotate the log file if it exceeds the maximum size."""
    try:
        if not os.path.exists(filename):
            return
        
        file_size = os.path.getsize(filename)
        if file_size < max_size_mb * 1024 * 1024:
            return

        print(f"Rotating logs... Current size: {file_size / (1024*1024):.2f} MB")
        
        # Simple rotation logic
        for i in range(backup_count - 1, 0, -1):
            s = f"{filename}.{i}"
            d = f"{filename}.{i+1}"
            if os.path.exists(s):
                if os.path.exists(d): os.remove(d)
                os.rename(s, d)
        
        os.rename(filename, f"{filename}.1")
    except Exception as e:
        print(f"Error rotating logs: {e}")

def run_scraper_task(new_run=False):
    """Background task to run the scraper pipeline."""
    try:
        # Ensure logs are rotated before starting a new run
        rotate_logs("job_scraper.log")
        
        cmd = [sys.executable, "schedule_runner.py"]
        if new_run:
            cmd.append("--new")
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        
        # Use utf-8 encoding for the log file
        with open("job_scraper.log", "a", encoding="utf-8") as log_file:
            log_file.write(f"\n--- Pipeline Started at {datetime.now()} (Fresh: {new_run}) ---\n")
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                env=env,
                text=True,
                encoding="utf-8",
                **kwargs
            )
            process.wait()
            log_file.write(f"--- Pipeline Finished at {datetime.now()} ---\n")
    except Exception as e:
        try:
            with open("job_scraper.log", "a", encoding="utf-8") as log_file:
                log_file.write(f"FAILED TO RUN PIPELINE: {str(e)}\n")
        except:
            pass

@app.route("/api/jobs")
def get_jobs():
    try:
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        search = request.args.get('search', default='', type=str)
        location = request.args.get('location', default='', type=str)
        source = request.args.get('source', default='', type=str)

        engine = get_engine()
        with engine.connect() as conn:
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify({"jobs": [], "total": 0})
            
            base_query = "FROM jobs WHERE 1=1"
            params = {}
            
            if search:
                base_query += " AND (LOWER(title) LIKE LOWER(:search) OR LOWER(company) LIKE LOWER(:search))"
                params['search'] = f"%{search}%"
            if location:
                # Find matching group case-insensitive
                matched_key = next((k for k in LOCATION_GROUPS.keys() if k.lower() == location.lower()), None)
                if matched_key:
                    sub_locs = LOCATION_GROUPS[matched_key]
                    or_clauses = []
                    for i, loc in enumerate(sub_locs):
                        or_clauses.append(f"LOWER(location) LIKE LOWER(:loc_{i})")
                        params[f'loc_{i}'] = f"%{loc}%"
                    base_query += f" AND ({' OR '.join(or_clauses)})"
                else:
                    base_query += " AND LOWER(location) LIKE LOWER(:location)"
                    params['location'] = f"%{location}%"
            if source:
                base_query += " AND source = :source"
                params['source'] = source

            # Get total count for pagination
            total_count = conn.execute(text(f"SELECT COUNT(*) {base_query}"), params).scalar()
            
            # Get paginated data (EXCLUDE DESCRIPTION for memory efficiency)
            query = f"SELECT id, title, company, location, date_posted, source, job_url {base_query} ORDER BY date_posted DESC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = offset
            
            result = conn.execute(text(query), params)
            jobs = [dict(row._mapping) for row in result]
            for job in jobs:
                for key, value in job.items():
                    if hasattr(value, "isoformat"):
                        job[key] = value.isoformat()
            
            return jsonify({
                "jobs": jobs,
                "total": total_count,
                "limit": limit,
                "offset": offset
            })
    except Exception as e:
        import traceback
        print(f"ERROR in get_jobs: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e), "traceback": traceback.format_exc() if os.getenv("FLASK_DEBUG") == "1" else None}), 500

@app.route("/api/jobs/<job_id>")
def get_job_detail(job_id):
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM jobs WHERE id = :id"), {"id": job_id}).first()
            if not result:
                return jsonify({"error": "Job not found"}), 404
            
            job = dict(result._mapping)
            for key, value in job.items():
                if hasattr(value, "isoformat"):
                    job[key] = value.isoformat()
            
            return jsonify(job)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/run-scraper", methods=["POST", "GET"])
def trigger_scraper():
    """Manually trigger the pipeline."""
    try:
        new_run = request.args.get("new", "false").lower() == "true"
        # Also support POST body
        if request.method == "POST" and request.is_json:
            new_run = request.json.get("new", new_run)
        
        # Check if already running
        import psutil
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and "schedule_runner.py" in " ".join(cmdline):
                    return jsonify({
                        "status": "error",
                        "message": "Scraper is already running."
                    }), 400
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Clear stop flag if it exists
        flag_file = os.path.join("cache", "stop_scraper.flag")
        if os.path.exists(flag_file):
            try:
                os.remove(flag_file)
            except Exception:
                pass

        # Run in background to avoid HTTP timeout
        thread = threading.Thread(target=run_scraper_task, args=(new_run,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "success",
            "message": f"Scraper pipeline started (Fresh: {new_run})"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/scraper/status")
def scraper_status():
    """Get the current progress of the pipeline."""
    try:
        state = load_state()
        
        import psutil
        is_running = False
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and "schedule_runner.py" in " ".join(cmdline):
                    is_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        state["is_active"] = is_running
        return jsonify(state)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/scraper/stop", methods=["POST"])
def stop_scraper():
    """Manually stop the pipeline gracefully using a flag file."""
    import psutil
    try:
        is_running = False
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and "schedule_runner.py" in " ".join(cmdline):
                    is_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if is_running:
            os.makedirs("cache", exist_ok=True)
            with open(os.path.join("cache", "stop_scraper.flag"), "w") as f:
                f.write("stop")
            return jsonify({"status": "success", "message": "Graceful stop signal sent to scraper. It will finish the current platform and exit."})
        else:
            return jsonify({"status": "error", "message": "Scraper is not currently running."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/scraper/kill", methods=["POST"])
def kill_scraper():
    """Forcefully terminate the scraper process."""
    import psutil
    import signal
    try:
        killed = False
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and "schedule_runner.py" in " ".join(cmdline):
                    proc.kill() # Force kill
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Also clean up the flag file if it exists
        flag_path = os.path.join("cache", "stop_scraper.flag")
        if os.path.exists(flag_path):
            os.remove(flag_path)
            
        if killed:
            return jsonify({"status": "success", "message": "Scraper process forcefully terminated."})
        else:
            return jsonify({"status": "error", "message": "No active scraper process found to kill."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/scraper/trigger-custom', methods=['POST'])
def trigger_custom_scrape():
    """Run a specific search/location combination immediately."""
    data = request.json
    search = data.get('search')
    location = data.get('location')
    max_results = data.get('max_results', 5)
    
    if not search or not location:
        return jsonify({"status": "error", "message": "Search term and location required"}), 400
        
    try:
        cmd = [
            sys.executable, "main.py",
            "--search", search,
            "--location", location,
            "--max-results", str(max_results),
            "--format", "sql",
            "--verbose", "1"
        ]
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        # We'll run this in background too to avoid timeouts, but log it specially
        def run_custom():
            with open("job_scraper.log", "a") as log_file:
                log_file.write(f"\n--- Custom Scrape: {search} in {location} at {datetime.now()} ---\n")
                subprocess.run(cmd, env=env, stdout=log_file, stderr=log_file)
        
        thread = threading.Thread(target=run_custom)
        thread.start()
        
        return jsonify({
            "status": "success", 
            "message": f"Custom scrape for '{search}' in '{location}' started in background."
        })
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/test-scraper", methods=["POST", "GET"])
def test_scraper():
    """Synchronous test for the dashboard UI to show immediate output."""
    try:
        cmd = [
            sys.executable, "main.py", 
            "--search", "Software Engineer", 
            "--location", "Mumbai", 
            "--format", "sql", 
            "--max-results", "2",
            "--verbose", "1"
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", timeout=45)
        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Test timed out after 45s. Try running in background."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/config/cities", methods=["GET", "POST"])
def config_cities():
    try:
        filename = "cities.json"
        if request.method == "POST":
            data = request.json
            cities = data.get("cities", [])
            with open(filename, "w") as f:
                json.dump(cities, f, indent=4)
            return jsonify({"status": "success", "cities": cities})
        else:
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    cities = json.load(f)
            elif os.path.exists("cities.txt"):
                with open("cities.txt", "r") as f:
                    # Convert old format to new
                    names = [line.strip() for line in f.readlines() if line.strip()]
                    cities = [{"name": name, "enabled": True} for name in names]
            else:
                cities = []
            return jsonify({"cities": cities})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/config/job-titles", methods=["GET", "POST"])
def config_job_titles():
    try:
        filename = "job_titles.json"
        if request.method == "POST":
            data = request.json
            job_titles = data.get("job_titles", [])
            with open(filename, "w") as f:
                json.dump(job_titles, f, indent=4)
            return jsonify({"status": "success", "job_titles": job_titles})
        else:
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    job_titles = json.load(f)
            elif os.path.exists("job_titles.txt"):
                with open("job_titles.txt", "r") as f:
                    # Convert old format to new
                    names = [line.strip() for line in f.readlines() if line.strip()]
                    job_titles = [{"name": name, "enabled": True} for name in names]
            else:
                job_titles = []
            return jsonify({"job_titles": job_titles})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/config/searches", methods=["GET", "POST"])
def config_searches():
    try:
        filename = "searches.json"
        if request.method == "POST":
            data = request.json
            searches = data.get("searches", [])
            with open(filename, "w") as f:
                json.dump(searches, f, indent=4)
            return jsonify({"status": "success", "searches": searches})
        else:
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    searches = json.load(f)
            else:
                searches = []
            return jsonify({"searches": searches})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/settings", methods=["GET", "POST"])
def settings_api():
    filename = "settings.json"
    try:
        if request.method == "POST":
            data = request.json
            with open(filename, "w") as f:
                json.dump(data, f, indent=4)
            return jsonify({"status": "success", "settings": data})
        else:
            return jsonify(load_settings())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs")
def get_logs():
    try:
        filename = "job_scraper.log"
        if os.path.exists(filename):
            # Use utf-8 with replacement to avoid decoding errors
            with open(filename, "r", encoding="utf-8", errors="replace") as f:
                # Read last 2000 lines for better context but without overloading
                lines = f.readlines()
                return jsonify({"logs": "".join(lines[-2000:])})
        return jsonify({"logs": "No logs found."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs/download")
def download_logs():
    try:
        filename = "job_scraper.log"
        if os.path.exists(filename):
            return send_from_directory(os.getcwd(), filename, as_attachment=True)
        return jsonify({"error": "Log file not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs/clear", methods=["DELETE"])
def clear_logs():
    try:
        filename = "job_scraper.log"
        with open(filename, "w") as f:
            f.write(f"Logs cleared at {datetime.now()}\n")
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/db/cleanup", methods=["DELETE"])
def db_cleanup():
    try:
        days = request.args.get('days', 30, type=int)
        engine = get_engine()
        with engine.begin() as conn:
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify({"status": "ignored", "message": "Table does not exist.", "deleted_count": 0})
            result = conn.execute(text(f"""
                DELETE FROM jobs 
                WHERE (date_posted ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' AND CAST(date_posted AS DATE) < CURRENT_DATE - INTERVAL '{days} days')
                   OR (date_posted IS NULL OR date_posted = '')
            """))
            deleted_count = result.rowcount
        return jsonify({"status": "success", "deleted_count": deleted_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/db/truncate", methods=["POST"])
def db_truncate():
    try:
        engine = get_engine()
        with engine.begin() as conn:
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify({"status": "ignored", "message": "Table does not exist."})
            conn.execute(text("TRUNCATE TABLE jobs"))
        return jsonify({"status": "success", "message": "All jobs cleared."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stats")
def get_stats():
    try:
        search = request.args.get('search', default='', type=str)
        location = request.args.get('location', default='', type=str)
        source = request.args.get('source', default='', type=str)

        engine = get_engine()
        with engine.connect() as conn:
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify({"total_jobs": 0, "cities": 0, "companies": 0, "locations_list": [], "sources_list": []})
            
            base_query = "FROM jobs WHERE 1=1"
            params = {}
            
            if search:
                base_query += " AND (LOWER(title) LIKE LOWER(:search) OR LOWER(company) LIKE LOWER(:search))"
                params['search'] = f"%{search}%"
            if location:
                matched_key = next((k for k in LOCATION_GROUPS.keys() if k.lower() == location.lower()), None)
                if matched_key:
                    sub_locs = LOCATION_GROUPS[matched_key]
                    or_clauses = []
                    for i, loc in enumerate(sub_locs):
                        or_clauses.append(f"LOWER(location) LIKE LOWER(:loc_{i})")
                        params[f'loc_{i}'] = f"%{loc}%"
                    base_query += f" AND ({' OR '.join(or_clauses)})"
                else:
                    base_query += " AND LOWER(location) LIKE LOWER(:location)"
                    params['location'] = f"%{location}%"
            if source:
                base_query += " AND source = :source"
                params['source'] = source
                
            # Combined count query with filters
            stats_query = f"SELECT COUNT(*), COUNT(DISTINCT location), COUNT(DISTINCT company) {base_query}"
            stats_result = conn.execute(text(stats_query), params).first()
            total_jobs, unique_cities_count, unique_companies = stats_result if stats_result else (0, 0, 0)
            
            # Get list of unique locations for filters (UNFILTERED)
            locations_result = conn.execute(text("SELECT DISTINCT location FROM jobs WHERE location IS NOT NULL AND location != ''"))
            location_set = set()
            for row in locations_result:
                parts = [p.strip() for p in row[0].split(',')]
                location_set.update(parts)
            locations = sorted(list(location_set))
            
            # Get list of unique sources (UNFILTERED)
            sources_result = conn.execute(text("SELECT DISTINCT source FROM jobs WHERE source IS NOT NULL ORDER BY source"))
            sources = [row[0] for row in sources_result]

            # Get counts per source (FILTERED)
            sources_counts_result = conn.execute(text(f"SELECT source, COUNT(*) {base_query} AND source IS NOT NULL GROUP BY source"), params)
            source_stats = [{"name": row[0], "value": row[1]} for row in sources_counts_result]

            # Get counts per city (base city before comma) (FILTERED)
            cities_counts_result = conn.execute(text(f"SELECT TRIM(SPLIT_PART(location, ',', 1)) as base_city, COUNT(*) as cnt {base_query} AND location IS NOT NULL AND location != '' GROUP BY base_city ORDER BY cnt DESC LIMIT 10"), params)
            city_stats = [{"name": row[0], "count": row[1]} for row in cities_counts_result]

            return jsonify({
                "total_jobs": total_jobs,
                "cities": unique_cities_count,
                "companies": unique_companies,
                "locations_list": locations,
                "sources_list": sources,
                "source_stats": source_stats,
                "city_stats": city_stats
            })
    except Exception as e:
        import traceback
        print(f"ERROR in get_stats: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/login", methods=["POST"])
@app.route("/api/login", methods=["POST"])
def login():
    import time
    try:
        data = request.json
        password = data.get("password")
        admin_pass = os.getenv("ADMIN_PASSWORD", "Zapril#Secure&Job!2024")
        if not admin_pass:
            return jsonify({"error": "Admin password not configured on server"}), 500
        if password == admin_pass:
            return jsonify({"token": "authenticated-session-token"}), 200
        time.sleep(1)
        return jsonify({"error": "Invalid password"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Serve React App
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path != "" and os.path.exists(app.static_folder + "/" + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
