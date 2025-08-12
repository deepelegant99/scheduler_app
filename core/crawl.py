# core/crawl.py
from __future__ import annotations
import io, json, os
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# --- Real‑browser headers (avoid anti‑bot) ---
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
FIREFOX_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
)
COMMON_HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def with_www(url: str) -> str:
    p = urlparse(url)
    host = p.netloc
    if host and not host.startswith("www."):
        host = "www." + host
    return urlunparse((p.scheme or "https", host, p.path or "/", p.params, p.query, p.fragment))

def get(url: str, timeout: int = 20) -> Optional[requests.Response]:
    """
    Robust GET:
      - Real browser headers
      - Retries/backoff for 429/5xx
      - Fallback UA if 403/406
      - Try www. variant if first try fails
    Returns Response even if status != 200 (so caller can still parse body).
    """
    sess = _session()
    try:
        r = sess.get(url, headers=COMMON_HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code in (403, 406):
            alt_headers = dict(COMMON_HEADERS); alt_headers["User-Agent"] = FIREFOX_UA
            r = sess.get(url, headers=alt_headers, timeout=timeout, allow_redirects=True)
        if (r.status_code >= 400) and "://www." not in url:
            r2 = sess.get(with_www(url), headers=COMMON_HEADERS, timeout=timeout, allow_redirects=True)
            if r2.status_code < 400:
                return r2
        return r
    except Exception:
        return None

# --- HTML/PDF helpers ---
def clean_text(s: str | None) -> str:
    import re
    return re.sub(r"\s+", " ", s or "").strip()

def extract_pdf_text(content: bytes) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        parts = []
        for p in reader.pages:
            try:
                parts.append(p.extract_text() or "")
            except Exception:
                pass
        return clean_text(" ".join(parts))
    except Exception:
        return ""

def visible_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script","style","noscript","header","footer","nav","svg"]):
        tag.decompose()
    return clean_text(soup.get_text(" "))

def extract_anchors(html: str, base_url: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    anchors = []
    for a in soup.find_all("a", href=True):
        txt = clean_text(a.get_text(" ")).lower()
        title = clean_text(a.get("title", "")).lower()
        aria = clean_text(a.get("aria-label", "")).lower()
        url = urljoin(base_url, a["href"])
        if url.startswith(("mailto:", "tel:")):
            continue
        anchors.append({"text": txt[:200], "title": title[:200], "aria": aria[:200], "href": url})
    return anchors

BELL_KWS = ["bell schedule","schedule","dismissal","school hours","hours","release"]
CAL_KWS  = ["calendar","academic calendar","important dates","school calendar"]

def _same_domain(u: str, base: str) -> bool:
    try:
        n1 = urlparse(u).netloc.lower(); n2 = urlparse(base).netloc.lower()
        return n1 == n2 or n1.endswith("."+n2) or n2.endswith("."+n1)
    except Exception:
        return False

def _score_anchor(a: Dict[str,str], base_url: str) -> Tuple[int,int]:
    hay = (a["text"]+" "+a["title"]+" "+a["aria"])
    sb = sum(1 for kw in BELL_KWS if kw in hay)
    sc = sum(1 for kw in CAL_KWS if kw in hay)
    same = 1 if _same_domain(a["href"], base_url) else 0
    return (sb + same, sc + same)

def shortlist(anchors: List[Dict[str,str]], base_url: str, per_cat: int = 15) -> List[Dict[str,str]]:
    scored = []
    for a in anchors:
        sb, sc = _score_anchor(a, base_url)
        if sb>0 or sc>0:
            scored.append((max(sb,sc), a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _,a in scored[:per_cat*2]]

def fetch_page_text(url: str) -> str:
    r = get(url)
    if not r:
        return ""
    # Even a 403 page can contain HTML we can parse. Try anyway.
    ct = (r.headers.get("Content-Type") or "").lower()
    if ".pdf" in url.lower() or "application/pdf" in ct:
        return extract_pdf_text(r.content)
    return visible_text_from_html(r.text)

# ---- LLM link picker (optional) ----
def pick_links_llm(candidates: List[Dict[str,str]], base_url: str, model: str = "gpt-4o-mini") -> Dict[str,Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return pick_links_heuristic(candidates, base_url)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        system = "Pick one 'bell schedule' URL and one 'academic calendar' URL from the provided anchors. Prefer same-domain. Return strict JSON."
        user = {"root_domain": urlparse(base_url).netloc, "anchors": candidates[:30]}
        msg = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},{"role":"user","content":json.dumps(user)}],
            response_format={"type":"json_object"},
            temperature=0
        )
        data = json.loads(msg.choices[0].message.content)
        return {
            "bell_schedule_url": data.get("bell_schedule_url","NOT_FOUND"),
            "calendar_url": data.get("calendar_url","NOT_FOUND"),
            "confidence_bell": float(data.get("confidence_bell",0.0)),
            "confidence_calendar": float(data.get("confidence_calendar",0.0)),
            "notes": data.get("notes","")
        }
    except Exception:
        return pick_links_heuristic(candidates, base_url)

def pick_links_heuristic(candidates: List[Dict[str,str]], base_url: str) -> Dict[str,Any]:
    bell = ""; cal = ""; bestb = bestc = -1
    for a in candidates:
        sb, sc = _score_anchor(a, base_url)
        if sb>bestb: bestb, bell = sb, a["href"]
        if sc>bestc: bestc, cal = sc, a["href"]
    return {
        "bell_schedule_url": bell or "NOT_FOUND",
        "calendar_url": cal or "NOT_FOUND",
        "confidence_bell": 0.4 if bell else 0.0,
        "confidence_calendar": 0.4 if cal else 0.0,
        "notes": "heuristic"
    }
