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
        "pass": os.getenv("DB_PASS", "Zapril#Secure&Job!2024"),
        "name": os.getenv("DB_NAME", "job_scraper"),
        "type": os.getenv("DB_TYPE", "postgresql"),
        "host": os.getenv("DB_HOST", "34.100.255.74"),
        "instance": os.getenv("INSTANCE_CONNECTION_NAME")
    }

def get_engine():
    config = get_db_config()
    user = urllib.parse.quote_plus(config["user"])
    password = urllib.parse.quote_plus(config["pass"])
    
    if config["instance"]:
        # Cloud SQL Unix Socket connection (pg8000 format)
        socket_path = f"/cloudsql/{config['instance']}"
        db_url = f"postgresql+pg8000://{user}:{password}@/{config['name']}?unix_sock={socket_path}/.s.PGSQL.5432"
    else:
        # Local/Public IP connection
        db_url = f"{config['type']}+pg8000://{user}:{password}@{config['host']}/{config['name']}"
    return create_engine(db_url)

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
        "enabled_platforms": ["linkedin", "indeed", "glassdoor", "naukri", "foundit", "internshala", "google"]
    }

def run_scraper_task(phase=False, jobs=3, cities=3):
    """Background task to run the scraper schedule."""
    try:
        cmd = [sys.executable, "schedule_runner.py"]
        if phase:
            cmd.extend(["--phase", "--jobs", str(jobs), "--cities", str(cities)])
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        with open("job_scraper.log", "a") as log_file:
            log_file.write(f"\n--- Scraping Started at {datetime.now()} (Phase: {phase}) ---\n")
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=log_file,
                env=env,
                text=True
            )
            process.wait()
            log_file.write(f"--- Scraping Finished at {datetime.now()} ---\n")
    except Exception as e:
        with open("job_scraper.log", "a") as log_file:
            log_file.write(f"FAILED TO RUN SCRAPER: {str(e)}\n")

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
                base_query += " AND LOWER(location) = LOWER(:location)"
                params['location'] = location
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

@app.route("/api/jobs/<int:job_id>")
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
    """Manually trigger the full or phased scraping schedule."""
    try:
        settings = load_settings()
        phase = settings.get("phased_scraping", True)
        jobs = settings.get("jobs_per_phase", 3)
        cities = settings.get("cities_per_phase", 3)
        
        # Run in background to avoid HTTP timeout (503)
        thread = threading.Thread(target=run_scraper_task, args=(phase, jobs, cities))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "success",
            "message": f"Scraping started in background (Phase Mode: {phase})"
        })
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

@app.route("/api/run-test")
def run_test():
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
            with open(filename, "r") as f:
                lines = f.readlines()
                return jsonify({"logs": "".join(lines[-1000:])})
        return jsonify({"logs": "No logs found."})
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
        engine = get_engine()
        with engine.connect() as conn:
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify({"total_jobs": 0, "cities": 0, "companies": 0, "locations_list": [], "sources_list": []})
            
            # Combined count query
            stats_query = "SELECT COUNT(*), COUNT(DISTINCT location), COUNT(DISTINCT company) FROM jobs"
            stats_result = conn.execute(text(stats_query)).first()
            total_jobs, unique_cities_count, unique_companies = stats_result if stats_result else (0, 0, 0)
            
            # Get list of unique locations for filters (Limit to avoid memory explosion if ever needed, but 3k is fine)
            locations_result = conn.execute(text("SELECT DISTINCT location FROM jobs WHERE location IS NOT NULL AND location != '' ORDER BY location"))
            locations = [row[0] for row in locations_result]
            
            # Get list of unique sources
            sources_result = conn.execute(text("SELECT DISTINCT source FROM jobs WHERE source IS NOT NULL ORDER BY source"))
            sources = [row[0] for row in sources_result]

            return jsonify({
                "total_jobs": total_jobs,
                "cities": unique_cities_count,
                "companies": unique_companies,
                "locations_list": locations,
                "sources_list": sources
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
