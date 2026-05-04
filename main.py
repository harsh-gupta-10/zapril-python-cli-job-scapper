"""
Job Scrapper — CLI Entry Point

A powerful multi-platform job scrapper that aggregates listings from
LinkedIn, Indeed, Naukri, Google Jobs, Glassdoor, and Internshala.
Features intelligent location resolution and fuzzy deduplication.
"""

import argparse
import sys
import time
import pandas as pd
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from config import (
    SUPPORTED_PLATFORMS,
    JOBSPY_PLATFORMS,
    INTERNSHALA_ENABLED,
    GLASSDOOR_ENABLED,
    NAUKRI_ENABLED,
    GOOGLE_JOBS_ENABLED,
    DEFAULT_MAX_RESULTS,
    DEFAULT_HOURS_OLD,
    DEFAULT_VERBOSE,
    OUTPUT_DIR,
    CACHE_DIR,
)

console = Console()


def print_banner():
    """Print a stylish banner."""
    banner_text = Text()
    banner_text.append("🔍 JOB SCRAPPER", style="bold cyan")
    banner_text.append("\n")
    banner_text.append(
        "Multi-platform job aggregator with smart location resolution",
        style="dim white",
    )

    console.print(
        Panel(
            banner_text,
            border_style="cyan",
            padding=(1, 4),
        )
    )
    console.print()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="🔍 Job Scrapper — Scrape, deduplicate, and enrich job listings from multiple platforms.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --location "Mumbai"                              # all jobs in Mumbai
  %(prog)s --search "Software Engineer" --location "Mumbai"
  %(prog)s -s "Data Analyst" -l "Bangalore" -p linkedin indeed naukri
  %(prog)s -s "Python Developer" -l "Delhi" --max-results 50 --hours-old 72
  %(prog)s -s "Frontend Dev" -l "Pune" --format json --proxy "http://user:pass@ip:port"
  %(prog)s -s "ML Engineer" -l "Chennai" --skip-location-check
        """,
    )

    # Search argument (optional — omit to scrape all jobs in the location)
    parser.add_argument(
        "-s", "--search",
        type=str,
        required=False,
        default=None,
        help="Job title or keywords to search for (omit to scrape all jobs in the location)",
    )
    parser.add_argument(
        "-l", "--location",
        type=str,
        required=True,
        help="Target city/location (e.g., 'Mumbai', 'Bangalore')",
    )

    # Optional arguments
    parser.add_argument(
        "-p", "--platforms",
        nargs="+",
        default=None,
        help="Platforms to scrape (default: all). Options: linkedin, indeed, naukri, google, glassdoor, internshala",
    )
    parser.add_argument(
        "-n", "--max-results",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help=f"Maximum results per platform (default: {DEFAULT_MAX_RESULTS})",
    )
    parser.add_argument(
        "--hours-old",
        type=int,
        default=DEFAULT_HOURS_OLD,
        help=f"Only jobs posted within N hours (default: {DEFAULT_HOURS_OLD} = 7 days)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["csv", "json", "both", "sql"],
        default="csv",
        help="Output format (default: csv)",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        nargs="+",
        default=None,
        help="Proxy URL(s) for scraping (e.g., 'http://user:pass@ip:port')",
    )
    parser.add_argument(
        "--skip-location-check",
        action="store_true",
        help="Skip company location cross-check (faster)",
    )
    parser.add_argument(
        "-v", "--verbose",
        type=int,
        choices=[0, 1, 2],
        default=DEFAULT_VERBOSE,
        help="Verbosity level: 0=errors, 1=warnings, 2=all (default: 1)",
    )
    parser.add_argument(
        "--job-type",
        choices=["fulltime", "parttime", "internship", "contract"],
        default=None,
        help="Filter by job type",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Filter for remote jobs only",
    )
    parser.add_argument(
        "--no-internshala",
        action="store_true",
        help="Skip Internshala scraping",
    )
    parser.add_argument(
        "--no-glassdoor",
        action="store_true",
        help="Skip Glassdoor scraping",
    )
    parser.add_argument(
        "--no-naukri",
        action="store_true",
        help="Skip Naukri scraping",
    )
    parser.add_argument(
        "--no-google",
        action="store_true",
        help="Skip Google Jobs scraping",
    )

    return parser.parse_args()


def main():
    """Main execution flow."""
    args = parse_args()

    # Resolve the search term — when omitted, scrape all jobs in the location
    search_display = args.search if args.search else f"All jobs in {args.location}"
    search_term = args.search if args.search else ""  # broad / empty query

    print_banner()

    # Display search config
    console.print(f"[bold]Search:[/]     [cyan]{search_display}[/]")
    console.print(f"[bold]Location:[/]   [cyan]{args.location}[/]")

    # Determine platforms
    all_platforms = JOBSPY_PLATFORMS.copy()  # LinkedIn, Indeed
    if NAUKRI_ENABLED and not args.no_naukri:
        all_platforms.append("naukri")
    if GOOGLE_JOBS_ENABLED and not args.no_google:
        all_platforms.append("google")
    if GLASSDOOR_ENABLED and not args.no_glassdoor:
        all_platforms.append("glassdoor")
    if INTERNSHALA_ENABLED and not args.no_internshala:
        all_platforms.append("internshala")

    platforms = args.platforms if args.platforms else all_platforms
    platforms = [p.lower().strip() for p in platforms]

    # Separate JobSpy platforms from Playwright-based scrapers
    jobspy_platforms = [p for p in platforms if p in JOBSPY_PLATFORMS]
    scrape_naukri = "naukri" in platforms and not args.no_naukri
    scrape_google = "google" in platforms and not args.no_google
    scrape_glassdoor = "glassdoor" in platforms and not args.no_glassdoor
    scrape_internshala = "internshala" in platforms and not args.no_internshala

    console.print(
        f"[bold]Platforms:[/]  [cyan]{', '.join(platforms)}[/]"
    )
    console.print(
        f"[bold]Max/platform:[/] [cyan]{args.max_results}[/]  |  "
        f"[bold]Hours old:[/] [cyan]{args.hours_old}[/]  |  "
        f"[bold]Format:[/] [cyan]{args.format}[/]"
    )
    if args.job_type:
        console.print(f"[bold]Job Type:[/]  [cyan]{args.job_type}[/]")
    if args.remote:
        console.print(f"[bold]Remote:[/]    [cyan]Yes[/]")
    if args.proxy:
        console.print(f"[bold]Proxies:[/]   [cyan]{len(args.proxy)} configured[/]")
    console.print()

    # Ensure directories exist
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: SCRAPING
    # ═══════════════════════════════════════════════════════════════
    console.rule("[bold cyan]Phase 1: Scraping", style="cyan")
    console.print()

    all_jobs = pd.DataFrame()
    start_time = time.time()

    # ── Scrape via JobSpy ─────────────────────────────────────────
    if jobspy_platforms:
        from scrapers.jobspy_scraper import scrape_with_jobspy

        jobspy_results = scrape_with_jobspy(
            search_term=search_term,
            location=args.location,
            platforms=jobspy_platforms,
            max_results=args.max_results,
            hours_old=args.hours_old,
            job_type=args.job_type,
            is_remote=args.remote,
            proxies=args.proxy,
            verbose=args.verbose,
        )

        if not jobspy_results.empty:
            all_jobs = pd.concat([all_jobs, jobspy_results], ignore_index=True)

    # ── Scrape Naukri (Playwright) ────────────────────────────────
    if scrape_naukri:
        console.print()
        from scrapers.naukri_scraper import scrape_naukri as _scrape_naukri

        naukri_results = _scrape_naukri(
            search_term=search_term,
            location=args.location,
            max_results=args.max_results,
            hours_old=args.hours_old,
            job_type=args.job_type,
        )

        if not naukri_results.empty:
            all_jobs = pd.concat([all_jobs, naukri_results], ignore_index=True)

    # ── Scrape Google Jobs (Playwright) ───────────────────────────
    if scrape_google:
        console.print()
        from scrapers.google_jobs_scraper import scrape_google_jobs as _scrape_google

        google_results = _scrape_google(
            search_term=search_term,
            location=args.location,
            max_results=args.max_results,
            hours_old=args.hours_old,
            job_type=args.job_type,
        )

        if not google_results.empty:
            all_jobs = pd.concat([all_jobs, google_results], ignore_index=True)

    # ── Scrape Glassdoor (Playwright) ─────────────────────────────
    if scrape_glassdoor:
        console.print()
        from scrapers.glassdoor_scraper import scrape_glassdoor as _scrape_glassdoor

        glassdoor_results = _scrape_glassdoor(
            search_term=search_term,
            location=args.location,
            max_results=args.max_results,
            hours_old=args.hours_old,
            job_type=args.job_type,
        )

        if not glassdoor_results.empty:
            all_jobs = pd.concat([all_jobs, glassdoor_results], ignore_index=True)

    # ── Scrape Internshala (Playwright) ───────────────────────────
    if scrape_internshala:
        console.print()
        from scrapers.internshala_scraper import scrape_internshala as _scrape_internshala

        internshala_results = _scrape_internshala(
            search_term=search_term,
            location=args.location,
            max_results=args.max_results,
            include_internships=(args.job_type in (None, "internship")),
        )

        if not internshala_results.empty:
            all_jobs = pd.concat([all_jobs, internshala_results], ignore_index=True)

    scrape_time = time.time() - start_time

    console.print()
    console.print(
        f"[bold green]📊 Total raw results:[/] {len(all_jobs)} jobs "
        f"[dim]({scrape_time:.1f}s)[/]"
    )
    console.print()

    if all_jobs.empty:
        console.print(
            "[bold red]✗ No jobs found. Try different search terms, "
            "a broader location, or check your internet connection.[/]"
        )
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2: DEDUPLICATION
    # ═══════════════════════════════════════════════════════════════
    console.rule("[bold cyan]Phase 2: Deduplication", style="cyan")
    console.print()

    from processors.deduplicator import deduplicate_jobs

    all_jobs = deduplicate_jobs(all_jobs)
    console.print()

    # ═══════════════════════════════════════════════════════════════
    # PHASE 3: LOCATION RESOLUTION
    # ═══════════════════════════════════════════════════════════════
    companies_in_location = []

    if not args.skip_location_check:
        console.rule("[bold cyan]Phase 3: Location Resolution", style="cyan")
        console.print()

        from processors.location_resolver import LocationResolver

        resolver = LocationResolver()
        all_jobs = resolver.enrich_jobs_with_location(all_jobs, args.location)

        # Get list of companies known to be in the target location
        companies_in_location = resolver.get_companies_in_location(args.location)

        console.print()
    else:
        console.print("[yellow]⏭ Location check skipped (--skip-location-check)[/]")
        console.print()

    # ═══════════════════════════════════════════════════════════════
    # PHASE 4: EXPORT
    # ═══════════════════════════════════════════════════════════════
    console.rule("[bold cyan]Phase 4: Export & Summary", style="cyan")
    console.print()

    from exporters.exporter import export_results

    output_path = export_results(
        df=all_jobs,
        location=args.location,
        search_term=search_term or "all_jobs",
        output_format=args.format,
        companies_in_location=companies_in_location,
    )

    total_time = time.time() - start_time

    console.rule(style="cyan")
    console.print(
        f"[bold green]✅ Done![/] Total time: [cyan]{total_time:.1f}s[/]  |  "
        f"Output: [cyan]{output_path}[/]"
    )
    console.print()


if __name__ == "__main__":
    main()
