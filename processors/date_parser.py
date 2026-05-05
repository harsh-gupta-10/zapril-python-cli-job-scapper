import re
from datetime import datetime, timedelta

def parse_relative_date(date_text: str) -> str:
    """
    Convert relative date strings like '2 hours ago', '3 days ago', 'today',
    'few hours ago', 'just now' into YYYY-MM-DD format.
    """
    if not date_text:
        return ""
        
    text = date_text.lower().strip()
    today = datetime.now()
    
    # Simple cases
    if any(phrase in text for phrase in ["today", "just now", "now", "0 days", "few hours", "moments"]):
        return today.strftime("%Y-%m-%d")
    
    if any(phrase in text for phrase in ["yesterday", "1 day ago", "a day ago"]):
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # Patterns for days, hours, minutes
    days_match = re.search(r"(\d+)\s*day", text)
    if days_match:
        return (today - timedelta(days=int(days_match.group(1)))).strftime("%Y-%m-%d")
        
    hours_match = re.search(r"(\d+)\s*hour", text)
    if hours_match:
        return today.strftime("%Y-%m-%d")
        
    mins_match = re.search(r"(\d+)\s*min", text)
    if mins_match:
        return today.strftime("%Y-%m-%d")
        
    weeks_match = re.search(r"(\d+)\s*week", text)
    if weeks_match:
        return (today - timedelta(weeks=int(weeks_match.group(1)))).strftime("%Y-%m-%d")
        
    months_match = re.search(r"(\d+)\s*month", text)
    if months_match:
        return (today - timedelta(days=int(months_match.group(1)) * 30)).strftime("%Y-%m-%d")

    # Try parsing as ISO date or other common formats
    try:
        # Remove timezone info for simplicity or handle Z
        clean_date = date_text.split('+')[0].split('Z')[0]
        # Common formats including those with month names
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%b %d, %Y", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(clean_date, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    except Exception:
        pass
        
    return date_text # Return as is if nothing matched
