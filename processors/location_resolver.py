"""
Location Resolver — Cross-references company names with their headquarters
locations using Wikipedia, Wikidata, and Google Search to resolve ambiguous
job listing locations.
"""

import json
import os
import re
import time
import requests
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from config import (
    WIKIPEDIA_API_URL,
    WIKIDATA_SPARQL_URL,
    VAGUE_LOCATIONS,
    CITY_ALIASES,
    COMPANY_CACHE_FILE,
    CACHE_DIR,
    REQUEST_DELAY_SECONDS,
)

console = Console()

# HTTP session for connection reuse
_session = requests.Session()
_session.headers.update({
    "User-Agent": "JobScrapper/1.0 (Python; educational project)",
    "Accept": "application/json",
})


class LocationResolver:
    """
    Resolves company office locations through multiple data sources
    and caches results locally.
    """

    def __init__(self):
        self.cache = self._load_cache()
        self._resolved_count = 0
        self._cache_hits = 0

    # ─── Public API ───────────────────────────────────────────────

    def enrich_jobs_with_location(
        self, df, target_location: str
    ):
        """
        For jobs with vague locations, cross-reference the company
        to determine if they have an office in the target location.

        Modifies the DataFrame in-place, adding:
          - location_status: "confirmed" | "inferred" | "unknown"
          - resolved_location: The resolved HQ/office city
        """
        import pandas as pd

        if df.empty:
            return df

        target_canonical = self._canonicalize_city(target_location)

        # Separate jobs into those with clear vs vague locations
        unique_companies = df["company"].unique()
        total_companies = len(unique_companies)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]🏢 Resolving company locations...",
                total=total_companies,
            )

            for company in unique_companies:
                mask = df["company"] == company
                company_rows = df.loc[mask]

                for idx in company_rows.index:
                    location_val = str(df.at[idx, "location"]).strip().lower()

                    if self._is_location_clear(location_val, target_canonical):
                        # Location already mentions the target city clearly
                        df.at[idx, "location_status"] = "confirmed"
                        df.at[idx, "resolved_location"] = target_location
                    elif self._is_vague_location(location_val):
                        # Vague location — try to resolve via company HQ
                        resolved = self.resolve_company_location(company)
                        if resolved:
                            df.at[idx, "resolved_location"] = resolved
                            resolved_canonical = self._canonicalize_city(resolved)
                            if resolved_canonical == target_canonical:
                                df.at[idx, "location_status"] = "inferred"
                            else:
                                df.at[idx, "location_status"] = "different_city"
                        else:
                            df.at[idx, "location_status"] = "unknown"
                    else:
                        # Has a specific location but it's not the target city
                        location_canonical = self._canonicalize_city(location_val)
                        if location_canonical == target_canonical:
                            df.at[idx, "location_status"] = "confirmed"
                            df.at[idx, "resolved_location"] = target_location
                        else:
                            df.at[idx, "location_status"] = "different_city"
                            df.at[idx, "resolved_location"] = location_val

                    # Add company intelligence if available in cache (now a dict)
                    cache_key = company.strip().lower()
                    if cache_key in self.cache:
                        cached = self.cache[cache_key]
                        if isinstance(cached, dict):
                            if "employees" in cached and cached["employees"]:
                                df.at[idx, "company_size"] = cached["employees"]
                            if "industry" in cached and cached["industry"]:
                                df.at[idx, "company_industry"] = cached["industry"]

                progress.advance(task)

            progress.update(
                task,
                description=(
                    f"[green]✓ Location resolved for {total_companies} companies "
                    f"({self._cache_hits} cache hits)"
                ),
            )

        # Save updated cache
        self._save_cache()

        # Print summary
        status_counts = df["location_status"].value_counts()
        console.print(f"  [green]Confirmed:[/] {status_counts.get('confirmed', 0)}")
        console.print(f"  [cyan]Inferred:[/] {status_counts.get('inferred', 0)}")
        console.print(f"  [yellow]Different city:[/] {status_counts.get('different_city', 0)}")
        console.print(f"  [red]Unknown:[/] {status_counts.get('unknown', 0)}")

        return df

    def resolve_company_location(self, company_name: str) -> str:
        """
        Resolve a company's HQ/office location using multiple sources.
        Returns the city name or empty string if resolution fails.
        """
        if not company_name or company_name.strip().lower() in ("n/a", "", "nan"):
            return ""

        clean_name = company_name.strip()

        # 1. Check cache
        cache_key = clean_name.lower()
        if cache_key in self.cache:
            self._cache_hits += 1
            cached = self.cache[cache_key]
            if isinstance(cached, dict):
                return cached.get("location", "")
            return cached

        # Prepare dict for new cache format
        company_info = {"location": "", "employees": "", "industry": ""}

        # 2. Try Wikipedia
        location = self._lookup_wikipedia(clean_name)
        if location:
            company_info["location"] = location
            self.cache[cache_key] = company_info
            self._resolved_count += 1
            return location

        time.sleep(0.5)

        # 3. Try Wikidata SPARQL
        wiki_info = self._lookup_wikidata_full(clean_name)
        if wiki_info and (wiki_info.get("location") or wiki_info.get("employees")):
            company_info.update(wiki_info)
            self.cache[cache_key] = company_info
            if company_info["location"]:
                self._resolved_count += 1
            return company_info["location"]

        time.sleep(0.5)

        # 4. Try Google search (scrape knowledge panel)
        location = self._lookup_google(clean_name)
        if location:
            company_info["location"] = location
            self.cache[cache_key] = company_info
            self._resolved_count += 1
            return location

        # Cache the miss too (so we don't retry)
        self.cache[cache_key] = company_info
        return ""

    # ─── Location Helpers ─────────────────────────────────────────

    def _is_vague_location(self, location: str) -> bool:
        """Check if a location string is vague/ambiguous."""
        loc_lower = location.strip().lower()
        return loc_lower in VAGUE_LOCATIONS or not loc_lower

    def _is_location_clear(self, location: str, target_canonical: str) -> bool:
        """Check if the location string clearly mentions the target city."""
        loc_canonical = self._canonicalize_city(location)
        if loc_canonical == target_canonical:
            return True

        # Also check if target city name appears as a substring
        target_lower = target_canonical.lower()
        if target_lower in location.lower():
            return True

        return False

    def _canonicalize_city(self, city_str: str) -> str:
        """
        Convert a city string to its canonical form using the alias map.
        e.g., "Bombay" → "mumbai", "Gurugram" → "delhi"
        """
        if not city_str:
            return ""

        # Extract the main city part (before comma, slash, or parentheses)
        city = re.split(r"[,/(\-]", city_str)[0].strip().lower()

        # Remove common suffixes
        city = re.sub(r"\s+(city|district|metro|area|region)$", "", city)

        # Check alias map
        if city in CITY_ALIASES:
            return CITY_ALIASES[city]

        return city

    # ─── Wikipedia Lookup ─────────────────────────────────────────

    def _lookup_wikipedia(self, company_name: str) -> str:
        """
        Look up company HQ from Wikipedia's REST API.
        Searches for the page summary and extract field.
        """
        try:
            # Try exact match first
            search_name = company_name.replace(" ", "_")
            url = WIKIPEDIA_API_URL.format(search_name)
            resp = _session.get(url, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")

                # Try to find headquarters mention in the extract
                location = self._extract_hq_from_text(extract)
                if location:
                    return location

            # Try with "(company)" suffix for disambiguation
            url = WIKIPEDIA_API_URL.format(f"{search_name}_(company)")
            resp = _session.get(url, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")
                location = self._extract_hq_from_text(extract)
                if location:
                    return location

        except requests.RequestException:
            pass

        return ""

    def _extract_hq_from_text(self, text: str) -> str:
        """Extract headquarters city from Wikipedia extract text."""
        if not text:
            return ""

        # Common patterns in Wikipedia extracts
        patterns = [
            r"headquartered\s+in\s+([A-Z][a-zA-Z\s]+?)(?:[,.])",
            r"headquarters?\s+(?:is\s+)?(?:in|at|located\s+in)\s+([A-Z][a-zA-Z\s]+?)(?:[,.])",
            r"based\s+in\s+([A-Z][a-zA-Z\s]+?)(?:[,.])",
            r"head\s+office\s+(?:is\s+)?(?:in|at)\s+([A-Z][a-zA-Z\s]+?)(?:[,.])",
            r"corporate\s+office\s+(?:is\s+)?(?:in|at)\s+([A-Z][a-zA-Z\s]+?)(?:[,.])",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                city = match.group(1).strip()
                # Clean up — remove trailing state/country names
                city = re.split(r",\s*", city)[0].strip()
                if len(city) > 2 and len(city) < 50:
                    return city

        return ""

    # ─── Wikidata SPARQL Lookup ───────────────────────────────────

    def _lookup_wikidata_full(self, company_name: str) -> dict:
        """
        Query Wikidata SPARQL to find the company's HQ city, employees, and industry.
        """
        query = """
        SELECT ?hqLabel ?employees ?industryLabel WHERE {
          ?company rdfs:label "%s"@en .
          OPTIONAL { ?company wdt:P159 ?hq . }
          OPTIONAL { ?company wdt:P1128 ?employees . }
          OPTIONAL { ?company wdt:P452 ?industry . }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
        }
        LIMIT 1
        """ % company_name.replace('"', '\\"')

        result = {"location": "", "employees": "", "industry": ""}
        try:
            resp = _session.get(
                WIKIDATA_SPARQL_URL,
                params={"query": query, "format": "json"},
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                bindings = data.get("results", {}).get("bindings", [])
                if bindings:
                    row = bindings[0]
                    result["location"] = row.get("hqLabel", {}).get("value", "")
                    result["employees"] = row.get("employees", {}).get("value", "")
                    result["industry"] = row.get("industryLabel", {}).get("value", "")
                    return result

        except requests.RequestException:
            pass

        return result

    # ─── Google Search Fallback ───────────────────────────────────

    def _lookup_google(self, company_name: str) -> str:
        """
        Search Google for the company's headquarters location.
        Parses the search results page for location info.
        """
        try:
            query = f"{company_name} headquarters location city"
            url = "https://www.google.com/search"

            resp = _session.get(
                url,
                params={"q": query},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                timeout=10,
            )

            if resp.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(resp.text, "html.parser")

                # Try to find the knowledge panel answer
                # Google often shows "Headquarters: <City>" in a special div
                for div in soup.find_all(["div", "span"]):
                    text = div.get_text()
                    if "headquarters" in text.lower():
                        location = self._extract_hq_from_text(text)
                        if location:
                            return location

                        # Try pattern: "Headquarters: City, State"
                        match = re.search(
                            r"[Hh]eadquarters?\s*[:\-]\s*([A-Z][a-zA-Z\s]+)",
                            text,
                        )
                        if match:
                            city = match.group(1).strip()
                            city = re.split(r",\s*", city)[0].strip()
                            if 2 < len(city) < 50:
                                return city

        except requests.RequestException:
            pass

        return ""

    # ─── Cache Management ─────────────────────────────────────────

    def _load_cache(self) -> dict:
        """Load the company→location cache from disk."""
        cache_path = Path(COMPANY_CACHE_FILE)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                console.print("[yellow]⚠ Cache file corrupted, starting fresh.[/]")
        return {}

    def _save_cache(self):
        """Save the company→location cache to disk."""
        cache_dir = Path(CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache_path = Path(COMPANY_CACHE_FILE)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except IOError as e:
            console.print(f"[yellow]⚠ Could not save cache: {e}[/]")

    def get_companies_in_location(self, target_location: str) -> list[str]:
        """
        Returns a list of company names from the cache that are
        known to be in the target location.
        """
        target_canonical = self._canonicalize_city(target_location)
        companies = []

        for company, cached in self.cache.items():
            location = cached.get("location", "") if isinstance(cached, dict) else cached
            if location:
                loc_canonical = self._canonicalize_city(location)
                if loc_canonical == target_canonical:
                    companies.append(company.title())

        return sorted(set(companies))
