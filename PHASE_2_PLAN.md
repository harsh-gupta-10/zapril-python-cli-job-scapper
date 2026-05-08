# Zapril Job Scraper — Phase 2: Autonomous Local Pipeline & Live Dashboard

This document outlines the transition from a manual CLI scraper to an autonomous, locally-hosted data pipeline with a cloud-backed public dashboard.

## 🏗️ Architecture Overview

1.  **Local Scraper Orchestrator**: A Flask API (`app.py`) running on your local machine.
2.  **Sequential Runner**: `schedule_runner.py` iterates through every city and job title combination, handling rate limits and resumable states.
3.  **Cloud Database**: Supabase PostgreSQL handles data storage and deduplication via `job_url` unique constraints.
4.  **Admin Dashboard**: A React-based UI (served locally) to control, configure, and monitor the scraper.
5.  **Live Job Board**: A separate public-facing site (`live-site/`) deployed to **Vercel**, fetching data directly from Supabase.

---

## 🛠️ Current Status & Progress

### ✅ Completed
- [x] **Supabase Setup**: `jobs` table created with `job_url` UNIQUE constraint and RLS enabled.
- [x] **Sequential Logic**: `schedule_runner.py` implemented with randomized delays and progress tracking.
- [x] **Supabase Integration**: `exporters/sql_exporter.py` configured for direct PostgreSQL upserts.
- [x] **Admin UI**: Robust React dashboard built for monitoring and control.
- [x] **Flask Backend**: API endpoints created for all scraper and database operations.
- [x] **Live Site Foundation**: `live-site/` ready with Supabase client and modern UI.

### ⏳ Next Steps
- [x] **Initial Batch Run**: Pipeline running (4 cities × 4 job titles = 16 combinations). 181+ jobs already in DB.
- [ ] **Vercel Deployment**: Deploy the `live-site/` folder to Vercel.
- [ ] **Domain Connection**: Connect your custom domain (optional).

---

## 🚀 How to Run the Local Pipeline

### 1. Start the Admin Dashboard
Run the following command in your terminal:
```bash
python app.py
```
Open your browser to: **http://localhost:8080**
*Password:* `Zapril#Secure&Job!2024` (Configurable in `.env`)

### 2. Configure Your Targets
- Go to the **Configuration** tab.
- Add or toggle the cities you want to target.
- Add or toggle the job roles (e.g., "Software Engineer", "AI Developer").
- Adjust the **Max Results** per platform to control scrape depth.

### 3. Launch the Scraper
- Go to the **Scraper Actions** tab.
- Click **"Start Fresh Pipeline"** to begin a full run.
- Monitor the **Terminal Logs** section to see real-time output.
- The scraper will automatically move from one combination to the next (e.g., *Software Engineer in Mumbai* -> *Software Engineer in Bangalore*).

---

## 🌐 Deploying the Live Job Board (Vercel)

1.  **Open Vercel Dashboard** and create a new project.
2.  **Root Directory**: Set this to `live-site/`.
3.  **Environment Variables**: Add the following from your `.env`:
    - `VITE_SUPABASE_URL`
    - `VITE_SUPABASE_ANON_KEY`
4.  **Deploy**. Your job board will be live at `https://your-project.vercel.app`.

---

## 📋 Database Schema (Reference)
```sql
CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    date_posted TEXT,
    source TEXT,
    job_url TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS Policies enabled for Public Read and Authenticated Full Access.
```

---

## ✅ Success Criteria
1.  The scraper completes the entire city/role list without manual intervention.
2.  Supabase reflects the latest jobs without duplicates.
3.  The Vercel site displays the jobs beautifully in the bento-grid layout.
