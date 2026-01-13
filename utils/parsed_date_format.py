import re
from datetime import datetime, timedelta

def parse_date_string(date_str: str) -> str:
    """
    Convert various date formats to YYYY-MM-DD format for yfinance.
    
    Handles:
    - "last year" -> one year ago
    - "2024-01-09" -> as is
    - "January 9, 2024" -> 2024-01-09
    - "1 month ago" -> date from 1 month ago
    - etc.
    """
    if not date_str:
        return None
    
    date_str = date_str.strip().lower()
    
    # If already in YYYY-MM-DD format, return as is
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    # Handle relative dates
    today = datetime.now()
    
    if 'last year' in date_str or '1 year ago' in date_str:
        target_date = today - timedelta(days=365)
        return target_date.strftime('%Y-%m-%d')
    
    if 'last month' in date_str or '1 month ago' in date_str:
        target_date = today - timedelta(days=30)
        return target_date.strftime('%Y-%m-%d')
    
    if 'last week' in date_str or '1 week ago' in date_str:
        target_date = today - timedelta(days=7)
        return target_date.strftime('%Y-%m-%d')
    
    if 'yesterday' in date_str:
        target_date = today - timedelta(days=1)
        return target_date.strftime('%Y-%m-%d')
    
    # Try to parse common date formats
    common_formats = [
        '%Y-%m-%d',      # 2024-01-09
        '%d-%m-%Y',      # 09-01-2024
        '%m/%d/%Y',      # 01/09/2024
        '%d/%m/%Y',      # 09/01/2024
        '%B %d, %Y',     # January 9, 2024
        '%b %d, %Y',     # Jan 9, 2024
        '%Y/%m/%d',      # 2024/01/09
    ]
    
    for fmt in common_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If nothing worked, return None
    return None