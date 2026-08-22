"""
Naukri Scraper — Uses curl_cffi with Chrome TLS impersonation
to access Naukri's internal job search API.

Falls back gracefully with Camoufox stealth HTML fetch when blocked by anti-bot.
"""

import asyncio
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
from processors.field_extractor import (
    clean_html_text,
    extract_salary_text,
    extract_work_experience,
    normalize_date_posted,
    normalize_text,
)

console = Console()

NAUKRI_BASE_URL = "https://www.naukri.com"
NAUKRI_API_URL = "https://www.naukri.com/jobapi/v3/search"


def scrape_naukri(
    search_term: str,
    location: str,
    max_results: int = 25,
    hours_old: int = 168,
    job_type: str | None = None,
) -> pd.DataFrame:
    """
    Scrape job listings from Naukri.com.

    Uses curl_cffi with TLS fingerprint impersonation and Naukri's
    internal API. Falls back to Camoufox stealth HTML fetch when blocked.
    """
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        console.print(
            "[bold red]✗[/] curl-cffi not installed. "
            "Run: [cyan]pip install curl-cffi[/]"
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
        task = progress.add_task("[cyan]Scraping Naukri...", total=None)

        try:
            # ── Strategy 1: Use API with session cookies ─────
            progress.update(task, description="[cyan]Naukri: Establishing session...")

            session = cffi_requests.Session(impersonate="chrome124")

            # Get initial page to establish cookies
            session.get(NAUKRI_BASE_URL, timeout=15)
            time.sleep(1)

            # Try the API
            progress.update(task, description="[cyan]Naukri: Querying job API...")

            current_page = 1
            max_api_pages = max(1, (max_results + 19) // 20)

            while len(all_listings) < max_results and current_page <= max_api_pages:
                api_results = _fetch_api_page(
                    session, search_term, location, current_page, 20, job_type
                )

                if api_results is None:
                    # API blocked — try HTML fallback
                    if current_page == 1:
                        progress.update(
                            task,
                            description="[cyan]Naukri: API blocked, trying Camoufox stealth...",
                        )
                        html_results = _scrape_html_with_camoufox(
                            search_term, location, max_results, job_type
                        )
                        if not html_results:
                            progress.update(
                                task,
                                description="[cyan]Naukri: Camoufox unavailable, trying HTTP fallback...",
                            )
                            html_results = _scrape_html_fallback(
                                session, search_term, location, max_results, job_type
                            )
                        all_listings.extend(html_results)
                    break

                if not api_results:
                    break  # No more results

                all_listings.extend(api_results)
                current_page += 1

                progress.update(
                    task,
                    description=f"[cyan]Naukri: {len(all_listings)} jobs (page {current_page - 1})",
                )

                time.sleep(1)

        except Exception as e:
            progress.update(
                task,
                description=f"[red]✗ Naukri error: {str(e)[:80]}",
            )
            console.print(f"[red]  Details: {str(e)}[/]")

        total = min(len(all_listings), max_results)
        if total > 0:
            progress.update(
                task,
                completed=total,
                total=total,
                description=f"[green]✓ Naukri: {total} listings scraped",
            )
        else:
            progress.update(
                task,
                completed=0,
                total=0,
                description="[yellow]⚠ Naukri: blocked by anti-bot (reCAPTCHA)",
            )

    if not all_listings:
        console.print(
            "[yellow]  ⚠ Naukri API requires reCAPTCHA — scraping blocked.[/]\n"
            "[yellow]    Tip: Use [cyan]--no-naukri[/cyan] to skip, or try with a proxy: "
            "[cyan]--proxy http://your:proxy@ip:port[/][/]"
        )
        return pd.DataFrame()

    # Filter by hours_old
    all_listings = _filter_by_age(all_listings, hours_old)

    df = pd.DataFrame(all_listings[:max_results])
    df["location_status"] = "unknown"
    df["resolved_location"] = ""

    console.print(f"[green]  → {len(df)} listings collected from Naukri[/]")
    return df


def _fetch_api_page(
    session, search_term: str, location: str, page: int, count: int, job_type: str | None
) -> list[dict] | None:
    """
    Fetch a page of results from Naukri's internal API.
    Returns None if blocked, empty list if no results, or list of listings.
    """
    params = {
        "noOfResults": str(count),
        "urlType": "search_by_keyword",
        "searchType": "adv",
        "pageNo": str(page),
    }

    if search_term and search_term.strip():
        params["keyword"] = search_term

    if location and location.strip():
        params["location"] = location

    if job_type:
        type_map = {
            "fulltime": "fullTime",
            "parttime": "partTime",
            "internship": "internship",
            "contract": "contract",
        }
        params["jobType"] = type_map.get(job_type, job_type)

    headers = {
        "appid": "109",
        "systemid": "Starter",
        "Accept": "application/json",
    }

    try:
        resp = session.get(
            NAUKRI_API_URL, headers=headers, params=params, timeout=15
        )

        if resp.status_code == 406:
            # reCAPTCHA required
            return None

        if resp.status_code != 200:
            return None

        data = resp.json()

        if not data.get("jobDetails"):
            return []

        listings = []
        for job in data["jobDetails"]:
            listing = _parse_api_job(job)
            if listing:
                listings.append(listing)

        return listings

    except Exception:
        return None


def _parse_api_job(job: dict) -> dict | None:
    """Parse a single job from Naukri's API response."""
    try:
        title = job.get("title", "") or ""
        company = job.get("companyName", "") or ""
        placeholders = job.get("placeholders", []) or []

        location = ""
        for ph in placeholders:
            if str(ph.get("type", "")).lower() in {"location", "loc"}:
                location = ph.get("value", "") or ""
                break
        if not location and placeholders:
            location = placeholders[0].get("value", "") or ""

        # Salary
        salary = ""
        for ph in placeholders:
            if ph.get("type") == "salary":
                salary = ph.get("value", "")
                break

        # Experience
        experience = ""
        for ph in placeholders:
            if ph.get("type") == "experience":
                experience = ph.get("value", "")
                break

        # URL
        job_url = job.get("jdURL", "") or ""
        if job_url and not job_url.startswith("http"):
            job_url = f"{NAUKRI_BASE_URL}{job_url}"

        # Date
        created = job.get("createdDate", "")

        # Tags/skills
        tags = job.get("tagsAndSkills", "")

        description = clean_html_text(job.get("jobDescription") or job.get("jd") or "")

        if not title and not company:
            return None

        desc_parts = []
        if experience:
            desc_parts.append(f"Experience: {experience}")
        if tags:
            desc_parts.append(f"Skills: {tags}")

        if not description and desc_parts:
            description = " | ".join(desc_parts)

        return {
            "source": "naukri",
            "title": title.strip(),
            "company": company.strip(),
            "location": normalize_text(location),
            "salary": normalize_text(salary) or extract_salary_text(description),
            "work_experience": extract_work_experience(experience, description),
            "job_type": job.get("jobType", "").lower() if job.get("jobType") else "",
            "date_posted": normalize_date_posted(created),
            "job_url": job_url,
            "description": description,
        }

    except Exception:
        return None


def _scrape_html_fallback(
    session, search_term: str, location: str, max_results: int, job_type: str | None
) -> list[dict]:
    """
    Fallback: try to extract job data from the rendered HTML page.
    This is unreliable since Naukri loads jobs via JavaScript, but
    sometimes SSR data is present.
    """
    listings = []

    try:
        url = _build_naukri_url(search_term, location, job_type)
        resp = session.get(url, timeout=15)

        if resp.status_code != 200:
            return []

        html = resp.text
        listings = _extract_jobs_from_html(html, max_results)

    except Exception:
        pass

    return listings


def _scrape_html_with_camoufox(
    search_term: str, location: str, max_results: int, job_type: str | None
) -> list[dict]:
    """Use Camoufox stealth fetcher for Naukri HTML fallback."""
    try:
        from scrapers.scraper_engine import ScraperEngine, ScraperEngineError
    except ImportError:
        return []

    url = _build_naukri_url(search_term, location, job_type)
    try:
        engine = ScraperEngine()
        html = asyncio.run(engine.fetch(url))
    except (ScraperEngineError, RuntimeError):
        return []

    return _extract_jobs_from_html(html, max_results)


def _extract_jobs_from_html(html: str, max_results: int) -> list[dict]:
    """Extract job rows from Naukri HTML script payloads."""
    listings = []

    patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
        r'window\.__NEXT_DATA__\s*=\s*({.*?});',
        r'"jobDetails"\s*:\s*(\[.*?\])',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            continue

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict):
            jobs = data.get("jobDetails", []) or data.get("jobs", [])
        elif isinstance(data, list):
            jobs = data
        else:
            continue

        for job in jobs[:max_results]:
            listing = _parse_api_job(job)
            if listing:
                listings.append(listing)

        if listings:
            break

    return listings


def _build_naukri_url(
    search_term: str, location: str, job_type: str | None = None
) -> str:
    """Build a Naukri search URL."""
    location_slug = re.sub(r"[^a-zA-Z0-9]+", "-", location.strip().lower()).strip("-")

    if search_term and search_term.strip():
        keyword_slug = re.sub(
            r"[^a-zA-Z0-9]+", "-", search_term.strip().lower()
        ).strip("-")
        path = f"{keyword_slug}-jobs-in-{location_slug}"
    else:
        path = f"jobs-in-{location_slug}"

    return f"{NAUKRI_BASE_URL}/{path}"


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


def _normalize_api_date(date_val) -> str:
    """Convert Naukri API date to YYYY-MM-DD."""
    return normalize_date_posted(date_val)
