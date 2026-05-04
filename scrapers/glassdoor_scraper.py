"""
Glassdoor Scraper — Custom Playwright-based scraper for Glassdoor
since python-jobspy's Glassdoor module is blocked by anti-bot measures.

Uses a real headless browser to bypass Cloudflare / JavaScript challenges
and extracts structured data from Glassdoor's embedded __NEXT_DATA__ JSON.
"""

import json
import re
import time
import pandas as pd
from datetime import datetime, timedelta
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from config import REQUEST_DELAY_SECONDS

console = Console()

GLASSDOOR_BASE_URL = "https://www.glassdoor.co.in"
GLASSDOOR_SEARCH_URL = "https://www.glassdoor.co.in/Job/jobs.htm"


def scrape_glassdoor(
    search_term: str,
    location: str,
    max_results: int = 25,
    hours_old: int = 168,
    job_type: str | None = None,
) -> pd.DataFrame:
    """
    Scrape job listings from Glassdoor using Playwright.

    Args:
        search_term: Job title or keywords.
        location: Target city/location.
        max_results: Maximum results to fetch.
        hours_old: Only include jobs posted within N hours.
        job_type: Filter by job type (fulltime, parttime, internship, contract).

    Returns:
        A pandas DataFrame with normalized listings.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        console.print(
            "[bold red]✗[/] Playwright not installed. "
            "Run: [cyan]pip install playwright && playwright install chromium[/]"
        )
        return pd.DataFrame()

    all_listings = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Scraping Glassdoor...", total=None)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                )

                # Block heavy resources to speed up scraping
                page = context.new_page()
                page.route(
                    re.compile(r"\.(png|jpg|jpeg|gif|svg|webp|woff2?|ttf|eot)$"),
                    lambda route: route.abort(),
                )

                # ── Navigate to search page ──────────────────────
                search_query = search_term if search_term else "jobs"
                url = (
                    f"{GLASSDOOR_SEARCH_URL}"
                    f"?sc.keyword={_url_encode(search_query)}"
                    f"&locT=C&locKeyword={_url_encode(location)}"
                )

                progress.update(task, description="[cyan]Glassdoor: Loading search page...")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)

                # Wait for page content or Cloudflare challenge to resolve
                _wait_for_page_ready(page)

                progress.update(task, description="[cyan]Glassdoor: Extracting job data...")

                # ── Try extracting from __NEXT_DATA__ first ──────
                listings_from_json = _extract_from_next_data(page, location)

                if listings_from_json:
                    all_listings.extend(listings_from_json[:max_results])
                    progress.update(
                        task,
                        description=f"[cyan]Glassdoor: {len(all_listings)} jobs from JSON data",
                    )
                else:
                    # Fallback: parse DOM directly
                    progress.update(task, description="[cyan]Glassdoor: Parsing DOM...")
                    dom_listings = _extract_from_dom(page, location)
                    all_listings.extend(dom_listings[:max_results])

                # ── Pagination: click "Show more jobs" ───────────
                pages_loaded = 1
                max_pages = max(1, max_results // 30)  # ~30 jobs per page

                while len(all_listings) < max_results and pages_loaded < max_pages:
                    progress.update(
                        task,
                        description=f"[cyan]Glassdoor: Loading page {pages_loaded + 1}...",
                    )

                    if not _click_show_more(page):
                        break

                    time.sleep(REQUEST_DELAY_SECONDS + 1)

                    # Extract new listings
                    new_listings = _extract_from_next_data(page, location)
                    if not new_listings:
                        new_listings = _extract_from_dom(page, location)

                    if not new_listings:
                        break

                    # Only add listings we haven't seen yet
                    existing_urls = {l.get("job_url", "") for l in all_listings}
                    new_unique = [
                        l for l in new_listings if l.get("job_url", "") not in existing_urls
                    ]

                    if not new_unique:
                        break

                    all_listings.extend(new_unique)
                    pages_loaded += 1

                browser.close()

        except Exception as e:
            progress.update(
                task,
                description=f"[red]✗ Glassdoor error: {str(e)[:80]}",
            )
            console.print(f"[red]  Details: {str(e)}[/]")
            console.print(
                "[yellow]  Tip: Run [cyan]playwright install chromium[/cyan] "
                "if browser not found.[/]"
            )
            return pd.DataFrame()

        total = len(all_listings)
        progress.update(
            task,
            completed=total,
            total=total,
            description=f"[green]✓ Glassdoor: {total} listings scraped",
        )

    if not all_listings:
        console.print("[yellow]  ⚠ No Glassdoor results found (may be blocked by anti-bot).[/]")
        return pd.DataFrame()

    # Filter by hours_old if date_posted is available
    all_listings = _filter_by_age(all_listings, hours_old)

    df = pd.DataFrame(all_listings[:max_results])
    df["location_status"] = "unknown"
    df["resolved_location"] = ""

    console.print(f"[green]  → {len(df)} listings collected from Glassdoor[/]")
    return df


# ═════════════════════════════════════════════════════════════════════
# Data Extraction — __NEXT_DATA__ JSON
# ═════════════════════════════════════════════════════════════════════


def _extract_from_next_data(page, location: str) -> list[dict]:
    """Extract job listings from Glassdoor's embedded __NEXT_DATA__ JSON."""
    listings = []

    try:
        script_el = page.query_selector("script#__NEXT_DATA__")
        if not script_el:
            return []

        raw_json = script_el.inner_text()
        data = json.loads(raw_json)

        # Navigate the nested JSON to find job listings
        jobs = _find_jobs_in_json(data)

        for job in jobs:
            listing = _parse_json_job(job, location)
            if listing:
                listings.append(listing)

    except Exception as e:
        console.print(f"[yellow]  ⚠ Glassdoor JSON extraction error: {str(e)[:80]}[/]")

    return listings


def _find_jobs_in_json(data: dict) -> list[dict]:
    """
    Recursively search the __NEXT_DATA__ JSON for job listing arrays.
    Glassdoor nests jobs in various structures depending on the page state.
    """
    jobs = []

    # Common paths in Glassdoor's Next.js data
    try:
        # Path 1: props.pageProps.jobListings
        page_props = data.get("props", {}).get("pageProps", {})

        # Try jobListings directly
        if "jobListings" in page_props:
            job_listings = page_props["jobListings"]
            if isinstance(job_listings, dict):
                jobs = job_listings.get("jobListings", [])
                if not jobs:
                    jobs = job_listings.get("jobs", [])
            elif isinstance(job_listings, list):
                jobs = job_listings

        # Path 2: props.pageProps.initialState
        if not jobs and "initialState" in page_props:
            initial_state = page_props["initialState"]
            if isinstance(initial_state, dict):
                jobs = _deep_find_key(initial_state, "jobListings") or []

        # Path 3: search through dehydratedState (React Query)
        if not jobs:
            dehydrated = data.get("props", {}).get("pageProps", {}).get("dehydratedState", {})
            if dehydrated:
                queries = dehydrated.get("queries", [])
                for query in queries:
                    state_data = query.get("state", {}).get("data", {})
                    if isinstance(state_data, dict):
                        found = _deep_find_key(state_data, "jobListings")
                        if found:
                            jobs = found
                            break
                        found = _deep_find_key(state_data, "jobs")
                        if found:
                            jobs = found
                            break

        # Path 4: brute-force search for any array with job-like objects
        if not jobs:
            jobs = _deep_find_job_array(data)

    except Exception:
        pass

    return jobs


def _deep_find_key(data, target_key: str):
    """Recursively find the first value for a given key in nested dicts/lists."""
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for v in data.values():
            result = _deep_find_key(v, target_key)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _deep_find_key(item, target_key)
            if result:
                return result
    return None


def _deep_find_job_array(data, depth=0) -> list[dict]:
    """
    Recursively look for an array of objects that look like job listings
    (have keys like 'jobTitle', 'companyName', etc.).
    """
    if depth > 8:
        return []

    if isinstance(data, list) and len(data) > 0:
        # Check if items look like jobs
        sample = data[0] if isinstance(data[0], dict) else None
        if sample:
            job_keys = {"jobTitle", "header", "companyName", "employer", "locationName", "jobLink"}
            if len(job_keys & set(sample.keys())) >= 2:
                return data
            # Check nested: sometimes each item has a "jobview" or "job" sub-key
            for nested_key in ("jobview", "job", "listing", "node"):
                if nested_key in sample and isinstance(sample[nested_key], dict):
                    inner_keys = set(sample[nested_key].keys())
                    if len(job_keys & inner_keys) >= 2:
                        return [item.get(nested_key, item) for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        for v in data.values():
            result = _deep_find_job_array(v, depth + 1)
            if result:
                return result
    elif isinstance(data, list):
        for item in data[:20]:  # Limit to avoid massive lists
            result = _deep_find_job_array(item, depth + 1)
            if result:
                return result

    return []


def _parse_json_job(job: dict, location: str) -> dict | None:
    """Parse a single job object from Glassdoor's JSON data into our standard format."""
    try:
        # Handle nested structures — Glassdoor wraps jobs differently
        if "jobview" in job:
            job = job["jobview"]
        if "job" in job and isinstance(job["job"], dict):
            inner = job["job"]
            job = {**job, **inner}
        if "header" in job and isinstance(job["header"], dict):
            header = job["header"]
            job = {**job, **header}

        title = (
            job.get("jobTitle")
            or job.get("title")
            or job.get("jobTitleText")
            or ""
        )

        company = (
            job.get("companyName")
            or job.get("employerName")
            or ""
        )
        # Sometimes company is nested in an employer object
        if not company and "employer" in job:
            emp = job["employer"]
            if isinstance(emp, dict):
                company = emp.get("name", "") or emp.get("shortName", "")

        job_location = (
            job.get("locationName")
            or job.get("location")
            or job.get("locName")
            or location
        )

        # Salary
        salary = _extract_salary_from_json(job)

        # URL
        job_url = ""
        listing_id = job.get("listingId") or job.get("jobListingId") or job.get("id")
        if listing_id:
            job_url = f"{GLASSDOOR_BASE_URL}/job-listing/j?jl={listing_id}"

        link = job.get("jobLink") or job.get("seoJobLink") or job.get("jobUrl") or ""
        if link and not job_url:
            job_url = link if link.startswith("http") else f"{GLASSDOOR_BASE_URL}{link}"

        # Date posted
        date_posted = job.get("datePosted") or job.get("discoverDate") or ""
        if isinstance(date_posted, (int, float)):
            # Unix timestamp in milliseconds
            try:
                date_posted = datetime.fromtimestamp(date_posted / 1000).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                date_posted = ""

        # Job type
        job_type_val = job.get("jobType") or job.get("employmentType") or ""

        if not title and not company:
            return None

        return {
            "source": "glassdoor",
            "title": str(title).strip() or "N/A",
            "company": str(company).strip() or "N/A",
            "location": str(job_location).strip(),
            "salary": salary,
            "job_type": str(job_type_val).strip().lower() if job_type_val else "",
            "date_posted": str(date_posted).strip(),
            "job_url": job_url,
            "description": str(job.get("description") or job.get("jobDescription") or "")[:500],
        }

    except Exception:
        return None


def _extract_salary_from_json(job: dict) -> str:
    """Extract and format salary from various JSON structures."""
    try:
        # Direct salary fields
        salary_text = job.get("salarySource") or job.get("salary") or ""
        if salary_text and isinstance(salary_text, str):
            return salary_text

        # Structured pay info
        pay = job.get("payPercentile90") or job.get("payCurrency")
        if pay:
            min_pay = job.get("payPercentile10") or job.get("payPeriodAdjustedPay", {}).get("p10")
            max_pay = job.get("payPercentile90") or job.get("payPeriodAdjustedPay", {}).get("p90")
            if min_pay and max_pay:
                return f"₹{int(min_pay):,} - ₹{int(max_pay):,}"

        # Nested compensation
        comp = job.get("compensation") or job.get("salaryEstimate") or {}
        if isinstance(comp, dict):
            min_val = comp.get("min") or comp.get("payPercentile10")
            max_val = comp.get("max") or comp.get("payPercentile90")
            if min_val and max_val:
                return f"₹{int(min_val):,} - ₹{int(max_val):,}"

    except (ValueError, TypeError):
        pass

    return ""


# ═════════════════════════════════════════════════════════════════════
# Data Extraction — DOM Fallback
# ═════════════════════════════════════════════════════════════════════


def _extract_from_dom(page, location: str) -> list[dict]:
    """Fallback: extract job data by parsing the DOM directly."""
    listings = []

    try:
        # Wait for job cards to appear
        page.wait_for_selector(
            "[class*='JobCard'], [class*='jobCard'], [class*='JobsList_jobListItem']",
            timeout=10000,
        )
    except Exception:
        # No job cards found in DOM
        return []

    try:
        # Try multiple container selectors
        cards = page.query_selector_all("li[class*='JobsList_jobListItem']")
        if not cards:
            cards = page.query_selector_all("[class*='JobCard']")
        if not cards:
            cards = page.query_selector_all("[data-test='jobListing']")

        for card in cards:
            listing = _extract_dom_listing(card, location)
            if listing:
                listings.append(listing)

    except Exception as e:
        console.print(f"[yellow]  ⚠ Glassdoor DOM extraction error: {str(e)[:80]}[/]")

    return listings


def _extract_dom_listing(card, location: str) -> dict | None:
    """Extract data from a single DOM job card element."""
    try:
        title = _safe_dom_text(card, [
            "[class*='JobCard_jobTitle']",
            "[class*='jobTitle']",
            "a[class*='jobLink']",
            "h2 a",
        ])

        company = _safe_dom_text(card, [
            "[class*='EmployerProfile']",
            "[class*='employerName']",
            "[class*='companyName']",
            "[data-test='emp-name']",
        ])

        job_location = _safe_dom_text(card, [
            "[class*='JobCard_location']",
            "[class*='location']",
            "[data-test='emp-location']",
        ])

        salary = _safe_dom_text(card, [
            "[class*='JobCard_salaryEstimate']",
            "[class*='salary']",
            "[class*='compensation']",
        ])

        # Get job URL
        link_el = (
            card.query_selector("a[class*='JobCard_jobTitle']")
            or card.query_selector("a[class*='jobLink']")
            or card.query_selector("a[href*='/job-listing/']")
            or card.query_selector("a[href]")
        )
        job_url = ""
        if link_el:
            href = link_el.get_attribute("href") or ""
            if href:
                job_url = href if href.startswith("http") else f"{GLASSDOOR_BASE_URL}{href}"

        if not title and not company:
            return None

        return {
            "source": "glassdoor",
            "title": title or "N/A",
            "company": company or "N/A",
            "location": job_location or location,
            "salary": salary or "",
            "job_type": "",
            "date_posted": "",
            "job_url": job_url,
            "description": "",
        }

    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════


def _wait_for_page_ready(page, timeout_seconds: int = 20):
    """
    Wait for the Glassdoor page to become ready.
    Handles Cloudflare challenge delays.
    """
    start = time.time()

    while time.time() - start < timeout_seconds:
        # Check if we're still on a Cloudflare challenge page
        title = page.title().lower()
        if "just a moment" in title or "checking" in title:
            time.sleep(2)
            continue

        # Check for actual job content
        has_jobs = page.query_selector(
            "[class*='JobCard'], [class*='JobsList'], script#__NEXT_DATA__"
        )
        if has_jobs:
            time.sleep(1)  # Small extra wait for full render
            return

        time.sleep(1)

    # Final wait as buffer
    time.sleep(2)


def _click_show_more(page) -> bool:
    """Click the 'Show more jobs' button for pagination. Returns True if clicked."""
    try:
        selectors = [
            "button[class*='JobsList_button']",
            "button[data-test='load-more']",
            "button:has-text('Show more jobs')",
            "button:has-text('Load more')",
        ]

        for selector in selectors:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(2)
                return True

    except Exception:
        pass

    return False


def _filter_by_age(listings: list[dict], hours_old: int) -> list[dict]:
    """Filter listings to only include those posted within hours_old hours."""
    if not hours_old or hours_old <= 0:
        return listings

    cutoff = datetime.now() - timedelta(hours=hours_old)
    filtered = []

    for listing in listings:
        date_str = listing.get("date_posted", "")
        if not date_str:
            # If no date, keep the listing (benefit of doubt)
            filtered.append(listing)
            continue

        try:
            posted = datetime.strptime(date_str, "%Y-%m-%d")
            if posted >= cutoff:
                filtered.append(listing)
        except (ValueError, TypeError):
            # Can't parse date, keep the listing
            filtered.append(listing)

    return filtered


def _safe_dom_text(element, selectors: list[str]) -> str:
    """Try multiple CSS selectors and return the first non-empty text found."""
    for selector in selectors:
        try:
            el = element.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def _url_encode(text: str) -> str:
    """Simple URL encoding for query parameters."""
    import urllib.parse
    return urllib.parse.quote_plus(text)
