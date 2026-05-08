"""
Job Scrapper — CLI Entry Point

A powerful multi-platform job scrapper that aggregates listings from
LinkedIn, Indeed, Naukri, Google Jobs, Glassdoor, and Internshala.
Features intelligent location resolution and fuzzy deduplication.
"""

import argparse
import sys
import os
import time
import signal
import pandas as pd
from pathlib import Path

# Fix Windows console encoding — Rich uses emoji that crash cp1252
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
    parser.add_argument(
        "--resume-state",
        action="store_true",
        help="Resume from partial state file if it matches the current job/city",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip AI description enhancement (saves tokens)",
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

    # State tracking
    import json
    state_file = Path(CACHE_DIR) / "platform_state.json"
    platform_state = {"job": search_term, "city": args.location, "completed": [], "failed": []}

    if args.resume_state and state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                saved_state = json.load(f)
                if saved_state.get("job") == search_term and saved_state.get("city") == args.location:
                    platform_state = saved_state
                    completed = saved_state.get("completed", [])
                    if completed:
                        console.print(f"[bold green]Resuming... Skipping completed platforms: {', '.join(completed)}[/]")
                        platforms = [p for p in platforms if p not in completed]
                        jobspy_platforms = [p for p in jobspy_platforms if p not in completed]
                        if "naukri" in completed: scrape_naukri = False
                        if "google" in completed: scrape_google = False
                        if "glassdoor" in completed: scrape_glassdoor = False
                        if "internshala" in completed: scrape_internshala = False
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read state file: {e}[/]")

    def save_platform_state():
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(platform_state, f, indent=4)

    save_platform_state()
    
    import datetime
    paused_file = Path(CACHE_DIR) / "paused_platforms.json"
    paused_platforms = {}
    if paused_file.exists():
        try:
            with open(paused_file, "r", encoding="utf-8") as f:
                paused_platforms = json.load(f)
        except Exception:
            pass
            
    now = datetime.datetime.now()
    active_pauses = {}
    for p, until_str in paused_platforms.items():
        try:
            until = datetime.datetime.fromisoformat(until_str)
            if now < until:
                active_pauses[p] = until_str
        except Exception:
            pass
    paused_platforms = active_pauses

    def save_pauses():
        with open(paused_file, "w", encoding="utf-8") as f:
            json.dump(paused_platforms, f, indent=4)

    stop_requested = False

    def should_stop():
        nonlocal stop_requested
        if stop_requested:
            return True
        if os.path.exists(os.path.join(CACHE_DIR, "stop_scraper.flag")):
            console.print("\n[bold yellow]⚠️ Stop flag detected. Initiating graceful shutdown...[/]")
            return True
        return False

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: SCRAPING
    # ═══════════════════════════════════════════════════════════════
    console.rule("[bold cyan]Phase 1: Scraping", style="cyan")
    console.print()

    # Custom SIGINT handler for Graceful Stop with Double Confirmation
    def handle_sigint(signum, frame):
        nonlocal stop_requested
        # If not running interactively, just set flag
        if not sys.stdout.isatty():
            console.print("\n[bold yellow]⚠️ Stop signal received. Initiating graceful shutdown after current platform...[/]")
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            stop_requested = True
            return

        console.print()
        console.print("[bold yellow]⚠️ Scraping in progress.[/]")
        try:
            ans = input("Are you sure you want to stop? (y/n): ").strip().lower()
            if ans == 'y':
                console.print("[bold red]Finishing current platform, then stopping gracefully... Press Ctrl+C again to force quit immediately.[/]")
                # Restore default so a second Ctrl+C kills immediately
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                stop_requested = True
            else:
                console.print("[bold green]Resuming scrape...[/]")
        except EOFError:
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            stop_requested = True

    # Install the signal handler
    signal.signal(signal.SIGINT, handle_sigint)

    all_jobs = pd.DataFrame()
    start_time = time.time()

    try:

        # ── Scrape Platforms Individually ──────────────────────────────
        for platform in platforms:
            if should_stop():
                console.print("\n[bold red]⚠️ Stop requested! Proceeding to deduplicate and export gathered data so far...[/]")
                break

            if platform in platform_state.get("completed", []):
                continue
                
            if platform in paused_platforms:
                until_str = paused_platforms[platform]
                until_dt = datetime.datetime.fromisoformat(until_str)
                minutes_left = int((until_dt - datetime.datetime.now()).total_seconds() / 60)
                console.print(f"[yellow]⏭ Skipping {platform} (Paused for {minutes_left} more mins due to previous bans)[/]")
                continue
            
            try:
                results = pd.DataFrame()
                if platform in JOBSPY_PLATFORMS:
                    from scrapers.jobspy_scraper import scrape_with_jobspy
                    results = scrape_with_jobspy(
                        search_term=search_term,
                        location=args.location,
                        platforms=[platform],
                        max_results=args.max_results,
                        hours_old=args.hours_old,
                        job_type=args.job_type,
                        is_remote=args.remote,
                        proxies=args.proxy,
                        verbose=args.verbose,
                    )
                elif platform == "naukri" and scrape_naukri:
                    console.print()
                    from scrapers.naukri_scraper import scrape_naukri as _scrape_naukri
                    results = _scrape_naukri(
                        search_term=search_term,
                        location=args.location,
                        max_results=args.max_results,
                        hours_old=args.hours_old,
                        job_type=args.job_type,
                    )
                elif platform == "google" and scrape_google:
                    console.print()
                    from scrapers.google_jobs_scraper import scrape_google_jobs as _scrape_google
                    results = _scrape_google(
                        search_term=search_term,
                        location=args.location,
                        max_results=args.max_results,
                        hours_old=args.hours_old,
                        job_type=args.job_type,
                    )
                elif platform == "glassdoor" and scrape_glassdoor:
                    console.print()
                    from scrapers.glassdoor_scraper import scrape_glassdoor as _scrape_glassdoor
                    results = _scrape_glassdoor(
                        search_term=search_term,
                        location=args.location,
                        max_results=args.max_results,
                        hours_old=args.hours_old,
                        job_type=args.job_type,
                    )
                elif platform == "internshala" and scrape_internshala:
                    console.print()
                    from scrapers.internshala_scraper import scrape_internshala as _scrape_internshala
                    results = _scrape_internshala(
                        search_term=search_term,
                        location=args.location,
                        max_results=args.max_results,
                        include_internships=(args.job_type in (None, "internship")),
                    )
                    
                if not results.empty:
                    all_jobs = pd.concat([all_jobs, results], ignore_index=True)
                    
                platform_state.setdefault("completed", []).append(platform)
                save_platform_state()
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                err_str = str(e).lower()
                is_ban = any(x in err_str for x in ["429", "403", "captcha", "blocked", "banned", "too many requests"])
                if is_ban:
                    console.print(f"[red]✗ {platform} blocked us! Pausing this platform for 1 hour.[/]")
                    until = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
                    paused_platforms[platform] = until
                    save_pauses()
                else:
                    console.print(f"[red]Error scraping {platform}: {e}[/]")
                
                platform_state.setdefault("failed", []).append(platform)
                save_platform_state()

    except KeyboardInterrupt:
        console.print("\n[bold red]⚠️ Scrape phase interrupted! Proceeding to deduplicate and export gathered data so far...[/]")
        
    finally:
        # Restore original signal handler when scraping finishes or is interrupted
        signal.signal(signal.SIGINT, signal.SIG_DFL)

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
    # PHASE 3.5: AI ENHANCEMENT
    # ═══════════════════════════════════════════════════════════════
    if not args.skip_ai:
        console.rule("[bold cyan]Phase 3.5: AI Description Enhancement", style="cyan")
        console.print()

        from processors.description_improver import DescriptionImprover

        improver = DescriptionImprover()
        all_jobs = improver.process_dataframe(all_jobs)
        console.print()
    else:
        console.print("[yellow]⏭ AI enrichment skipped (--skip-ai)[/]")
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
    
    # Clear state file on successful full completion
    if state_file.exists():
        try:
            os.remove(state_file)
        except Exception:
            pass


if __name__ == "__main__":
    main()
