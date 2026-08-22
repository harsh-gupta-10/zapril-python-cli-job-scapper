"""
Foundit Scraper — extracts listings from foundit.in search pages and
parses structured JobPosting data from each job detail page.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from processors.field_extractor import (
    clean_html_text,
    extract_salary_text,
    extract_work_experience,
    normalize_date_posted,
    normalize_text,
)

console = Console()

FOUNDIT_BASE_URL = "https://www.foundit.in"
_FOUNDIT_JOB_LINK_RE = re.compile(
    r'href=["\'](?P<href>(?:https://www\.foundit\.in)?/job/[^"\']+)["\']',
    re.IGNORECASE,
)


def scrape_foundit(
    search_term: str,
    location: str,
    max_results: int = 25,
    hours_old: int = 168,
    job_type: str | None = None,
) -> pd.DataFrame:
    """Scrape job listings from Foundit."""
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        console.print(
            "[bold red]✗[/] curl-cffi not installed. "
            "Run: [cyan]pip install curl-cffi[/]"
        )
        return pd.DataFrame()

    search_urls = _collect_job_urls(
        cffi_requests=cffi_requests,
        search_term=search_term,
        location=location,
        max_results=max_results,
    )
    if not search_urls:
        console.print("[yellow]  ⚠ Foundit returned no job links.[/]")
        return pd.DataFrame()

    listings: list[dict] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Scraping Foundit job details...", total=len(search_urls))
        workers = min(8, max(2, len(search_urls)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_fetch_job_detail, cffi_requests, url, location): url
                for url in search_urls
            }
            for future in as_completed(futures):
                try:
                    listing = future.result()
                except Exception:
                    listing = None
                if listing and _job_type_matches(listing, job_type):
                    listings.append(listing)
                progress.advance(task, 1)

    if not listings:
        return pd.DataFrame()

    listings = _filter_by_age(listings, hours_old)
    df = pd.DataFrame(listings[:max_results])
    df["location_status"] = "unknown"
    df["resolved_location"] = ""
    console.print(f"[green]  → {len(df)} listings collected from Foundit[/]")
    return df


def _collect_job_urls(
    *,
    cffi_requests,
    search_term: str,
    location: str,
    max_results: int,
) -> list[str]:
    session = cffi_requests.Session(impersonate="chrome124")
    urls: list[str] = []
    seen: set[str] = set()

    page = 1
    max_pages = max(1, (max_results + 19) // 20) + 1

    while len(urls) < max_results and page <= max_pages:
        search_url = _build_search_url(search_term, location, page)
        response = session.get(search_url, timeout=20)
        if response.status_code != 200:
            break

        page_links = _extract_job_links(response.text)
        if not page_links:
            break

        new_count = 0
        for link in page_links:
            if link in seen:
                continue
            seen.add(link)
            urls.append(link)
            new_count += 1
            if len(urls) >= max_results:
                break

        if new_count == 0:
            break
        page += 1
        time.sleep(0.4)

    return urls[:max_results]


def _build_search_url(search_term: str, location: str, page: int) -> str:
    location_slug = _slugify(location) or "india"
    if search_term and search_term.strip():
        search_slug = _slugify(search_term)
        path = f"{search_slug}-jobs-in-{location_slug}"
    else:
        path = f"jobs-in-{location_slug}"

    if page > 1:
        path = f"{path}-{page}"
    return f"{FOUNDIT_BASE_URL}/search/{path}"


def _extract_job_links(html: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    for match in _FOUNDIT_JOB_LINK_RE.finditer(html):
        href = match.group("href").strip()
        if href.startswith("/"):
            href = f"{FOUNDIT_BASE_URL}{href}"
        href = href.split("?")[0]
        if href in seen:
            continue
        seen.add(href)
        links.append(href)

    return links


def _fetch_job_detail(cffi_requests, url: str, default_location: str) -> dict | None:
    try:
        response = cffi_requests.get(url, impersonate="chrome124", timeout=25)
    except Exception:
        return None
    if response.status_code != 200:
        return None

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        data = _extract_job_posting_json_ld(soup)
        if not data:
            return None

        description = clean_html_text(data.get("description"))
        salary = _parse_salary_from_json_ld(data)
        if not salary:
            salary = extract_salary_text(description)

        experience = extract_work_experience(
            data.get("experienceRequirements"),
            data.get("qualifications"),
            description,
            data.get("title"),
        )

        return {
            "source": "foundit",
            "title": normalize_text(data.get("title")) or "N/A",
            "company": _extract_company_name(data) or "N/A",
            "location": _extract_location(data.get("jobLocation"), default_location),
            "salary": salary,
            "work_experience": experience,
            "job_type": _extract_job_type(data.get("employmentType")),
            "date_posted": normalize_date_posted(data.get("datePosted")),
            "job_url": normalize_text(data.get("url")) or url,
            "description": description,
        }
    except Exception:
        return None


def _extract_job_posting_json_ld(soup: BeautifulSoup) -> dict | None:
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in scripts:
        raw_text = script.get_text(strip=True)
        if not raw_text:
            continue
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict) and payload.get("@type") == "JobPosting":
            return payload

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    return item

    return None


def _extract_company_name(data: dict) -> str:
    org = data.get("hiringOrganization")
    if isinstance(org, dict):
        return normalize_text(org.get("name"))
    return normalize_text(org)


def _extract_location(job_location, default_location: str) -> str:
    if isinstance(job_location, list) and job_location:
        return _extract_location(job_location[0], default_location)

    if isinstance(job_location, dict):
        address = job_location.get("address")
        if isinstance(address, dict):
            city = normalize_text(address.get("addressLocality"))
            region = normalize_text(address.get("addressRegion"))
            country = normalize_text(address.get("addressCountry"))
            raw_parts = [city, region, country]
            parts: list[str] = []
            seen: set[str] = set()
            for raw in raw_parts:
                for part in [p.strip() for p in raw.split(",") if p.strip()]:
                    key = part.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    parts.append(part)
            if parts:
                return ", ".join(parts)

    return normalize_text(default_location)


def _extract_job_type(employment_type) -> str:
    if isinstance(employment_type, list):
        return ", ".join(normalize_text(item).lower() for item in employment_type if normalize_text(item))
    return normalize_text(employment_type).lower()


def _parse_salary_from_json_ld(data: dict) -> str:
    base_salary = data.get("baseSalary")
    if not isinstance(base_salary, dict):
        return ""

    currency = normalize_text(base_salary.get("currency")) or "INR"
    salary_value = base_salary.get("value")

    if isinstance(salary_value, dict):
        min_value = salary_value.get("minValue")
        max_value = salary_value.get("maxValue")
        unit = normalize_text(salary_value.get("unitText")).lower()
        unit_suffix = " PA" if "year" in unit else (" PM" if "month" in unit else "")

        if min_value is not None and max_value is not None:
            return _format_salary_pair(min_value, max_value, currency, unit_suffix)
        if min_value is not None:
            return f"{_currency_symbol(currency)}{_fmt_num(min_value)}+{unit_suffix}"
        if max_value is not None:
            return f"Up to {_currency_symbol(currency)}{_fmt_num(max_value)}{unit_suffix}"

    if isinstance(salary_value, (int, float, str)):
        return f"{_currency_symbol(currency)}{_fmt_num(salary_value)}"

    return ""


def _format_salary_pair(min_value, max_value, currency: str, suffix: str) -> str:
    symbol = _currency_symbol(currency)
    return f"{symbol}{_fmt_num(min_value)} - {symbol}{_fmt_num(max_value)}{suffix}"


def _currency_symbol(currency: str) -> str:
    upper = currency.upper()
    if upper == "INR":
        return "₹"
    if upper == "USD":
        return "$"
    return f"{upper} "


def _fmt_num(value) -> str:
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return normalize_text(value)


def _job_type_matches(listing: dict, requested_job_type: str | None) -> bool:
    if not requested_job_type:
        return True
    listing_job_type = normalize_text(listing.get("job_type")).lower()
    return requested_job_type.lower() in listing_job_type if listing_job_type else True


def _filter_by_age(listings: list[dict], hours_old: int) -> list[dict]:
    if not hours_old or hours_old <= 0:
        return listings

    cutoff = datetime.now() - timedelta(hours=hours_old)
    filtered: list[dict] = []

    for listing in listings:
        date_str = normalize_text(listing.get("date_posted"))
        if not date_str:
            filtered.append(listing)
            continue
        try:
            posted = datetime.strptime(date_str, "%Y-%m-%d")
            if posted >= cutoff:
                filtered.append(listing)
        except ValueError:
            filtered.append(listing)

    return filtered


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", normalize_text(value).lower()).strip("-")
