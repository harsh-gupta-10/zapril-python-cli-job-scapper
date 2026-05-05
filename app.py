import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, text
from schedule_runner import run_schedule
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="admin/dist")
# Restrict CORS to allowed origins in production
if os.getenv("FLASK_ENV") == "production":
    CORS(app, origins=["https://zapril.com", "https://*.run.app"]) # Update with your domain
else:
    CORS(app) # Enable CORS for development

# Database configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "ZaprilPassword123!")
DB_NAME = os.getenv("DB_NAME", "job_data")
DB_TYPE = os.getenv("DB_TYPE", "postgresql")
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")

def get_engine():
    if INSTANCE_CONNECTION_NAME:
        # Cloud SQL Unix Socket connection (pg8000 format)
        db_url = f"postgresql+pg8000://{DB_USER}:{DB_PASS}@/{DB_NAME}?unix_sock=/cloudsql/{INSTANCE_CONNECTION_NAME}/.s.PGSQL.5432"
    else:
        # Local/Public IP connection
        DB_HOST = os.getenv("DB_HOST", "34.100.255.74")
        db_url = f"{DB_TYPE}+pg8000://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
    return create_engine(db_url)

@app.route("/api/debug")
def debug():
    if os.getenv("FLASK_ENV") == "production":
        return jsonify({"error": "Unauthorized"}), 403
    import sys
    import subprocess
    try:
        packages = subprocess.check_output([sys.executable, "-m", "pip", "list"]).decode()
        return jsonify({
            "python_executable": sys.executable,
            "python_version": sys.version,
            "pip_list": packages,
            "instance_connection": INSTANCE_CONNECTION_NAME
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/login", methods=["POST"])
def login():
    import time
    data = request.json
    password = data.get("password")
    
    # Securely retrieve admin password from environment ONLY
    admin_pass = os.getenv("ADMIN_PASSWORD")
    
    if not admin_pass:
        return jsonify({"error": "Admin password not configured on server"}), 500
    
    if password == admin_pass:
        return jsonify({"token": "authenticated-session-token"}), 200
    
    # Artificial delay to prevent brute-force attacks
    time.sleep(1.5)
    return jsonify({"error": "Invalid password"}), 401

@app.route("/api/jobs")
def get_jobs():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Check if table exists first
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify([])
                
            result = conn.execute(text("SELECT * FROM jobs ORDER BY date_posted DESC LIMIT 500"))
            jobs = [dict(row._mapping) for row in result]
            # Convert datetime objects to strings
            for job in jobs:
                for key, value in job.items():
                    if hasattr(value, "isoformat"):
                        job[key] = value.isoformat()
            return jsonify(jobs)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/stats")
def get_stats():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Check if table exists first
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify({"total_jobs": 0, "cities": 0, "companies": 0})

            total_jobs = conn.execute(text("SELECT COUNT(*) FROM jobs")).scalar()
            unique_cities = conn.execute(text("SELECT COUNT(DISTINCT location) FROM jobs")).scalar()
            unique_companies = conn.execute(text("SELECT COUNT(DISTINCT company) FROM jobs")).scalar()
            return jsonify({
                "total_jobs": total_jobs,
                "cities": unique_cities,
                "companies": unique_companies
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/run-test")
def run_test():
    import subprocess
    import sys
    try:
        cmd = [
            sys.executable, "main.py", 
            "--search", "Software Engineer", 
            "--location", "Mumbai", 
            "--format", "sql", 
            "--max-results", "5",
            "--verbose", "1"
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8")
        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/run-scraper", methods=["POST", "GET"])
def trigger_scraper():
    import subprocess
    import sys
    from datetime import datetime
    try:
        cmd = [sys.executable, "schedule_runner.py"]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        with open("job_scraper.log", "a") as log_file:
            log_file.write(f"\n--- Scheduled Run Triggered at {datetime.now()} ---\n")
            subprocess.Popen(cmd, env=env, stdout=log_file, stderr=log_file)
            
        return jsonify({"status": "Scraping schedule started in the background."}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/config/cities", methods=["GET", "POST"])
def config_cities():
    try:
        filename = "cities.txt"
        if request.method == "POST":
            data = request.json
            cities = data.get("cities", [])
            with open(filename, "w") as f:
                f.write("\n".join(cities) + "\n")
            return jsonify({"status": "success", "cities": cities})
        else:
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    cities = [line.strip() for line in f.readlines() if line.strip()]
            else:
                cities = []
            return jsonify({"cities": cities})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/config/job-titles", methods=["GET", "POST"])
def config_job_titles():
    try:
        filename = "job_titles.txt"
        if request.method == "POST":
            data = request.json
            job_titles = data.get("job_titles", [])
            with open(filename, "w") as f:
                f.write("\n".join(job_titles) + "\n")
            return jsonify({"status": "success", "job_titles": job_titles})
        else:
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    job_titles = [line.strip() for line in f.readlines() if line.strip()]
            else:
                job_titles = []
            return jsonify({"job_titles": job_titles})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/settings", methods=["GET", "POST"])
def settings_api():
    import json
    filename = "settings.json"
    try:
        if request.method == "POST":
            data = request.json
            with open(filename, "w") as f:
                json.dump(data, f, indent=4)
            return jsonify({"status": "success", "settings": data})
        else:
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    settings = json.load(f)
            else:
                settings = {
                    "scraping_interval_hours": 48,
                    "lookback_period_hours": 48,
                    "max_results_per_scrape": 10,
                    "enabled_platforms": ["linkedin", "indeed", "glassdoor", "naukri", "foundit"]
                }
            return jsonify(settings)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/scraper/trigger-custom", methods=["POST"])
def trigger_custom():
    import subprocess
    import sys
    try:
        data = request.json
        city = data.get("city")
        job_title = data.get("job_title")
        max_results = data.get("max_results", 10)
        hours_old = data.get("hours_old", 48)
        
        if not city or not job_title:
            return jsonify({"error": "city and job_title are required"}), 400
            
        cmd = [
            sys.executable, "main.py", 
            "--search", job_title, 
            "--location", city, 
            "--format", "sql", 
            "--max-results", str(max_results),
            "--hours-old", str(hours_old),
            "--verbose", "1"
        ]
        # Run in background and redirect output to log file
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        with open("job_scraper.log", "a") as log_file:
            log_file.write(f"\n--- Custom Trigger: {job_title} in {city} at {datetime.now()} ---\n")
            subprocess.Popen(cmd, env=env, stdout=log_file, stderr=log_file)
            
        return jsonify({"status": f"Scraping started for {job_title} in {city}."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs")
def get_logs():
    try:
        filename = "job_scraper.log"
        if os.path.exists(filename):
            with open(filename, "r") as f:
                lines = f.readlines()
                # Return last 100 lines
                return jsonify({"logs": "".join(lines[-100:])})
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
            # Check if table exists
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify({"status": "ignored", "message": "Table does not exist.", "deleted_count": 0})
                
            # Cast date_posted (text) to DATE for comparison, only for valid YYYY-MM-DD formats
            # Also delete rows with empty or null date_posted if they are older than 30 days (we'll just clear them if invalid too)
            result = conn.execute(text(f"""
                DELETE FROM jobs 
                WHERE (date_posted ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' AND CAST(date_posted AS DATE) < CURRENT_DATE - INTERVAL '{days} days')
                   OR (date_posted IS NULL OR date_posted = '')
            """))
            deleted_count = result.rowcount
        return jsonify({"status": "success", "deleted_count": deleted_count})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/db/truncate", methods=["POST"])
def db_truncate():
    try:
        engine = get_engine()
        with engine.begin() as conn:
            # Check if table exists
            table_exists = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'jobs')")).scalar()
            if not table_exists:
                return jsonify({"status": "ignored", "message": "Table does not exist."})
                
            conn.execute(text("TRUNCATE TABLE jobs"))
        return jsonify({"status": "success", "message": "All jobs cleared."})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/db/export")
def db_export():
    import csv
    from io import StringIO
    from flask import Response
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM jobs ORDER BY date_posted DESC"))
            jobs = [dict(row._mapping) for row in result]
            
        if not jobs:
            return jsonify({"error": "No data to export"}), 404
            
        si = StringIO()
        cw = csv.DictWriter(si, fieldnames=jobs[0].keys())
        cw.writeheader()
        cw.writerows(jobs)
        
        output = si.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=jobs_export.csv"}
        )
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
