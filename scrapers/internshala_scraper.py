"""
Internshala Scraper — Custom Playwright-based scraper for Internshala
since python-jobspy does not support it natively.
"""

import re
import time
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from config import REQUEST_DELAY_SECONDS

console = Console()

INTERNSHALA_BASE_URL = "https://internshala.com"
INTERNSHALA_JOBS_URL = "https://internshala.com/jobs/{keyword}-jobs-in-{location}"
INTERNSHALA_INTERNSHIPS_URL = "https://internshala.com/internships/{keyword}-internship-in-{location}"


def scrape_internshala(
    search_term: str,
    location: str,
    max_results: int = 25,
    include_internships: bool = True,
) -> pd.DataFrame:
    """
    Scrape job and internship listings from Internshala using Playwright.

    Args:
        search_term: Job title or keywords.
        location: Target city/location.
        max_results: Maximum results to fetch.
        include_internships: Also scrape internships (not just full-time jobs).

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
        task = progress.add_task("[cyan]Scraping Internshala...", total=None)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()

                # ── Scrape Jobs ──────────────────────────────────
                jobs_url = _build_internshala_url(
                    search_term, location, is_internship=False
                )
                job_listings = _scrape_internshala_page(
                    page, jobs_url, max_results, is_internship=False
                )
                all_listings.extend(job_listings)

                progress.update(
                    task,
                    description=f"[cyan]Internshala: {len(job_listings)} jobs found",
                )

                # ── Scrape Internships ───────────────────────────
                if include_internships:
                    time.sleep(REQUEST_DELAY_SECONDS)

                    intern_url = _build_internshala_url(
                        search_term, location, is_internship=True
                    )
                    intern_listings = _scrape_internshala_page(
                        page, intern_url, max_results, is_internship=True
                    )
                    all_listings.extend(intern_listings)

                browser.close()

        except Exception as e:
            progress.update(
                task,
                description=f"[red]✗ Internshala error: {str(e)[:80]}",
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
            description=f"[green]✓ Internshala: {total} listings scraped",
        )

    if not all_listings:
        return pd.DataFrame()

    df = pd.DataFrame(all_listings)
    df["location_status"] = "unknown"
    df["resolved_location"] = ""

    console.print(f"[green]  → {len(df)} listings collected from Internshala[/]")
    return df


def _build_internshala_url(
    search_term: str, location: str, is_internship: bool
) -> str:
    """Build the Internshala search URL."""
    keyword_slug = re.sub(r"[^a-zA-Z0-9]+", "-", search_term.strip().lower()).strip("-")
    location_slug = re.sub(r"[^a-zA-Z0-9]+", "-", location.strip().lower()).strip("-")

    if is_internship:
        return f"{INTERNSHALA_BASE_URL}/internships/{keyword_slug}-internship-in-{location_slug}"
    else:
        return f"{INTERNSHALA_BASE_URL}/jobs/{keyword_slug}-jobs-in-{location_slug}"


def _scrape_internshala_page(
    page, url: str, max_results: int, is_internship: bool
) -> list[dict]:
    """
    Navigate to an Internshala listing page and extract job/internship data.
    """
    listings = []

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)  # Let dynamic content load

        # Internshala uses different selectors for jobs vs internships
        if is_internship:
            card_selector = ".internship_meta, .individual_internship"
        else:
            card_selector = ".individual_internship, .job-internship-name, .individual_job"

        # Try multiple selectors since Internshala changes their DOM
        cards = page.query_selector_all(card_selector)

        if not cards:
            # Fallback: try a more generic selector
            cards = page.query_selector_all(
                "[class*='internship'], [class*='job_listing'], .container-fluid .internship_meta"
            )

        for card in cards[:max_results]:
            listing = _extract_listing_data(card, is_internship)
            if listing:
                listings.append(listing)

    except Exception as e:
        console.print(f"[yellow]  ⚠ Internshala page error: {str(e)[:80]}[/]")

    return listings


def _extract_listing_data(card, is_internship: bool) -> dict | None:
    """Extract data from a single listing card element."""
    try:
        # Try multiple selectors for each field since DOM varies
        title = _safe_text(card, [
            ".job-internship-name a",
            ".profile a",
            "h3 a",
            ".heading_4_5 a",
            "a.view_detail_button",
        ])

        company = _safe_text(card, [
            ".company_name a",
            ".company-name",
            ".heading_6",
            "p.company_name",
            ".company_and_premium a",
        ])

        location = _safe_text(card, [
            ".locations a",
            ".location_link",
            "#location_names a",
            ".locations span",
            ".individual_internship_details .item_body",
        ])

        stipend = _safe_text(card, [
            ".stipend",
            ".desktop-text .item_body",
            ".stipend_container_table_cell .item_body",
            ".salary span",
        ])

        # Get the link
        link_el = card.query_selector("a.view_detail_button") or card.query_selector("a[href]")
        link = ""
        if link_el:
            href = link_el.get_attribute("href") or ""
            if href:
                link = href if href.startswith("http") else f"{INTERNSHALA_BASE_URL}{href}"

        if not title and not company:
            return None

        return {
            "source": "internshala",
            "title": title or "N/A",
            "company": company or "N/A",
            "location": location or "",
            "salary": stipend or "",
            "job_type": "internship" if is_internship else "fulltime",
            "date_posted": "",
            "job_url": link,
            "description": "",
        }

    except Exception:
        return None


def _safe_text(element, selectors: list[str]) -> str:
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
