
from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urlparse

UA = "Mozilla/5.0 (compatible; SchoolScheduleBot/1.0; +https://example.com/bot)"

def clean_text(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

def is_same_domain(url: str, base: str) -> bool:
    try:
        u1 = urlparse(url).netloc.lower()
        u2 = urlparse(base).netloc.lower()
        return u1 == u2 or (u1.endswith("."+u2) or u2.endswith("."+u1))
    except Exception:
        return False

def ts() -> str:
    return datetime.utcnow().isoformat()+"Z"
