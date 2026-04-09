# Job Scrapper — Implementation Plan

## Goal

Build a **Python CLI tool** that scrapes job listings from multiple platforms (LinkedIn, Indeed, Naukri, Google Jobs, Glassdoor), resolves ambiguous job locations by cross-referencing company headquarters, deduplicates results, and exports clean data to CSV/JSON.

---

## Key Challenges & Decisions

### 1. Platform Coverage

| Platform | Method | Notes |
|---|---|---|
| LinkedIn | `python-jobspy` | Most restrictive; proxy recommended |
| Indeed | `python-jobspy` | `country_indeed='india'` for India |
| Naukri | `python-jobspy` | Natively supported |
| Google Jobs | `python-jobspy` | Uses `google_search_term` param |
| Glassdoor | `python-jobspy` | Uses `country_indeed` param |
| Internshala | **Custom scraper** | Not supported by JobSpy — we'll build a Playwright-based scraper |

### 2. Location Resolution Strategy

Many job listings say "India" or "Remote" instead of the actual office city. Our approach:

1. **Wikipedia/Wikidata lookup** — Query company name → extract HQ location from infobox
2. **Google Search fallback** — Search `"<Company Name> headquarters location"` and parse the knowledge panel
3. **Local cache** — Store resolved company→location mappings in a JSON file to avoid repeated lookups
4. **Manual override** — Allow users to provide a `company_locations.json` file with known mappings

### 3. Deduplication Strategy

Jobs are matched as duplicates if they share **2 or more** of:
- Same company name (fuzzy matched, normalized)
- Same job title (fuzzy matched using `rapidfuzz`)
- Same job URL / listing ID
- Posted within ±2 days of each other

---

## User Review Required

> [!IMPORTANT]
> **Proxy Configuration**: LinkedIn and Indeed aggressively block scrapers. For large-scale scraping (100+ results), you'll need to provide proxy URLs. The tool will support proxies via CLI flag or config file, but **you'll need to supply your own proxy list**.

> [!WARNING]
> **Internshala Scraper**: Building a custom Playwright scraper for Internshala adds complexity and is more fragile than the JobSpy-based scrapers. It may break if Internshala changes their HTML structure. Want me to include it, or skip Internshala for now?

> [!NOTE]
> **Rate Limiting**: To be respectful and avoid bans, the tool will add delays between requests. A full scrape across all platforms for one search term may take **2-5 minutes**.

---

## Proposed Changes

### Project Structure

```
d:\codes3\zapril\job-scapper\
├── main.py                    # CLI entry point (argparse)
├── config.py                  # Configuration & constants
├── requirements.txt           # Python dependencies
├── README.md                  # Usage documentation
│
├── scrapers/
│   ├── __init__.py
│   ├── jobspy_scraper.py      # Wrapper around python-jobspy (LinkedIn, Indeed, Naukri, Google, Glassdoor)
│   └── internshala_scraper.py # Custom Playwright scraper for Internshala
│
├── processors/
│   ├── __init__.py
│   ├── deduplicator.py        # Fuzzy deduplication logic
│   └── location_resolver.py   # Company HQ lookup (Wikipedia + Google)
│
├── exporters/
│   ├── __init__.py
│   └── exporter.py            # CSV / JSON export logic
│
├── cache/
│   └── company_locations.json # Cached company → location mappings
│
└── output/                    # Scrape results saved here
    └── .gitkeep
```

---

### [NEW] `requirements.txt`
Core dependencies:
```
python-jobspy>=1.1
pandas>=2.0
rapidfuzz>=3.0
requests>=2.31
beautifulsoup4>=4.12
playwright>=1.40
rich>=13.0          # Beautiful CLI output (tables, progress bars, spinners)
geopy>=2.4         # Nominatim geocoding for location validation
```

---

### [NEW] `config.py`
- Default configuration constants (timeouts, delays, max results)
- Platform-specific settings (country codes, search term templates)
- Color scheme for Rich CLI output

---

### [NEW] `main.py` — CLI Entry Point

The CLI interface using `argparse` with the following usage:

```bash
# Basic usage — scrape Software Engineer jobs in Mumbai
python main.py --search "Software Engineer" --location "Mumbai"

# Specify platforms
python main.py --search "Data Analyst" --location "Bangalore" --platforms linkedin indeed naukri

# With proxy support
python main.py --search "Python Developer" --location "Delhi" --proxy "http://user:pass@ip:port"

# Limit results and filter by recency
python main.py --search "Frontend Developer" --location "Pune" --max-results 50 --hours-old 72

# Export format
python main.py --search "DevOps" --location "Hyderabad" --format json

# Skip location resolution (faster)
python main.py --search "ML Engineer" --location "Chennai" --skip-location-check
```

**CLI Flags:**
| Flag | Description | Default |
|---|---|---|
| `--search` / `-s` | Job title / keywords (required) | — |
| `--location` / `-l` | Target city/location (required) | — |
| `--platforms` / `-p` | Platforms to scrape | all |
| `--max-results` / `-n` | Max results per platform | 25 |
| `--hours-old` | Only jobs posted within N hours | 168 (7 days) |
| `--format` / `-f` | Output format: `csv`, `json`, `both` | `csv` |
| `--proxy` | Proxy URL(s) for scraping | None |
| `--skip-location-check` | Skip company location cross-check | False |
| `--verbose` / `-v` | Verbose output level (0-2) | 1 |
| `--job-type` | Filter: fulltime, parttime, internship, contract | None |
| `--remote` | Filter for remote jobs only | False |

---

### [NEW] `scrapers/jobspy_scraper.py`
- Wraps `python-jobspy`'s `scrape_jobs()` function
- Handles each platform with correct parameters:
  - Indeed → sets `country_indeed='india'`
  - Google → constructs `google_search_term` dynamically
  - LinkedIn → enables `linkedin_fetch_description=True`
- Returns a normalized Pandas DataFrame with consistent columns
- Handles errors gracefully with Rich console warnings

---

### [NEW] `scrapers/internshala_scraper.py`
- Uses **Playwright** (headless Chromium) to scrape Internshala listings
- Navigates to internship/job search pages
- Extracts: title, company, location, stipend/salary, link, posted date
- Returns data in same DataFrame format as JobSpy scraper

---

### [NEW] `processors/location_resolver.py`
The core location intelligence module:

1. **`resolve_company_location(company_name)`**:
   - Check local cache first (`cache/company_locations.json`)
   - Query Wikipedia API for company page → parse infobox for "Headquarters"
   - Fallback: Google search `"<company> headquarters office <target_city>"`
   - Use `geopy` Nominatim to validate/standardize the resolved location

2. **`is_company_in_location(company_name, target_location)`**:
   - Resolves company HQ and checks if it matches the target city
   - Handles fuzzy matching (e.g., "Bombay" ↔ "Mumbai", "Bengaluru" ↔ "Bangalore")

3. **`enrich_jobs_with_location(df, target_location)`**:
   - For each job with vague location (e.g., "India", "Remote", blank):
     - Cross-reference company against resolved locations
     - Tag jobs as `location_confirmed`, `location_inferred`, or `location_unknown`

---

### [NEW] `processors/deduplicator.py`
- Normalize company names (lowercase, strip suffixes like "Pvt Ltd", "Inc")
- Normalize job titles (lowercase, strip common prefixes/suffixes)
- Use `rapidfuzz.fuzz.token_sort_ratio` with a threshold of 85% for fuzzy matching
- Deduplicate by composite key: `(normalized_company, normalized_title, location)`
- When duplicates found, keep the entry with the most complete data (description, salary, etc.)

---

### [NEW] `exporters/exporter.py`
- Export to CSV with proper column ordering
- Export to JSON with nested structure
- Auto-generate filename with timestamp: `jobs_mumbai_2026-04-09_18-30.csv`
- Summary statistics printed to console after export

---

### [NEW] `README.md`
- Installation instructions
- Usage examples
- Configuration guide
- Proxy setup guide

---

## CLI Output Preview

The tool will use `rich` for a beautiful terminal experience:

```
╔══════════════════════════════════════════════════════════════╗
║                    🔍 JOB SCRAPPER                         ║
╚══════════════════════════════════════════════════════════════╝

Search: "Software Engineer"  |  Location: Mumbai  |  Platforms: ALL

⏳ Scraping LinkedIn...           ████████████████████ 25/25 ✓
⏳ Scraping Indeed...              ████████████████████ 25/25 ✓
⏳ Scraping Naukri...              ████████████████████ 22/25 ✓
⏳ Scraping Google Jobs...         ████████████████████ 25/25 ✓
⏳ Scraping Glassdoor...           ████████████████████ 18/25 ✓
⏳ Scraping Internshala...         ████████████████████ 15/25 ✓

📊 Raw Results: 130 jobs collected

🔄 Deduplicating...                Removed 23 duplicates
🏢 Resolving company locations...  ████████████████████ 107/107

┌─────────────────────────────────────────────────────────────┐
│                    📋 RESULTS SUMMARY                       │
├─────────────────────────────────────────────────────────────┤
│  Total Unique Jobs:        107                              │
│  Location Confirmed:        72  (67%)                       │
│  Location Inferred:         28  (26%)                       │
│  Location Unknown:           7  (7%)                        │
│  Companies Found in Mumbai: 45                              │
├─────────────────────────────────────────────────────────────┤
│  Output: output/jobs_mumbai_2026-04-09_18-30.csv            │
└─────────────────────────────────────────────────────────────┘
```

---

## Open Questions

> [!IMPORTANT]
> 1. **Should I include the Internshala custom scraper?** It adds ~200 lines of code and is more fragile. We can always add it later.

> [!IMPORTANT]
> 2. **Do you want to provide proxy URLs**, or should the tool work without them (accepting that LinkedIn/Indeed may block after ~50 results)?

> [!NOTE]
> 3. **City alias mapping** — I plan to include common Indian city aliases (Mumbai/Bombay, Bangalore/Bengaluru, Chennai/Madras, Kolkata/Calcutta, etc.). Should I handle other countries too, or focus on India?

---

## Verification Plan

### Automated Tests
1. Run the scraper with `--search "Python Developer" --location "Mumbai" --max-results 5` on each individual platform
2. Verify CSV output contains expected columns
3. Test deduplication with known duplicate entries
4. Test location resolution with known companies (TCS → Mumbai, Infosys → Bangalore)

### Manual Verification
1. Spot-check 10 random job listings against actual platform pages
2. Verify location-inferred jobs have correct company HQ data
3. Confirm no duplicate entries in final output
