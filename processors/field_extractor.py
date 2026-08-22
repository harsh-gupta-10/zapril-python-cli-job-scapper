"""
Helpers for extracting normalized job fields from raw text/source payloads.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from processors.date_parser import parse_relative_date


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

_EXP_RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs?)",
    re.IGNORECASE,
)
_EXP_PLUS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)", re.IGNORECASE)
_EXP_SINGLE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", re.IGNORECASE)
_EXP_FRESHER_RE = re.compile(r"\b(fresher|entry[\s-]?level|no experience)\b", re.IGNORECASE)

_SALARY_RE = re.compile(
    r"(₹|\$|INR|USD)\s*[\d,]+(?:\.\d+)?(?:\s*(?:-|to)\s*(?:₹|\$|INR|USD)?\s*[\d,]+(?:\.\d+)?)?"
    r"(?:\s*(?:LPA|PA|PM|per annum|per month|annum|month))?",
    re.IGNORECASE,
)
_SALARY_LPA_RE = re.compile(
    r"[\d,.]+\s*(?:-|to)\s*[\d,.]+\s*LPA|[\d,.]+\s*LPA",
    re.IGNORECASE,
)


def normalize_text(value) -> str:
    """Return a clean one-line string representation."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "n/a"}:
        return ""
    return _SPACE_RE.sub(" ", text).strip()


def clean_html_text(value) -> str:
    """Strip HTML tags and compact whitespace."""
    text = normalize_text(value)
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def normalize_date_posted(value) -> str:
    """Normalize a date-like value into YYYY-MM-DD when possible."""
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    text = normalize_text(value)
    if not text:
        return ""

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text

    epoch_match = re.fullmatch(r"\d{10,13}", text)
    if epoch_match:
        try:
            ts = int(text)
            if len(text) == 13:
                ts //= 1000
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return ""

    # Handle ISO-like strings before relative parser.
    try:
        iso_value = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(iso_value)
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    normalized = parse_relative_date(text)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        return normalized
    return normalized if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized) else ""


def extract_work_experience(*values) -> str:
    """Extract a compact work-experience value from one or more text inputs."""
    for value in values:
        text = normalize_text(value)
        if not text:
            continue

        if _EXP_FRESHER_RE.search(text):
            return "0 years"

        match = _EXP_RANGE_RE.search(text)
        if match:
            return f"{match.group(1)}-{match.group(2)} years"

        match = _EXP_PLUS_RE.search(text)
        if match:
            return f"{match.group(1)}+ years"

        match = _EXP_SINGLE_RE.search(text)
        if match:
            return f"{match.group(1)} years"

    return ""


def extract_salary_text(*values) -> str:
    """Extract salary text from known salary fields or unstructured text."""
    for value in values:
        text = normalize_text(value)
        if not text:
            continue

        salary_match = _SALARY_RE.search(text)
        if salary_match:
            return normalize_text(salary_match.group(0))

        lpa_match = _SALARY_LPA_RE.search(text)
        if lpa_match:
            return normalize_text(lpa_match.group(0))

    return ""
