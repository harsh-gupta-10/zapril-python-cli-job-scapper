"""
Exporter — Saves job results to CSV and/or JSON files.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from config import OUTPUT_DIR, OUTPUT_COLUMNS

console = Console()


def export_results(
    df: pd.DataFrame,
    location: str,
    search_term: str,
    output_format: str = "csv",
    companies_in_location: list[str] | None = None,
) -> str:
    """
    Export the job results DataFrame to a file and display a summary.

    Args:
        df: The final deduplicated DataFrame.
        location: Target location used in the search.
        search_term: The job search term used.
        output_format: "csv", "json", or "both".
        companies_in_location: List of company names known to be in the target location.

    Returns:
        Path to the primary output file.
    """
    if df.empty:
        console.print("[yellow]⚠ No results to export.[/]")
        return ""

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    location_slug = location.lower().replace(" ", "_").replace(",", "")
    search_slug = search_term.lower().replace(" ", "_")[:20]
    base_name = f"jobs_{search_slug}_{location_slug}_{timestamp}"

    # Ensure output directory exists as a subfolder specific to this run
    output_dir = Path(OUTPUT_DIR) / base_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select and reorder columns for output
    output_cols = [c for c in OUTPUT_COLUMNS if c in df.columns]
    # Include any extra columns not in the standard list
    extra_cols = [c for c in df.columns if c not in OUTPUT_COLUMNS and not c.startswith("_")]
    all_cols = output_cols + extra_cols
    df_export = df[all_cols].copy()

    saved_files = []

    # ── Export CSV ────────────────────────────────────────────────
    if output_format in ("csv", "both"):
        csv_path = output_dir / f"{base_name}.csv"
        df_export.to_csv(csv_path, index=False, encoding="utf-8-sig")
        saved_files.append(str(csv_path))
        console.print(f"[green]📄 CSV saved:[/] {csv_path}")

    # ── Export JSON ───────────────────────────────────────────────
    if output_format in ("json", "both"):
        json_path = output_dir / f"{base_name}.json"
        export_data = {
            "metadata": {
                "search_term": search_term,
                "location": location,
                "timestamp": datetime.now().isoformat(),
                "total_jobs": len(df_export),
                "companies_in_location": companies_in_location or [],
            },
            "jobs": json.loads(df_export.to_json(orient="records", date_format="iso")),
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        saved_files.append(str(json_path))
        console.print(f"[green]📋 JSON saved:[/] {json_path}")

    # ── Export companies list ────────────────────────────────────
    if companies_in_location:
        companies_path = output_dir / f"companies_in_{location_slug}_{timestamp}.txt"
        with open(companies_path, "w", encoding="utf-8") as f:
            f.write(f"Companies with offices in {location}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("=" * 50 + "\n\n")
            for company in companies_in_location:
                f.write(f"• {company}\n")
        console.print(f"[green]🏢 Companies list saved:[/] {companies_path}")

    # ── Display Summary Table ────────────────────────────────────
    _print_summary(df, location, search_term, companies_in_location)

    # ── Display Top Results Preview ──────────────────────────────
    _print_preview_table(df)

    return saved_files[0] if saved_files else ""


def _print_summary(
    df: pd.DataFrame,
    location: str,
    search_term: str,
    companies_in_location: list[str] | None,
):
    """Print a beautiful summary box."""
    console.print()
    console.rule("[bold cyan]📋 RESULTS SUMMARY", style="cyan")
    console.print()

    # Stats
    total = len(df)
    confirmed = len(df[df["location_status"] == "confirmed"]) if "location_status" in df.columns else 0
    inferred = len(df[df["location_status"] == "inferred"]) if "location_status" in df.columns else 0
    unknown = len(df[df["location_status"] == "unknown"]) if "location_status" in df.columns else 0
    different = len(df[df["location_status"] == "different_city"]) if "location_status" in df.columns else 0

    # Sources breakdown
    source_counts = df["source"].value_counts() if "source" in df.columns else pd.Series()

    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column("Key", style="bold")
    summary_table.add_column("Value")

    summary_table.add_row("Search Term", f"[cyan]{search_term}[/]")
    summary_table.add_row("Location", f"[cyan]{location}[/]")
    summary_table.add_row("", "")
    summary_table.add_row("Total Unique Jobs", f"[bold green]{total}[/]")

    if not source_counts.empty:
        sources_str = " | ".join(
            f"{src}: {count}" for src, count in source_counts.items()
        )
        summary_table.add_row("By Platform", f"[dim]{sources_str}[/]")

    summary_table.add_row("", "")
    summary_table.add_row("📍 Location Confirmed", f"[green]{confirmed}[/] ({_pct(confirmed, total)})")
    summary_table.add_row("🔍 Location Inferred", f"[cyan]{inferred}[/] ({_pct(inferred, total)})")
    summary_table.add_row("🌍 Different City", f"[yellow]{different}[/] ({_pct(different, total)})")
    summary_table.add_row("❓ Location Unknown", f"[red]{unknown}[/] ({_pct(unknown, total)})")

    if companies_in_location:
        summary_table.add_row("", "")
        summary_table.add_row(
            f"🏢 Companies in {location}",
            f"[bold magenta]{len(companies_in_location)}[/]",
        )

    console.print(summary_table)
    console.print()


def _print_preview_table(df: pd.DataFrame, max_rows: int = 15):
    """Print a preview of the top job results."""
    console.rule("[bold cyan]🔝 TOP RESULTS", style="cyan")
    console.print()

    preview = df.head(max_rows)

    table = Table(
        show_header=True,
        header_style="bold magenta",
        show_lines=True,
        expand=True,
    )

    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="bold white", max_width=35)
    table.add_column("Company", style="cyan", max_width=25)
    table.add_column("Location", max_width=20)
    table.add_column("Status", width=10)
    table.add_column("Source", style="dim", width=12)
    table.add_column("Salary", max_width=18)

    status_colors = {
        "confirmed": "[green]✓ Confirmed[/]",
        "inferred": "[cyan]▸ Inferred[/]",
        "different_city": "[yellow]◆ Different[/]",
        "unknown": "[red]? Unknown[/]",
    }

    for i, (_, row) in enumerate(preview.iterrows(), 1):
        loc = str(row.get("location", ""))[:20]
        status = status_colors.get(
            row.get("location_status", "unknown"), "[dim]—[/]"
        )
        salary = str(row.get("salary", ""))[:18]

        table.add_row(
            str(i),
            str(row.get("title", ""))[:35],
            str(row.get("company", ""))[:25],
            loc,
            status,
            str(row.get("source", ""))[:12],
            salary if salary and salary != "nan" else "[dim]—[/]",
        )

    console.print(table)
    console.print()


def _pct(part: int, total: int) -> str:
    """Calculate percentage string."""
    if total == 0:
        return "0%"
    return f"{(part / total * 100):.0f}%"
