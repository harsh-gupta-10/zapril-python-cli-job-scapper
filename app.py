import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine, text
from schedule_runner import run_schedule
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="admin/dist")
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
    data = request.json
    password = data.get("password")
    admin_pass = os.getenv("ADMIN_PASSWORD", "ZaprilAdmin2024")
    
    if password == admin_pass:
        return jsonify({"token": "authenticated-session-token"}), 200
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
        result = subprocess.run(cmd, capture_output=True, text=True)
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
    try:
        run_schedule()
        return jsonify({"status": "Scraping schedule completed successfully."}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
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
    app.run(debug=False, host="0.0.0.0", port=port)
