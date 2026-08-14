"""
ConsultBae Data Normalization Module
Handles all messy data cleaning, standardization, unit conversions,
and data quality edge cases across the three source datasets.
"""

import re
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

# Standardized canonical city mappings
CITY_MAPPINGS = {
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "pune": "Pune",
    "noida": "Noida",
    "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru",
    "delhi": "Delhi",
    "new delhi": "New Delhi",
    "delhi ncr": "Delhi NCR"
}

# Standard skill display casing dictionary
CANONICAL_SKILLS = {
    "n8n": "n8n",
    "langchain": "LangChain",
    "rest apis": "REST APIs",
    "rest api": "REST APIs",
    "mongodb": "MongoDB",
    "sql": "SQL",
    "mysql": "MySQL",
    "docker": "Docker",
    "zapier": "Zapier",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "react": "React",
    "selenium": "Selenium",
    "web scraping": "Web Scraping",
    "fastapi": "FastAPI",
    "python": "Python",
    "pandas": "Pandas"
}


def normalize_phone(phone_raw: Any) -> Optional[str]:
    """
    Standardizes any phone string to a clean 10-digit Indian mobile number.
    Handles formats: +919000000254, 9000000237, 09000000287, +91-9000000131, 919000000231.
    """
    if phone_raw is None:
        return None
    phone_str = str(phone_raw).strip()
    if not phone_str or phone_str.lower() in ("nan", "none", "null", ""):
        return None
    
    # Strip all non-digit characters
    digits = re.sub(r"\D", "", phone_str)
    
    # Handle country code prefixes and leading zeros
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    
    # Check if we have a valid 10-digit number
    if len(digits) == 10:
        return digits
    return digits if digits else None


def normalize_email(email_raw: Any) -> Optional[str]:
    """
    Standardizes email strings: lowers, strips whitespace.
    """
    if email_raw is None:
        return None
    email_str = str(email_raw).strip().lower()
    if not email_str or email_str in ("nan", "none", "null", ""):
        return None
    
    # Remove accidental surrounding quotes or trailing spaces
    email_str = email_str.strip("'\" \t\r\n")
    if "@" in email_str:
        return email_str
    return None


def normalize_name(name_raw: Any) -> Optional[str]:
    """
    Standardizes person full name: trims whitespace, normalizes casing to Title Case.
    """
    if name_raw is None:
        return None
    name_str = str(name_raw).strip()
    if not name_str or name_str.lower() in ("nan", "none", "null", ""):
        return None
    
    # Collapse multiple consecutive whitespace characters
    cleaned = re.sub(r"\s+", " ", name_str).strip()
    # Title-case for standard display
    return cleaned.title()


def get_name_match_key(name: str) -> str:
    """
    Generates a normalized comparison key for fuzzy/name resolution.
    e.g. 'Rohit Verma' -> 'rohit verma', 'R. Verma' -> 'r verma'.
    """
    if not name:
        return ""
    cleaned = re.sub(r"[^\w\s]", "", name.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_city(city_raw: Any) -> Optional[str]:
    """
    Standardizes city names to canonical representations.
    e.g. 'GURGAON', 'gurugram ', 'Gurgaon' -> 'Gurugram', 'pune' -> 'Pune'.
    """
    if city_raw is None:
        return None
    city_str = str(city_raw).strip()
    if not city_str or city_str.lower() in ("nan", "none", "null", ""):
        return None
    
    key = city_str.lower().strip()
    if key in CITY_MAPPINGS:
        return CITY_MAPPINGS[key]
    return city_str.title()


def normalize_ctc(ctc_raw: Any) -> Tuple[Optional[int], Optional[float], Optional[str]]:
    """
    Resolves the CTC unit mismatch problem:
    Some entries are in LPA (e.g. 4.2, 8.3, 11.2) while others are in direct INR (e.g. 417964, 1195422).
    
    Returns:
        (ctc_inr: int, ctc_lpa: float, formatted_display: str)
    """
    if ctc_raw is None:
        return None, None, None
    ctc_str = str(ctc_raw).strip()
    if not ctc_str or ctc_str.lower() in ("nan", "none", "null", ""):
        return None, None, None
    
    try:
        val = float(ctc_str)
        if val <= 0:
            return None, None, None
        
        if val < 100.0:
            # Value is in Lakhs Per Annum (LPA)
            ctc_lpa = round(val, 2)
            ctc_inr = int(round(val * 100000))
        else:
            # Value is already in full annual INR
            ctc_inr = int(round(val))
            ctc_lpa = round(ctc_inr / 100000.0, 2)
            
        formatted = f"₹{ctc_inr:,} ({ctc_lpa} LPA)"
        return ctc_inr, ctc_lpa, formatted
    except ValueError:
        return None, None, None


def normalize_date(date_raw: Any) -> Optional[str]:
    """
    Parses multi-format date strings into standard ISO YYYY-MM-DD.
    Handles:
      - 24-07-2026 (DD-MM-YYYY)
      - 2026-08-08 (YYYY-MM-DD)
      - 7 Jul 2026 / 19 Jul 2026 (D Mon YYYY)
      - 07/13/2026 (MM/DD/YYYY)
      - 08/19/2026, 07/03/2026, 21-08-2026
    """
    if date_raw is None:
        return None
    date_str = str(date_raw).strip()
    if not date_str or date_str.lower() in ("nan", "none", "null", ""):
        return None
    
    formats_to_try = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%b %d, %Y",
        "%d-%b-%Y"
    ]
    
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
            
    # Fallback regex if leading zero missing
    m = re.match(r"^(\d{1,2})[\s\-]+([A-Za-z]{3,9})[\s\-]+(\d{4})$", date_str)
    if m:
        try:
            day, month, year = m.groups()
            dt = datetime.strptime(f"{day} {month[:3]} {year}", "%d %b %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
            
    return None


def normalize_rate(rate_raw: Any) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Parses freelancer rates from diverse notations into structured hourly and monthly rates.
    Examples:
      - '1415/hr' -> hourly: 1415.0, monthly: ~226400 (based on 160 hrs), display: '₹1,415/hr'
      - '15k/month' -> hourly: ~93.75, monthly: 15000.0, display: '₹15,000/month'
      - '72k/month' -> hourly: ~450.0, monthly: 72000.0, display: '₹72,000/month'
    
    Returns:
        (hourly_rate: float, monthly_rate: float, formatted_display: str)
    """
    if rate_raw is None:
        return None, None, None
    rate_str = str(rate_raw).strip().lower()
    if not rate_str or rate_str in ("nan", "none", "null", ""):
        return None, None, None
    
    # 1. Hourly rate pattern (e.g. 1415/hr, 403 / hr, 1483/hour)
    hourly_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:/|\s+per\s+)?(?:hr|hour)$", rate_str)
    if hourly_match:
        hourly = float(hourly_match.group(1))
        # Standard full-time equivalent ~160 hours/month
        monthly = round(hourly * 160.0, 2)
        return hourly, monthly, f"₹{int(hourly):,}/hr"
        
    # 2. Monthly 'k' pattern (e.g. 15k/month, 72k / month)
    monthly_k_match = re.match(r"^(\d+(?:\.\d+)?)\s*k\s*(?:/|\s+per\s+)?(?:mo|month)$", rate_str)
    if monthly_k_match:
        val_k = float(monthly_k_match.group(1))
        monthly = val_k * 1000.0
        hourly = round(monthly / 160.0, 2)
        return hourly, monthly, f"₹{int(monthly):,}/month"
        
    # 3. Monthly flat pattern (e.g. 15000/month)
    monthly_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:/|\s+per\s+)?(?:mo|month)$", rate_str)
    if monthly_match:
        monthly = float(monthly_match.group(1))
        hourly = round(monthly / 160.0, 2)
        return hourly, monthly, f"₹{int(monthly):,}/month"
        
    return None, None, rate_str


def normalize_verified(verified_raw: Any) -> Optional[int]:
    """
    Standardizes varied boolean/status values into 1 (True) or 0 (False).
    'Y', 'yes', 'Yes', 'True', '1' -> 1
    'N', 'No', 'no', 'False', '0' -> 0
    """
    if verified_raw is None:
        return None
    val = str(verified_raw).strip().lower()
    if val in ("y", "yes", "true", "1", "verified"):
        return 1
    if val in ("n", "no", "false", "0", "unverified"):
        return 0
    return None


def normalize_status(status_raw: Any) -> Optional[str]:
    """
    Standardizes worker status: 'active', 'ACTIVE', 'paused', 'Inactive', 'Inactive' -> Title Case
    """
    if status_raw is None:
        return None
    status_str = str(status_raw).strip()
    if not status_str or status_str.lower() in ("nan", "none", "null", ""):
        return None
    return status_str.title()


def clean_skills(skills_raw: Any) -> List[str]:
    """
    Splits skill strings, trims, normalizes casing, and deduplicates.
    e.g. 'n8n, LangChain, REST APIs, MongoDB, SQL' -> ['FastAPI', 'LangChain', 'MongoDB', 'n8n', 'REST APIs', 'SQL']
    """
    if skills_raw is None:
        return []
    skills_str = str(skills_raw).strip()
    if not skills_str or skills_str.lower() in ("nan", "none", "null", ""):
        return []
    
    parts = [s.strip() for s in skills_str.split(",") if s.strip()]
    unique_skills = {}
    
    for p in parts:
        lower_key = p.lower()
        canonical = CANONICAL_SKILLS.get(lower_key, p.title())
        unique_skills[lower_key] = canonical
        
    return sorted(list(unique_skills.values()))


def merge_skills_lists(skills_list_a: List[str], skills_list_b: List[str]) -> List[str]:
    """
    Merges two skills lists and returns sorted canonical unique list.
    """
    combined = {}
    for s in skills_list_a + skills_list_b:
        if not s:
            continue
        lower_key = s.lower().strip()
        canonical = CANONICAL_SKILLS.get(lower_key, s.strip().title())
        combined[lower_key] = canonical
    return sorted(list(combined.values()))
