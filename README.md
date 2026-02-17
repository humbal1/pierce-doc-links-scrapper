# Pierce County Document Scraper - Web Dashboard

## 🎯 Overview

A fully automated web dashboard that:
- ✅ Connects to your Google Sheets
- ✅ Monitors for "Start" status in the Search Status column
- ✅ Automatically scrapes Pierce County documents **in headless mode** (no browser window)
- ✅ Saves results as CSV files
- ✅ Updates Google Sheets with completion status

## 📋 Prerequisites

1. **Python 3.8+** installed
2. **Google Cloud Project** with Sheets API enabled
3. **Chrome/Chromium** installed (for headless browsing)

---

## 🚀 QUICK START GUIDE

### Step 1: Google Sheets API Setup (5 minutes)

1. Go to https://console.cloud.google.com/
2. Create new project → Enable "Google Sheets API" and "Google Drive API"
3. Create Service Account → Download JSON key
4. Rename to `google_credentials.json`
5. Copy the service account email from the JSON
6. Share your Google Sheet with that email (Editor access)

### Step 2: Install and Run (2 minutes)

```bash
pip install -r requirements.txt
python app.py
```

### Step 3: Use Dashboard

1. Open http://localhost:5000
2. In Google Sheets, set Search Status to "Start"
3. Click "Auto-Sync" button
4. Watch it scrape in background!

---

## 📁 Project Files

```
├── app.py                    # Flask backend
├── scraper_engine.py         # Headless scraper
├── templates/index.html      # Dashboard UI
├── requirements.txt          # Dependencies
├── google_credentials.json   # Your Google API key
└── results/                  # CSV outputs
```

---

## 🌐 Deployment (Choose One)

### ⭐ Render.com (Recommended - Free)

1. Sign up at render.com
2. New Web Service → Connect GitHub
3. Build: `pip install -r requirements.txt`
4. Start: `python app.py`
5. Add `google_credentials.json` content as secret
6. Deploy!

### Railway.app

1. Sign up at railway.app
2. New Project → Deploy from GitHub
3. Add `google_credentials.json` as environment variable
4. Auto-deploys!

### Your Own VPS

```bash
git clone your-repo
cd pierce-county-scraper
pip3 install -r requirements.txt
nohup python3 app.py &
```

---

## 🔧 How It Works

1. Set "Start" in Google Sheet → System detects it
2. Launches headless Chrome (invisible)
3. Scrapes Pierce County website
4. Saves CSV to results folder
5. Updates Sheet status to "Complete"

**All happens in background - no browser windows!**

---

## 📊 API Endpoints

- `POST /api/auto-sync` - Start all pending jobs
- `GET /api/jobs` - List all jobs
- `GET /api/results/{file}` - Download CSV

---

## 🛠️ Troubleshooting

**Google Sheets error?**
- Check service account email is shared with sheet
- Verify `google_credentials.json` exists

**Chrome not found?**
```bash
sudo apt-get install chromium-browser  # Linux
brew install chromium  # Mac
```

---

## ✨ Features

- ✅ Fully headless (no visible browser)
- ✅ Auto-sync with Google Sheets
- ✅ Real-time progress tracking
- ✅ Download results as CSV
- ✅ Scrapes up to 50 pages per job
- ✅ Multiple concurrent jobs

---

🎉 **Ready to scrape!**
