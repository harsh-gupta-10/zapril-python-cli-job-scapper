"""
JobSpy Scraper — Wraps python-jobspy to fetch listings from
LinkedIn, Indeed, Naukri, Google Jobs, and Glassdoor.
"""

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from config import (
    JOBSPY_SITE_MAP,
    DEFAULT_COUNTRY_INDEED,
    REQUEST_DELAY_SECONDS,
)

console = Console()


def scrape_with_jobspy(
    search_term: str,
    location: str,
    platforms: list[str],
    max_results: int = 25,
    hours_old: int = 168,
    job_type: str | None = None,
    is_remote: bool = False,
    proxies: list[str] | None = None,
    verbose: int = 1,
) -> pd.DataFrame:
    """
    Scrape jobs from multiple platforms using python-jobspy.

    Args:
        search_term: Job title or keywords to search.
        location: Target city/location.
        platforms: List of platforms to scrape (e.g., ["linkedin", "indeed"]).
        max_results: Maximum results per platform.
        hours_old: Only jobs posted within N hours.
        job_type: Filter by job type (fulltime, parttime, internship, contract).
        is_remote: Filter for remote jobs only.
        proxies: List of proxy URLs.
        verbose: Verbosity level (0=errors, 1=warnings, 2=all).

    Returns:
        A pandas DataFrame with normalized job listings.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        console.print(
            "[bold red]✗[/] python-jobspy not installed. "
            "Run: [cyan]pip install -U python-jobspy[/]"
        )
        return pd.DataFrame()

    # Map platform names to jobspy site_name values
    site_names = []
    for p in platforms:
        p_lower = p.lower().strip()
        if p_lower in JOBSPY_SITE_MAP:
            site_names.append(JOBSPY_SITE_MAP[p_lower])
        elif p_lower == "internshala":
            continue  # Handled separately
        else:
            console.print(f"[yellow]⚠[/] Unknown platform '{p}', skipping.")

    if not site_names:
        console.print("[yellow]⚠[/] No valid JobSpy platforms selected.")
        return pd.DataFrame()

    # Build the google_search_term if Google is included
    google_search_term = None
    if "google" in site_names:
        google_search_term = f"{search_term} jobs in {location}"

    # Build scrape parameters
    scrape_params = {
        "site_name": site_names,
        "search_term": search_term,
        "location": location,
        "results_wanted": max_results,
        "hours_old": hours_old,
        "country_indeed": DEFAULT_COUNTRY_INDEED,
        "verbose": verbose,
    }

    if google_search_term:
        scrape_params["google_search_term"] = google_search_term

    if job_type:
        scrape_params["job_type"] = job_type

    if is_remote:
        scrape_params["is_remote"] = True

    if proxies:
        scrape_params["proxies"] = proxies

    # Fetch full descriptions for LinkedIn (slower but more data)
    if "linkedin" in site_names:
        scrape_params["linkedin_fetch_description"] = True

    # ── Execute the scrape ────────────────────────────────────────
    all_jobs = pd.DataFrame()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Scraping {', '.join(site_names)}...", total=None
        )

        try:
            all_jobs = scrape_jobs(**scrape_params)
            progress.update(
                task,
                completed=len(all_jobs),
                total=len(all_jobs),
                description=f"[green]✓ Scraped {len(all_jobs)} jobs from JobSpy platforms",
            )
        except Exception as e:
            error_msg = str(e)
            progress.update(
                task,
                description=f"[red]✗ JobSpy error: {error_msg[:80]}",
            )
            console.print(f"[red]  Details: {error_msg}[/]")

            # Try scraping platforms individually as fallback
            console.print("[yellow]  Attempting individual platform scraping...[/]")
            all_jobs = _scrape_individual_platforms(
                site_names, scrape_params, progress, google_search_term
            )

    if all_jobs.empty:
        return all_jobs

    # ── Normalize the DataFrame ───────────────────────────────────
    all_jobs = _normalize_dataframe(all_jobs)

    console.print(
        f"[green]  → {len(all_jobs)} jobs collected from JobSpy platforms[/]"
    )
    return all_jobs


def _scrape_individual_platforms(
    site_names: list[str],
    base_params: dict,
    progress: Progress,
    google_search_term: str | None,
) -> pd.DataFrame:
    """
    Fallback: scrape each platform individually so one failure
    doesn't kill the entire run.
    """
    from jobspy import scrape_jobs
    import time

    frames = []

    for site in site_names:
        params = base_params.copy()
        params["site_name"] = [site]

        # Google needs its own search term
        if site != "google" and "google_search_term" in params:
            del params["google_search_term"]
        elif site == "google" and google_search_term:
            params["google_search_term"] = google_search_term

        task = progress.add_task(f"[cyan]  ↳ Scraping {site}...", total=None)

        try:
            df = scrape_jobs(**params)
            frames.append(df)
            progress.update(
                task,
                completed=len(df),
                total=len(df),
                description=f"[green]  ↳ {site}: {len(df)} jobs ✓",
            )
        except Exception as e:
            progress.update(
                task,
                description=f"[red]  ↳ {site}: Failed — {str(e)[:60]}",
            )

        time.sleep(REQUEST_DELAY_SECONDS)

    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the JobSpy DataFrame to have consistent columns.
    """
    # Rename columns to our standard names
    column_map = {
        "site": "source",
        "title": "title",
        "company_name": "company",
        "company": "company",
        "city": "city",
        "state": "state",
        "location": "location",
        "job_type": "job_type",
        "min_amount": "salary_min",
        "max_amount": "salary_max",
        "salary_source": "salary_source",
        "date_posted": "date_posted",
        "job_url": "job_url",
        "job_url_direct": "job_url_direct",
        "description": "description",
        "company_url": "company_url",
        "company_industry": "company_industry",
    }

    # Only rename columns that exist
    rename_cols = {k: v for k, v in column_map.items() if k in df.columns}
    df = df.rename(columns=rename_cols)

    # Build a combined location string if individual parts exist
    if "location" not in df.columns:
        location_parts = []
        if "city" in df.columns:
            location_parts.append(df["city"].fillna(""))
        if "state" in df.columns:
            location_parts.append(df["state"].fillna(""))
        if location_parts:
            df["location"] = (
                pd.concat(location_parts, axis=1)
                .apply(lambda row: ", ".join(filter(None, row)), axis=1)
            )
        else:
            df["location"] = ""

    # Build salary string
    if "salary_min" in df.columns and "salary_max" in df.columns:
        df["salary"] = df.apply(
            lambda row: _format_salary(row.get("salary_min"), row.get("salary_max")),
            axis=1,
        )
    elif "salary" not in df.columns:
        df["salary"] = ""

    # Add tracking columns
    df["location_status"] = "unknown"
    df["resolved_location"] = ""

    # Ensure all values are strings for text columns
    text_cols = ["title", "company", "location", "source", "job_type", "salary", "description"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    return df


def _format_salary(min_val, max_val) -> str:
    """Format salary range into a human-readable string."""
    try:
        if pd.notna(min_val) and pd.notna(max_val):
            return f"₹{int(min_val):,} - ₹{int(max_val):,}"
        elif pd.notna(min_val):
            return f"₹{int(min_val):,}+"
        elif pd.notna(max_val):
            return f"Up to ₹{int(max_val):,}"
    except (ValueError, TypeError):
        pass
    return ""
