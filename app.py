"""
Flask Backend - Pierce County Scraper Dashboard
Works locally (reads google_credentials.json file)
Works on Render (reads GOOGLE_CREDENTIALS env variable)
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import gspread
import os
import pickle
import requests as req_lib
import json
from datetime import datetime
import threading
import time
from scraper_engine import run_scraper_for_document

app = Flask(__name__)
CORS(app)

def get_google_sheet():
    try:
        # 1. Check if we have the credentials in an Environment Variable (Vercel/Render)
        env_creds = os.environ.get("GOOGLE_CREDENTIALS")
        
        if env_creds:
            # Parse the string into a dictionary and authenticate via info
            creds_dict = json.loads(env_creds)
            client = gspread.service_account_from_dict(creds_dict)
        else:
            # 2. Fallback to local file (Local development)
            client = gspread.service_account(filename=CREDENTIALS_FILE)
            
        return client.open(GOOGLE_SHEET_NAME).sheet1
        
    except Exception as e:
        print(f"❌ Google Sheets error: {e}")
        return None

# Global job tracking
jobs = {}
job_counter = 0


# ─────────────────────────────────────────
# GOOGLE SHEETS HELPER
# ─────────────────────────────────────────

def get_google_sheet():
    """
    Connect to Google Sheets using modern gspread 6.x API.
    gspread.service_account() replaces the old deprecated gspread.authorize()
    """
    try:
        client = gspread.service_account(filename=CREDENTIALS_FILE)
        return client.open(GOOGLE_SHEET_NAME).sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ Sheet not found: '{GOOGLE_SHEET_NAME}' - check the name and sharing settings")
        return None
    except FileNotFoundError:
        print(f"❌ google_credentials.json not found in project folder")
        return None
    except Exception as e:
        print(f"❌ Google Sheets error: {e}")
        return None


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/sheet/sync', methods=['GET'])
def sync_sheet():
    """Get all rows where Search Status = 'Start'"""
    try:
        sheet = get_google_sheet()
        if not sheet:
            return jsonify({"status": "error", "message": "Could not connect to Google Sheets"}), 500

        all_records = sheet.get_all_records()
        pending_jobs = []

        for idx, record in enumerate(all_records):
            status = str(record.get('Search Status', '')).strip().lower()
            if status == 'start':
                pending_jobs.append({
                    "row": idx + 2,  # +2 accounts for header row and 0-indexing
                    "county": record.get('County', ''),
                    "document_type": record.get('Document Types', ''),
                    "status": status
                })

        return jsonify({
            "status": "success",
            "pending_jobs": pending_jobs,
            "total_rows": len(all_records)
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/sheet/update', methods=['POST'])
def update_sheet():
    """Update a row's status in Google Sheets"""
    try:
        data = request.json
        row = data.get('row')
        status = data.get('status')
        result_file = data.get('result_file', '')

        sheet = get_google_sheet()
        if not sheet:
            return jsonify({"status": "error", "message": "Could not connect to Google Sheets"}), 500

        sheet.update_cell(row, 3, status)
        if result_file:
            sheet.update_cell(row, 4, result_file)

        return jsonify({"status": "success", "message": f"Updated row {row}"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/jobs/start', methods=['POST'])
def start_job():
    """Start a single scraping job manually"""
    global job_counter

    try:
        data = request.json
        document_type = data.get('document_type')
        sheet_row = data.get('row')

        if not document_type:
            return jsonify({"status": "error", "message": "document_type is required"}), 400

        job_counter += 1
        job_id = f"job_{job_counter}_{int(time.time())}"

        jobs[job_id] = {
            "id": job_id,
            "document_type": document_type,
            "sheet_row": sheet_row,
            "status": "queued",
            "progress": [],
            "result": None,
            "started_at": datetime.now().isoformat(),
            "completed_at": None
        }

        # Mark Running in sheet immediately
        if sheet_row:
            try:
                sheet = get_google_sheet()
                if sheet:
                    sheet.update_cell(sheet_row, 3, "Running")
            except:
                pass

        # Start background thread
        thread = threading.Thread(target=run_job_background, args=(job_id, document_type, sheet_row))
        thread.daemon = True
        thread.start()

        return jsonify({"status": "success", "job_id": job_id, "message": f"Started job for {document_type}"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/auto-sync', methods=['POST'])
def auto_sync():
    """Find ALL rows with Search Status = 'Start' and kick off scraping jobs"""
    global job_counter

    try:
        sheet = get_google_sheet()
        if not sheet:
            return jsonify({"status": "error", "message": "Could not connect to Google Sheets"}), 500

        all_records = sheet.get_all_records()
        started_jobs = []

        for idx, record in enumerate(all_records):
            status = str(record.get('Search Status', '')).strip().lower()

            if status == 'start':
                document_type = record.get('Document Types', '')
                row_number = idx + 2

                job_counter += 1
                job_id = f"job_{job_counter}_{int(time.time())}"

                jobs[job_id] = {
                    "id": job_id,
                    "document_type": document_type,
                    "sheet_row": row_number,
                    "status": "queued",
                    "progress": [],
                    "result": None,
                    "started_at": datetime.now().isoformat(),
                    "completed_at": None
                }

                # Update sheet to Running immediately
                sheet.update_cell(row_number, 3, "Running")

                # Launch background thread
                thread = threading.Thread(target=run_job_background, args=(job_id, document_type, row_number))
                thread.daemon = True
                thread.start()

                started_jobs.append({
                    "job_id": job_id,
                    "document_type": document_type,
                    "row": row_number
                })

        return jsonify({
            "status": "success",
            "message": f"Started {len(started_jobs)} job(s)",
            "jobs": started_jobs
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    return jsonify({"status": "success", "jobs": list(jobs.values())})


@app.route('/api/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    if job_id not in jobs:
        return jsonify({"status": "error", "message": "Job not found"}), 404
    return jsonify({"status": "success", "job": jobs[job_id]})


@app.route('/api/results/<path:filename>', methods=['GET'])
def download_result(filename):
    try:
        # Strip any directory separators - only allow simple filenames
        filename = os.path.basename(filename)
        filepath = os.path.join(RESULTS_FOLDER, filename)

        print(f"📥 Download requested: {filename}")
        print(f"📂 Looking at: {os.path.abspath(filepath)}")

        if not os.path.exists(filepath):
            # List available files to help debug
            available = os.listdir(RESULTS_FOLDER) if os.path.exists(RESULTS_FOLDER) else []
            print(f"❌ File not found. Available: {available}")
            return jsonify({
                "status": "error",
                "message": f"File not found: {filename}",
                "available_files": available
            }), 404

        return send_file(os.path.abspath(filepath), as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/results', methods=['GET'])
def list_results():
    """List all available result files"""
    try:
        if not os.path.exists(RESULTS_FOLDER):
            return jsonify({"status": "success", "files": []})
        files = []
        for f in os.listdir(RESULTS_FOLDER):
            if f.endswith('.csv'):
                fpath = os.path.join(RESULTS_FOLDER, f)
                files.append({
                    "filename": f,
                    "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                    "created": datetime.fromtimestamp(os.path.getctime(fpath)).isoformat()
                })
        files.sort(key=lambda x: x["created"], reverse=True)
        return jsonify({"status": "success", "files": files})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/image-proxy', methods=['GET'])
def image_proxy():
    """
    Proxy image/PDF requests through saved session cookies.
    The Pierce County website requires an active session to view images.
    We reuse the cookies saved during the last scraping session.
    Usage: /api/image-proxy?url=https://armsweb.co.pierce.wa.us/...
    """
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "url parameter required"}), 400

    # Only allow Pierce County URLs for security
    if 'armsweb.co.pierce.wa.us' not in target_url:
        return jsonify({"status": "error", "message": "Only Pierce County URLs allowed"}), 403

    try:
        # Load saved session cookies from last scrape
        cookies = {}
        if os.path.exists('session_cookies.pkl'):
            with open('session_cookies.pkl', 'rb') as f:
                selenium_cookies = pickle.load(f)
            cookies = {c['name']: c['value'] for c in selenium_cookies}
            print(f"🍪 Loaded {len(cookies)} session cookies for proxy")
        else:
            print("⚠️ No session cookies found - image may not load")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://armsweb.co.pierce.wa.us/RealEstate/SearchResults.aspx'
        }

        response = req_lib.get(target_url, cookies=cookies, headers=headers, timeout=30)

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            from flask import Response
            return Response(
                response.content,
                status=200,
                content_type=content_type
            )
        else:
            return jsonify({
                "status": "error",
                "message": f"Pierce County returned {response.status_code} - session may have expired. Run a new scrape to refresh cookies."
            }), response.status_code

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────
# BACKGROUND JOB RUNNER
# ─────────────────────────────────────────

def run_job_background(job_id, document_type, sheet_row=None):
    """Runs in background thread - scrapes data and updates Google Sheet when done"""

    def log(message):
        if job_id in jobs:
            jobs[job_id]["progress"].append({
                "time": datetime.now().isoformat(),
                "message": message
            })

    try:
        jobs[job_id]["status"] = "running"
        result = run_scraper_for_document(document_type, log)

        jobs[job_id]["status"] = result["status"]
        jobs[job_id]["result"] = result
        jobs[job_id]["completed_at"] = datetime.now().isoformat()

        # Update Google Sheet with final result
        if sheet_row:
            try:
                sheet = get_google_sheet()
                if sheet:
                    if result["status"] == "success":
                        sheet.update_cell(sheet_row, 3, "Complete")
                        sheet.update_cell(sheet_row, 4, result.get("filepath", ""))
                    else:
                        sheet.update_cell(sheet_row, 3, "Error")
                        sheet.update_cell(sheet_row, 4, result.get("message", "Unknown error"))
            except Exception as e:
                print(f"⚠️ Could not update Google Sheet after job: {e}")

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["result"] = {"status": "error", "message": str(e)}
        jobs[job_id]["completed_at"] = datetime.now().isoformat()


# ─────────────────────────────────────────
# START SERVER
# ─────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"🚀 Starting Pierce County Scraper on port {port}")
    print(f"📁 Results folder: {RESULTS_FOLDER}")
    print(f"🔗 Google Sheet: {GOOGLE_SHEET_NAME}")
    app.run(debug=debug, host='0.0.0.0', port=port)
