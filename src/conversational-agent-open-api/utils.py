import logging
import re

from dateutil import parser as dateutil_parser

# ---------------------------------------------------------
# Date extraction and parsing
# ---------------------------------------------------------
def extract_and_parse_date(query: str):
    """
    Extract dates from query string and parse them.
    Returns a tuple (start_date, end_date) in YYYYMMDD format, or (None, None) if no date found.

    Supports formats like:
    - "May 20, 2026"
    - "May 20"
    - "2026-05-20"
    - "05/20/2026"
    - "20260520"
    - "May 2026"
    - "2026"
    """
    # Pattern for common date formats
    # This is a basic pattern; dateutil_parser will handle most cases
    date_patterns = [
        r'\b\d{8}\b',  # YYYYMMDD
        r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # MM/DD/YYYY or M/D/YYYY
        r'\b\d{1,2}/\d{1,2}/\d{2}\b',  # MM/DD/YY
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:,?\s+\d{4})?\b',  # Month DD or Month DD, YYYY
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b',  # Month YYYY
        r'\b\d{4}\b',  # YYYY
    ]

    for pattern in date_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            date_str = match.group(0)
            try:
                # Try to parse the date string
                parsed_date = dateutil_parser.parse(date_str, fuzzy=True)
                date_yyyymmdd = parsed_date.strftime("%Y%m%d")
                logging.info(f"Extracted date '{date_str}' → {date_yyyymmdd}")
                return date_yyyymmdd, date_yyyymmdd
            except Exception as e:
                logging.debug(f"Failed to parse date '{date_str}': {e}")
                continue

    return None, None