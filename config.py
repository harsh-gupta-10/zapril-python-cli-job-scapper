"""
Configuration constants for the Job Scrapper.
"""

# ─── Platform Settings ────────────────────────────────────────────────
# Platforms handled by python-jobspy (HTTP-based, fast)
JOBSPY_PLATFORMS = ["linkedin", "indeed"]
# Platforms with custom Playwright scrapers (browser-based, reliable)
NAUKRI_ENABLED = True
GOOGLE_JOBS_ENABLED = True
GLASSDOOR_ENABLED = True
INTERNSHALA_ENABLED = True

# All supported platforms for display / CLI help
SUPPORTED_PLATFORMS = JOBSPY_PLATFORMS.copy()  # JobSpy handles these

# python-jobspy site_name values
JOBSPY_SITE_MAP = {
    "linkedin": "linkedin",
    "indeed": "indeed",
}

# ─── Scraping Defaults ────────────────────────────────────────────────
DEFAULT_MAX_RESULTS = 25
DEFAULT_HOURS_OLD = 168  # 7 days
DEFAULT_COUNTRY_INDEED = "india"
DEFAULT_VERBOSE = 1
REQUEST_DELAY_SECONDS = 2  # Delay between requests to be respectful

# ─── Deduplication Settings ───────────────────────────────────────────
FUZZY_MATCH_THRESHOLD = 85  # rapidfuzz score threshold (0-100)
COMPANY_SUFFIXES_TO_STRIP = [
    "pvt ltd", "pvt. ltd.", "private limited", "limited", "ltd", "ltd.",
    "inc", "inc.", "incorporated", "corp", "corp.", "corporation",
    "llc", "llp", "co.", "company", "technologies", "technology",
    "tech", "solutions", "services", "consulting", "consultancy",
    "india", "global", "systems", "infotech", "softech", "software",
]

# ─── Location Resolution ─────────────────────────────────────────────
WIKIPEDIA_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Vague location strings that trigger company HQ lookup
VAGUE_LOCATIONS = [
    "india", "remote", "anywhere", "pan india", "multiple locations",
    "work from home", "wfh", "hybrid", "flexible", "", "n/a", "na",
    "not specified", "various locations", "multiple cities",
]

# Indian city aliases → canonical name
CITY_ALIASES = {
    # Mumbai
    "bombay": "mumbai",
    "navi mumbai": "mumbai",
    "new mumbai": "mumbai",
    "thane": "mumbai",
    "andheri": "mumbai",
    "bandra": "mumbai",
    "lower parel": "mumbai",
    "powai": "mumbai",
    "goregaon": "mumbai",
    "malad": "mumbai",
    "worli": "mumbai",
    "bkc": "mumbai",
    # Bangalore
    "bengaluru": "bangalore",
    "bengalore": "bangalore",
    "whitefield": "bangalore",
    "electronic city": "bangalore",
    "koramangala": "bangalore",
    "hsr layout": "bangalore",
    "marathahalli": "bangalore",
    "indiranagar": "bangalore",
    # Delhi / NCR
    "new delhi": "delhi",
    "delhi ncr": "delhi",
    "ncr": "delhi",
    "noida": "delhi",
    "greater noida": "delhi",
    "gurgaon": "delhi",
    "gurugram": "delhi",
    "faridabad": "delhi",
    "ghaziabad": "delhi",
    # Chennai
    "madras": "chennai",
    "sholinganallur": "chennai",
    "omr": "chennai",
    "tambaram": "chennai",
    # Kolkata
    "calcutta": "kolkata",
    "salt lake": "kolkata",
    "rajarhat": "kolkata",
    "new town": "kolkata",
    # Hyderabad
    "secunderabad": "hyderabad",
    "hitec city": "hyderabad",
    "hitech city": "hyderabad",
    "gachibowli": "hyderabad",
    "madhapur": "hyderabad",
    "kondapur": "hyderabad",
    # Pune
    "pimpri": "pune",
    "chinchwad": "pune",
    "pimpri-chinchwad": "pune",
    "hinjewadi": "pune",
    "kharadi": "pune",
    "magarpatta": "pune",
    "hadapsar": "pune",
    # Others
    "ahmedabad": "ahmedabad",
    "amdavad": "ahmedabad",
    "trivandrum": "thiruvananthapuram",
    "cochin": "kochi",
    "ernakulam": "kochi",
    "vizag": "visakhapatnam",
    "pondicherry": "puducherry",
}

# ─── Output Settings ─────────────────────────────────────────────────
OUTPUT_DIR = "output"
CACHE_DIR = "cache"
COMPANY_CACHE_FILE = "cache/company_locations.json"

# Standard output columns and their display order
OUTPUT_COLUMNS = [
    "source",
    "title",
    "company",
    "location",
    "location_status",  # confirmed / inferred / unknown
    "resolved_location",
    "job_type",
    "salary",
    "date_posted",
    "job_url",
    "description",
]

# ─── Rich Console Theme ──────────────────────────────────────────────
THEME_COLORS = {
    "primary": "bold cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "info": "bold blue",
    "muted": "dim white",
    "highlight": "bold magenta",
}
