# orion/skills/search.py
from __future__ import annotations
import re
import urllib.parse
from typing import List, Tuple
import requests
from bs4 import BeautifulSoup

NAME = "search"
DESCRIPTION = "DuckDuckGo HTML search with Wikipedia fallback."
TRIGGERS = [r"\b(search|look\s*up|lookup|find|query)\b"]


try:
    import wikipedia
except Exception:
    wikipedia = None  # optional

HEADERS = {
    "User-Agent": "Orion/1.0 (+https://example.local)",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 8
MAX_RESULTS = 5

DDG_HTML = "https://duckduckgo.com/html/"

def _unwrap_ddg_link(href: str) -> str:
    """
    DuckDuckGo often returns redirect links like:
      https://duckduckgo.com/l/?uddg=<urlencoded_target>
    Extract and return the real target when present.
    """
    if not href:
        return href
    try:
        parsed = urllib.parse.urlparse(href)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            q = urllib.parse.parse_qs(parsed.query)
            if "uddg" in q and q["uddg"]:
                return urllib.parse.unquote(q["uddg"][0])
    except Exception:
        pass
    return href

def ddg_search(q: str, n: int = MAX_RESULTS) -> List[Tuple[str, str]]:
    r = requests.get(DDG_HTML, params={"q": q}, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # DuckDuckGo may change classes; try multiple selectors
    anchors = soup.select("a.result__a") or soup.select("a.result__title") or []
    out: List[Tuple[str, str]] = []
    seen = set()
    for a in anchors:
        title = a.get_text(" ", strip=True)
        href = _unwrap_ddg_link(a.get("href"))
        if not title or not href:
            continue
        key = (title.lower(), href)
        if key in seen:
            continue
        seen.add(key)
        out.append((title, href))
        if len(out) >= n:
            break
    return out

def _clean_query(query: str) -> str:
    # remove leading triggers: search/find/look up/lookup
    return re.sub(r"^\s*(search|find|look\s*up|lookup)\s*[:\-]?\s*", "", query, flags=re.I).strip()

def run(query: str, context: dict) -> str:
    q = _clean_query(query)
    if not q:
        return "What should I search for?"

    # 1) DuckDuckGo HTML
    try:
        hits = ddg_search(q, n=MAX_RESULTS)
        if hits:
            return "Search results:\n" + "\n".join([f"• {t} — {u}" for t, u in hits])
    except Exception:
        # Fall through to Wikipedia
        pass

    # 2) Wikipedia summary fallback
    if wikipedia:
        try:
            # try with auto_suggest first for friendlier behavior
            try:
                summary = wikipedia.summary(q, sentences=2, auto_suggest=True)
                page = wikipedia.page(q, auto_suggest=True)
            except Exception:
                # then try strict mode
                summary = wikipedia.summary(q, sentences=2, auto_suggest=False)
                page = wikipedia.page(q, auto_suggest=False)
            return f"{summary}\nMore: {page.url}"
        except Exception:
            pass

    return f"Sorry, I couldn't find anything for: {q!r}."