# 🚀 Zapril Job Scrapper: Approved Feature Roadmap

This document outlines the high-priority features and architectural improvements we are focusing on for the **Zapril Job Scrapper**.

---

## 🛡️ 1. Terminal Scrapper Control (Graceful Stop)
Currently, stopping the scraper via `Ctrl+C` or closing the terminal can lead to interrupted database writes or lost session data.

- **Double-Confirmation Prompt**: When an interrupt signal is received, the CLI should pause and ask: `⚠️ Scraping in progress. Are you sure you want to stop? (y/n)`.
- **Checkpointing**: If confirmed, the scraper completes the *current* platform's export before shutting down, ensuring no data from the last 10-15 minutes is lost.
- **Remote Kill Switch**: An API endpoint `/api/scraper/stop` that allows the Admin Dashboard to safely terminate the background `subprocess` by sending a signal that the Python script catches and handles gracefully.

## 🔄 2. Intelligent Scrape Resumption
While basic state is saved in `scraper_state.json`, we can make this more robust.

- **Partial Progress Recovery**: If a scrape fails midway through "LinkedIn" but finished "Indeed", the resume feature should skip the completed platforms for that specific job/city combination.
- **Failover Logic**: If a proxy is banned, automatically switch to a fallback proxy or pause that specific platform for 1 hour while continuing others.

## 📊 3. Advanced Salary Intelligence
Move beyond just listing jobs; provide market insights.

- **Salary Aggregator**: Scrape and normalize salary ranges (e.g., converting "₹12L - ₹18L" to a standard annual numeric range).
- **Market Heatmaps**: Visual reports in the Admin Dashboard showing which cities or job titles have the highest paying listings this month.
- **Platform Discrepancy**: Alert users if Indeed lists a salary higher/lower than LinkedIn for the exact same role.

## 🏠 4. Enhanced Company Intelligence
Expand the `LocationResolver` logic.

- **Deep Company Profiles**: Automatically fetch company size, funding stage (via Crunchbase), and Glassdoor ratings during the enrichment phase.
- **Employee "Who Do I Know?"**: (Advanced) Check LinkedIn connections (if authenticated) to see if the user has any 1st or 2nd-degree connections at the hiring company.

## ✨ 5. Description Improver & Skill Lister
Use AI to analyze and enhance the unstructured job descriptions scraped from various platforms.

- **Skill Extraction**: Automatically parse the raw job description to extract a clean, bulleted list of required technical and soft skills (e.g., `["React", "Node.js", "System Design"]`).
- **Description Formatting**: Clean up messy, poorly formatted job descriptions (often caused by raw HTML extraction) into a standardized, easy-to-read markdown format.
- **Key Takeaways**: Generate a 3-bullet summary of the role (e.g., "Hybrid role in Mumbai", "Requires 3+ years experience", "Focuses on scalable architecture") so users don't have to read the entire text.

---

### Implementation Strategy
We will implement these sequentially, starting with the **Terminal Scrapper Control** to ensure the foundation is stable and safe to pause/stop before adding more complex processing like the **Description Improver**.
