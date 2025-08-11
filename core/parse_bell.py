
from __future__ import annotations
import re
import pandas as pd

WD_MAP = {
    "monday":"Mon","mon":"Mon",
    "tuesday":"Tue","tue":"Tue","tues":"Tue",
    "wednesday":"Wed","wed":"Wed",
    "thursday":"Thu","thu":"Thu","thurs":"Thu",
    "friday":"Fri","fri":"Fri",
}

TIME_RE = re.compile(r"(\b[0-1]?\d:[0-5]\d(?:\s?[APap][Mm])?\b)")

def parse_bell_text(text: str) -> tuple[dict, str | None]:
    times = {}
    early_release = None
    if re.search(r"early\s*release[^\.]*wednesday", text, re.I):
        early_release = "Wed"
    for line in re.split(r"[\n\r]+", text or ""):
        l = line.strip()
        if not l: 
            continue
        low = l.lower()
        for key, wd in WD_MAP.items():
            if key in low and wd not in times:
                m = TIME_RE.search(l)
                if m:
                    times[wd] = m.group(1).upper().replace(" ", "")
        if "dismiss" in low or "release" in low or "ends" in low:
            m = TIME_RE.search(l)
            if m:
                for wd in ["Mon","Tue","Thu","Fri"]:
                    times.setdefault(wd, m.group(1).upper().replace(" ", ""))
    def to_24h(s):
        try:
            dt = pd.to_datetime(s).time()
            return f"{dt.hour:02d}:{dt.minute:02d}"
        except Exception:
            return None
    out = {}
    for wd,t in times.items():
        v = to_24h(t)
        if v: out[wd]=v
    return out, early_release
