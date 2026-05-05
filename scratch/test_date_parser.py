from processors.date_parser import parse_relative_date
from datetime import datetime

test_dates = [
    "2 hours ago",
    "1 day ago",
    "Just now",
    "30 minutes ago",
    "2026-05-01",
    "May 5, 2026",
    "Invalid date"
]

print(f"Current date: {datetime.now().strftime('%Y-%m-%d')}")
for d in test_dates:
    parsed = parse_relative_date(d)
    print(f"Original: {d:20} -> Parsed: {parsed}")
