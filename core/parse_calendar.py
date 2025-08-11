
from __future__ import annotations
import re
import pandas as pd
from datetime import timedelta

MONTHS = "(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DAY = r"([0-3]?\d)"
YEAR = r"(20\d{2})"
SINGLE = re.compile(rf"{MONTHS}\s+{DAY},?\s*{YEAR}", re.I)
RANGE = re.compile(rf"{MONTHS}\s+{DAY}\s*[-–]\s*{DAY},?\s*{YEAR}", re.I)

def parse_calendar_text(text: str) -> list:
    dates = set()
    for m in RANGE.finditer(text or ""):
        mo, d1, d2, yr = m.group(1), m.group(2), m.group(3), m.group(4)
        try:
            start = pd.to_datetime(f"{mo} {d1}, {yr}").date()
            end = pd.to_datetime(f"{mo} {d2}, {yr}").date()
            cur = start
            while cur <= end:
                dates.add(cur)
                cur += timedelta(days=1)
        except Exception:
            continue
    for m in SINGLE.finditer(text or ""):
        mo, d1, yr = m.group(1), m.group(2), m.group(3)
        try:
            dates.add(pd.to_datetime(f"{mo} {d1}, {yr}").date())
        except Exception:
            continue
    return sorted(dates)
