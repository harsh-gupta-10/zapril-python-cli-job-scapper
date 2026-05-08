# Zapril Job Scraper - Updated Architecture Plan

## 1. Project Objective & Architecture

**Goal**: Establish a robust, self-contained automated scraping system with a local backend/UI for management and a live public site hosted on Vercel. 
The system explicitly avoids Cloud Run and Cloud SQL to simplify the stack, mitigate costs, and ensure easy local maintenance. Data is pushed directly to a remote Supabase PostgreSQL database.

*   **Local Scraper & API Backend**:
    *   A local Flask server (`app.py`) orchestrates the scraping pipeline.
    *   Maintains a list of target cities and job titles locally (or fetches from backend config).
    *   Executes scraping sequentially or in phases using Selenium/Playwright across platforms like LinkedIn, Indeed, and Naukri.
    *   Processes the jobs locally and updates the remote Supabase database directly using `exporters/sql_exporter.py` or direct API calls.
*   **Admin Dashboard (Local UI)**:
    *   A local React application running alongside the Flask backend.
    *   Provides a graphical interface to configure the scraper (target cities, roles, intervals), trigger the pipeline manually, and monitor live progress and system logs.
*   **Live Site (Vercel)**:
    *   A public-facing React frontend deployed to Vercel.
    *   Fetches the aggregated job data directly from the Supabase database using the Supabase JS client.
    *   Features search, filtering, pagination, and fresh timestamp formatting to explore thousands of live job listings.

## 2. Infrastructure Setup
*   **Database**: Supabase PostgreSQL is the central source of truth, handling unique constraints (job URLs) and deduplication.
*   **Hosting (Public)**: The public job board is hosted on Vercel. Environment variables (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) must be correctly bound in the Vercel project settings.
*   **Hosting (Admin/Backend)**: Admin operations remain exclusively on the local machine (or a dedicated internal VPS) to maintain security and control over the resource-intensive web scraping processes.

## 3. Addressed Issues & Improvements
*   **Scraper UI Stability**: Fixed a crash in the Admin Dashboard's "Scraper Actions" tab caused by unhandled empty states when fetching the pipeline status.
*   **Date Formatting**: Updated the display logic across both the Admin Dashboard and Live Site to show "Today" for jobs published within the last 24 hours, replacing vague terms like "Recently".
*   **Live Site Pagination**: Validated and ensured the Live Site correctly paginates and reports the exact total number of jobs found in the Supabase database.

## 4. Final Deployment Steps
1. Push the updated `live-site/` code to the connected GitHub repository (or deploy via Vercel CLI).
2. Configure the custom domain in Vercel.
3. Validate that the local scraper can continuously feed new data into Supabase, and that the Live Site automatically reflects these updates.
