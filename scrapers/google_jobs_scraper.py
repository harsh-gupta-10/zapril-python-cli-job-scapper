"""
Google Jobs Scraper — Uses curl_cffi with Chrome TLS impersonation
to access Google's job search results.

Tries to extract structured data from Google's HTML response.
Falls back gracefully when blocked by anti-bot measures.
"""

import re
import json
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

console = Console()

GOOGLE_SEARCH_URL = "https://www.google.com/search"


def scrape_google_jobs(
    search_term: str,
    location: str,
    max_results: int = 25,
    hours_old: int = 168,
    job_type: str | None = None,
) -> pd.DataFrame:
    """
    Scrape job listings from Google Jobs.

    Uses curl_cffi with TLS fingerprint impersonation to access
    Google's Jobs vertical (udm=8). Falls back to Playwright if available.
    """
    all_listings = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Scraping Google Jobs...", total=None)

        # ── Strategy 1: Try Playwright with stealth ──────
        progress.update(task, description="[cyan]Google Jobs: Launching browser...")
        playwright_results = _try_playwright_stealth(search_term, location, max_results, job_type)

        if playwright_results:
            all_listings.extend(playwright_results)
            progress.update(
                task,
                description=f"[cyan]Google Jobs: {len(all_listings)} jobs from browser",
            )
        else:
            # ── Strategy 2: Try curl_cffi ────────────────
            progress.update(task, description="[cyan]Google Jobs: Trying HTTP fallback...")
            http_results = _try_curl_cffi(search_term, location, max_results, job_type)

            if http_results:
                all_listings.extend(http_results)
            else:
                progress.update(
                    task,
                    completed=0,
                    total=0,
                    description="[yellow]⚠ Google Jobs: blocked by anti-bot (CAPTCHA)",
                )

        total = min(len(all_listings), max_results)
        if total > 0:
            progress.update(
                task,
                completed=total,
                total=total,
                description=f"[green]✓ Google Jobs: {total} listings scraped",
            )

    if not all_listings:
        console.print(
            "[yellow]  ⚠ Google Jobs blocked by CAPTCHA — scraping unavailable.[/]\n"
            "[yellow]    Tip: Use [cyan]--no-google[/cyan] to skip, or try with a proxy: "
            "[cyan]--proxy http://your:proxy@ip:port[/][/]"
        )
        return pd.DataFrame()

    # Filter by age
    all_listings = _filter_by_age(all_listings, hours_old)

    df = pd.DataFrame(all_listings[:max_results])
    df["location_status"] = "unknown"
    df["resolved_location"] = ""

    console.print(f"[green]  → {len(df)} listings collected from Google Jobs[/]")
    return df


def _try_playwright_stealth(
    search_term: str, location: str, max_results: int, job_type: str | None
) -> list[dict]:
    """Try scraping Google Jobs with Playwright + stealth plugin."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    # Try to use stealth
    stealth_cls = None
    try:
        from playwright_stealth import Stealth
        stealth_cls = Stealth()
    except ImportError:
        pass

    listings = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            page = ctx.new_page()

            # Apply stealth if available
            if stealth_cls:
                stealth_cls.apply_stealth_sync(page)

            # Build query
            query = _build_search_query(search_term, location, job_type)
            url = f"{GOOGLE_SEARCH_URL}?q={_url_encode(query)}&udm=8"

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)

            # Check for CAPTCHA/sorry page
            if "/sorry/" in page.url or "unusual traffic" in page.content()[:1000].lower():
                browser.close()
                return []

            # Wait for job cards
            try:
                page.wait_for_selector("a.MQUd2b, li.iFjolb", timeout=10000)
            except Exception:
                browser.close()
                return []

            time.sleep(2)

            # Extract job cards
            cards = page.query_selector_all("a.MQUd2b")
            if not cards:
                cards = page.query_selector_all("li.iFjolb")

            for card in cards[:max_results]:
                listing = _extract_card_from_element(card, location)
                if listing:
                    listings.append(listing)

            browser.close()

    except Exception:
        pass

    return listings


def _try_curl_cffi(
    search_term: str, location: str, max_results: int, job_type: str | None
) -> list[dict]:
    """Try scraping Google Jobs with curl_cffi HTTP requests."""
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        return []

    listings = []

    try:
        query = _build_search_query(search_term, location, job_type)
        url = f"{GOOGLE_SEARCH_URL}?q={_url_encode(query)}&udm=8"

        resp = cffi_requests.get(url, impersonate="chrome124", timeout=15)

        if resp.status_code != 200:
            return []

        html = resp.text

        # Check for blocking
        if "/sorry/" in html or "unusual traffic" in html.lower():
            return []

        # Try to extract from JSON-LD or embedded data
        listings = _extract_from_html(html, location)

    except Exception:
        pass

    return listings


def _extract_from_html(html: str, location: str) -> list[dict]:
    """Extract job listings from Google's HTML response."""
    listings = []

    # Try JSON-LD
    json_ld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    for match in re.finditer(json_ld_pattern, html, re.DOTALL):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                listings.append(_parse_json_ld_job(data, location))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        listings.append(_parse_json_ld_job(item, location))
        except (json.JSONDecodeError, KeyError):
            continue

    if listings:
        return [l for l in listings if l is not None]

    # Try parsing from regular search result divs
    # Google's HTML includes job titles in <div> elements with specific classes
    title_pattern = r'<div[^>]*class="[^"]*BjJfJf[^"]*"[^>]*>([^<]+)</div>'
    company_pattern = r'<div[^>]*class="[^"]*vNEEBe[^"]*"[^>]*>([^<]+)</div>'

    titles = re.findall(title_pattern, html)
    companies = re.findall(company_pattern, html)

    for i, title in enumerate(titles):
        company = companies[i] if i < len(companies) else "N/A"
        listings.append({
            "source": "google",
            "title": _clean_html(title),
            "company": _clean_html(company),
            "location": location,
            "salary": "",
            "job_type": "",
            "date_posted": "",
            "job_url": "",
            "description": "",
        })

    return [l for l in listings if l is not None]


def _parse_json_ld_job(data: dict, location: str) -> dict | None:
    """Parse a JobPosting JSON-LD object."""
    try:
        title = data.get("title", "")
        company = ""
        hiring_org = data.get("hiringOrganization", {})
        if isinstance(hiring_org, dict):
            company = hiring_org.get("name", "")

        job_location = location
        loc_data = data.get("jobLocation", {})
        if isinstance(loc_data, dict):
            address = loc_data.get("address", {})
            if isinstance(address, dict):
                city = address.get("addressLocality", "")
                region = address.get("addressRegion", "")
                job_location = f"{city}, {region}".strip(", ") or location

        date_posted = data.get("datePosted", "")

        return {
            "source": "google",
            "title": title or "N/A",
            "company": company or "N/A",
            "location": job_location,
            "salary": "",
            "job_type": data.get("employmentType", ""),
            "date_posted": date_posted,
            "job_url": data.get("url", ""),
            "description": str(data.get("description", ""))[:500],
        }
    except Exception:
        return None


def _extract_card_from_element(card, location: str) -> dict | None:
    """Extract data from a Playwright DOM element (Google Jobs card)."""
    try:
        all_divs = card.query_selector_all("div")
        span = card.query_selector("span")
        span_divs = span.query_selector_all("div") if span else all_divs

        title, company, loc_via = "", "", ""

        if len(span_divs) >= 1:
            title = _get_text(span_divs[0])
        if len(span_divs) >= 2:
            company = _get_text(span_divs[1])
        if len(span_divs) >= 3:
            loc_via = _get_text(span_divs[2])

        # Parse location
        job_location = loc_via
        via_source = ""
        if " via " in loc_via:
            parts = loc_via.split(" via ", 1)
            job_location = parts[0].strip().rstrip("•").strip()
            via_source = parts[1].strip()
        elif "•" in loc_via:
            job_location = loc_via.split("•", 1)[0].strip()

        href = card.get_attribute("href") or ""
        job_url = href if href.startswith("http") else ""

        if not title:
            return None

        return {
            "source": f"google{' (via ' + via_source + ')' if via_source else ''}",
            "title": title,
            "company": company or "N/A",
            "location": job_location or location,
            "salary": "",
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


def _build_search_query(
    search_term: str, location: str, job_type: str | None = None
) -> str:
    """Build the Google search query string."""
    parts = []
    if search_term and search_term.strip():
        parts.append(search_term.strip())
    parts.append("jobs")
    parts.append(f"in {location.strip()}")
    if job_type:
        type_labels = {
            "fulltime": "full time",
            "parttime": "part time",
            "internship": "internship",
            "contract": "contract",
        }
        parts.append(type_labels.get(job_type, job_type))
    return " ".join(parts)


def _filter_by_age(listings: list[dict], hours_old: int) -> list[dict]:
    """Filter listings by age."""
    if not hours_old or hours_old <= 0:
        return listings

    cutoff = datetime.now() - timedelta(hours=hours_old)
    filtered = []

    for listing in listings:
        date_str = listing.get("date_posted", "")
        if not date_str:
            filtered.append(listing)
            continue
        try:
            posted = datetime.strptime(date_str, "%Y-%m-%d")
            if posted >= cutoff:
                filtered.append(listing)
        except (ValueError, TypeError):
            filtered.append(listing)

    return filtered


def _get_text(element) -> str:
    """Get inner text from an element."""
    try:
        return element.inner_text().strip()
    except Exception:
        return ""


def _clean_html(text: str) -> str:
    """Remove HTML entities and tags from text."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    return text.strip()


def _url_encode(text: str) -> str:
    """URL encode a string."""
    import urllib.parse
    return urllib.parse.quote_plus(text)
