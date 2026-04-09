"""
Deduplicator — Removes duplicate job listings using fuzzy matching
on company name, job title, and location.
"""

import re
import pandas as pd
from rapidfuzz import fuzz
from rich.console import Console

from config import FUZZY_MATCH_THRESHOLD, COMPANY_SUFFIXES_TO_STRIP

console = Console()


def deduplicate_jobs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate job listings from the DataFrame.

    Deduplication strategy:
    1. Exact URL dedup (same job_url → definitely duplicate)
    2. Fuzzy composite key dedup (similar company + title + location)
    3. When duplicates found, keep the entry with the most complete data.

    Args:
        df: DataFrame with job listings.

    Returns:
        Deduplicated DataFrame.
    """
    if df.empty:
        return df

    original_count = len(df)

    # ── Phase 1: Exact URL deduplication ──────────────────────────
    if "job_url" in df.columns:
        # Remove rows with identical job URLs (keep first)
        url_mask = df["job_url"].notna() & (df["job_url"] != "") & (df["job_url"] != "nan")
        df_with_urls = df[url_mask].drop_duplicates(subset=["job_url"], keep="first")
        df_without_urls = df[~url_mask]
        df = pd.concat([df_with_urls, df_without_urls], ignore_index=True)

    url_dedup_count = original_count - len(df)

    # ── Phase 2: Normalize text fields for comparison ─────────────
    df["_norm_company"] = df["company"].apply(_normalize_company)
    df["_norm_title"] = df["title"].apply(_normalize_title)
    df["_norm_location"] = df["location"].apply(lambda x: str(x).strip().lower())

    # ── Phase 3: Fuzzy composite key deduplication ────────────────
    # Build a composite key and compare
    keep_indices = []
    seen_groups = []  # List of (norm_company, norm_title, norm_location) tuples

    # Sort by data completeness (more complete entries first)
    df["_completeness"] = df.apply(_calc_completeness, axis=1)
    df = df.sort_values("_completeness", ascending=False).reset_index(drop=True)

    for idx, row in df.iterrows():
        norm_company = row["_norm_company"]
        norm_title = row["_norm_title"]
        norm_location = row["_norm_location"]

        is_duplicate = False
        for seen_company, seen_title, seen_location in seen_groups:
            company_score = fuzz.token_sort_ratio(norm_company, seen_company)
            title_score = fuzz.token_sort_ratio(norm_title, seen_title)

            # Location comparison is less strict
            location_match = (
                norm_location == seen_location
                or fuzz.ratio(norm_location, seen_location) > 80
                or not norm_location  # If location is empty, focus on company+title
                or not seen_location
            )

            # Both company AND title must be similar, plus location must match
            if (
                company_score >= FUZZY_MATCH_THRESHOLD
                and title_score >= FUZZY_MATCH_THRESHOLD
                and location_match
            ):
                is_duplicate = True
                break

        if not is_duplicate:
            keep_indices.append(idx)
            seen_groups.append((norm_company, norm_title, norm_location))

    df = df.loc[keep_indices].reset_index(drop=True)

    # ── Cleanup temporary columns ─────────────────────────────────
    df = df.drop(columns=["_norm_company", "_norm_title", "_norm_location", "_completeness"])

    fuzzy_dedup_count = original_count - url_dedup_count - len(df)
    total_removed = original_count - len(df)

    console.print(
        f"[green]🔄 Deduplication complete:[/] Removed {total_removed} duplicates "
        f"({url_dedup_count} exact URL + {fuzzy_dedup_count} fuzzy matches)"
    )
    console.print(f"   [dim]{original_count} → {len(df)} unique jobs[/]")

    return df


def _normalize_company(name: str) -> str:
    """
    Normalize a company name for comparison.
    - Lowercase
    - Strip common suffixes (Pvt Ltd, Inc, etc.)
    - Remove special characters
    """
    if not name or pd.isna(name):
        return ""

    name = str(name).strip().lower()

    # Remove common suffixes
    for suffix in COMPANY_SUFFIXES_TO_STRIP:
        # Use word boundary to avoid partial matches
        pattern = r"\b" + re.escape(suffix) + r"\b\.?"
        name = re.sub(pattern, "", name)

    # Remove special chars and extra whitespace
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name


def _normalize_title(title: str) -> str:
    """
    Normalize a job title for comparison.
    - Lowercase
    - Remove seniority prefixes (Sr., Jr., Lead, etc.)
    - Remove Roman numerals and level numbers
    """
    if not title or pd.isna(title):
        return ""

    title = str(title).strip().lower()

    # Remove seniority prefixes
    seniority_patterns = [
        r"\b(senior|sr\.?|junior|jr\.?|lead|principal|staff|chief)\b",
        r"\b(level|lvl)\s*[ivx0-9]+\b",
        r"\b[ivx]{1,4}\b",  # Roman numerals
        r"\b(i{1,3}|iv|v|vi{0,3})\b",
    ]
    for pat in seniority_patterns:
        title = re.sub(pat, "", title)

    # Remove special chars and extra whitespace
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()

    return title


def _calc_completeness(row) -> int:
    """
    Calculate a "completeness" score for a job listing.
    Higher score = more fields filled in.
    """
    score = 0
    important_fields = [
        "title", "company", "location", "salary", "description",
        "job_url", "date_posted", "job_type",
    ]

    for field in important_fields:
        val = row.get(field, "")
        if val and str(val).strip() not in ("", "nan", "N/A", "None"):
            score += 1

    # Bonus for having a description (most useful field)
    desc = row.get("description", "")
    if desc and len(str(desc)) > 100:
        score += 3

    return score
