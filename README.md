# 🔍 Job Scrapper

A powerful Python CLI tool that scrapes job listings from **6 major platforms**, cross-references company locations to resolve ambiguous listings, and deduplicates results intelligently.

## ✨ Features

- **Multi-Platform Scraping** — LinkedIn, Indeed, Naukri, Google Jobs, Glassdoor, and Internshala
- **Smart Location Resolution** — Cross-references company HQ via Wikipedia, Wikidata, and Google to identify jobs in your target city even when the listing says "India" or "Remote"
- **Fuzzy Deduplication** — Removes duplicate listings across platforms using intelligent fuzzy matching
- **Beautiful CLI** — Rich terminal output with progress bars, summary tables, and color-coded results
- **Flexible Export** — CSV, JSON, or both, with auto-generated filenames
- **Company Directory** — Generates a list of companies with offices in your target location

## 📦 Installation

```bash
# Clone or navigate to the project
cd job-scapper

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (needed for Internshala)
playwright install chromium
```

## 🚀 Usage

### Basic Search
```bash
python main.py --search "Software Engineer" --location "Mumbai"
```

### Specify Platforms
```bash
python main.py -s "Data Analyst" -l "Bangalore" -p linkedin indeed naukri
```

### Limit Results & Filter by Recency
```bash
python main.py -s "Python Developer" -l "Delhi" --max-results 50 --hours-old 72
```

### Export as JSON
```bash
python main.py -s "Frontend Developer" -l "Pune" --format json
```

### Export Both CSV and JSON
```bash
python main.py -s "DevOps Engineer" -l "Hyderabad" --format both
```

### Use Proxies (for large scrapes)
```bash
python main.py -s "Backend Dev" -l "Mumbai" --proxy "http://user:pass@ip:port"
```

### Skip Location Check (faster)
```bash
python main.py -s "ML Engineer" -l "Chennai" --skip-location-check
```

### Filter by Job Type
```bash
python main.py -s "Intern" -l "Mumbai" --job-type internship
```

### Remote Jobs Only
```bash
python main.py -s "React Developer" -l "India" --remote
```

### Skip Internshala (faster, no Playwright needed)
```bash
python main.py -s "Java Developer" -l "Pune" --no-internshala
```

## 📋 CLI Flags

| Flag | Short | Description | Default |
|---|---|---|---|
| `--search` | `-s` | Job title or keywords (required) | — |
| `--location` | `-l` | Target city/location (required) | — |
| `--platforms` | `-p` | Platforms to scrape | all |
| `--max-results` | `-n` | Max results per platform | 25 |
| `--hours-old` | | Only jobs within N hours | 168 (7d) |
| `--format` | `-f` | Output: csv, json, both | csv |
| `--proxy` | | Proxy URL(s) | None |
| `--skip-location-check` | | Skip HQ lookup | False |
| `--verbose` | `-v` | 0=errors, 1=warn, 2=all | 1 |
| `--job-type` | | fulltime/parttime/internship/contract | None |
| `--remote` | | Remote jobs only | False |
| `--no-internshala` | | Skip Internshala | False |

## 📁 Output

Results are saved in the `output/` directory:
- `jobs_<search>_<location>_<timestamp>.csv` — Job listings
- `jobs_<search>_<location>_<timestamp>.json` — Job listings (JSON format)
- `companies_in_<location>_<timestamp>.txt` — Companies with offices in your city

## 🏢 Location Resolution

The tool resolves ambiguous locations through a 3-tier strategy:

1. **Wikipedia** — Looks up the company's Wikipedia page for HQ info
2. **Wikidata SPARQL** — Queries Wikidata's structured database
3. **Google Search** — Searches Google for company headquarters

Results are cached in `cache/company_locations.json` to avoid repeated lookups.

### Indian City Aliases

The tool automatically maps local area names and aliases:
- Bombay → Mumbai, Navi Mumbai → Mumbai, Powai → Mumbai
- Bengaluru → Bangalore, Whitefield → Bangalore
- Gurugram/Gurgaon/Noida → Delhi NCR
- Madras → Chennai
- Calcutta → Kolkata

## ⚠️ Important Notes

- **Rate Limiting**: Job platforms may block rapid requests. Use `--proxy` for large scrapes.
- **LinkedIn**: Most restrictive platform. Proxies recommended for 50+ results.
- **Internshala**: Uses Playwright (browser automation) and is slower than other platforms.
- **Ethical Usage**: This tool is for personal/educational use. Respect each platform's ToS.

## 📄 License

MIT
