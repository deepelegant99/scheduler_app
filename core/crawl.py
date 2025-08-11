
from __future__ import annotations
import io, json, time, re, os
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from .utils import clean_text, is_same_domain, UA

def extract_pdf_text(content: bytes) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                pass
        return clean_text(" ".join(parts))
    except Exception:
        return ""

def get(url: str, timeout: int = 20) -> Optional[requests.Response]:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None

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
        href = a["href"]
        url = urljoin(base_url, href)
        if url.startswith("mailto:") or url.startswith("tel:"):
            continue
        anchors.append({
            "text": txt[:200],
            "title": title[:200],
            "aria": aria[:200],
            "href": url
        })
    return anchors

BELL_KWS = ["bell schedule","schedule","dismissal","school hours","hours","release"]
CAL_KWS  = ["calendar","academic calendar","important dates","school calendar"]

def score_anchor(a: Dict[str,str], base_url: str) -> Tuple[int,int]:
    score_bell = sum(1 for kw in BELL_KWS if kw in (a["text"]+" "+a["title"]+" "+a["aria"]))
    score_cal  = sum(1 for kw in CAL_KWS  if kw in (a["text"]+" "+a["title"]+" "+a["aria"]))
    same = 1 if is_same_domain(a["href"], base_url) else 0
    return (score_bell + same, score_cal + same)

def shortlist(anchors: List[Dict[str,str]], base_url: str, per_cat: int = 15) -> List[Dict[str,str]]:
    scored = []
    for a in anchors:
        sb, sc = score_anchor(a, base_url)
        if sb>0 or sc>0:
            scored.append((max(sb,sc), a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _,a in scored[:per_cat*2]]

def fetch_page_text(url: str) -> str:
    r = get(url)
    if not r:
        return ""
    ct = (r.headers.get("Content-Type") or "").lower()
    if ".pdf" in url.lower() or "application/pdf" in ct:
        return extract_pdf_text(r.content)
    return visible_text_from_html(r.text)

def pick_links_llm(candidates: List[Dict[str,str]], base_url: str, model: str = "gpt-4o-mini") -> Dict[str,Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return pick_links_heuristic(candidates, base_url)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        system = "You select 2 URLs (bell schedule and academic calendar) from the given anchors. Prefer same-domain. Return strict JSON."
        user = {
            "root_domain": urlparse(base_url).netloc,
            "anchors": candidates[:30]
        }
        msg = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},
                      {"role":"user","content":json.dumps(user)}],
            response_format={"type":"json_object"},
            temperature=0
        )
        content = msg.choices[0].message.content
        data = json.loads(content)
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
    bell = ""
    cal = ""
    bestb, bestc = -1, -1
    for a in candidates:
        sb, sc = score_anchor(a, base_url)
        if sb>bestb:
            bestb, bell = sb, a["href"]
        if sc>bestc:
            bestc, cal = sc, a["href"]
    return {
        "bell_schedule_url": bell or "NOT_FOUND",
        "calendar_url": cal or "NOT_FOUND",
        "confidence_bell": 0.4 if bell else 0.0,
        "confidence_calendar": 0.4 if cal else 0.0,
        "notes": "heuristic"
    }
