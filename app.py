import os
from flask import Flask, jsonify
from schedule_runner import run_schedule

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "Job Scraper Cloud Run Service is running."})

@app.route("/run-scraper", methods=["POST", "GET"])
def trigger_scraper():
    # Trigger the scraping job synchronously
    # Cloud Run timeout must be configured to accommodate this (e.g., 60 minutes)
    try:
        run_schedule()
        return jsonify({"status": "Scraping schedule completed successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
