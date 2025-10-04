# orion/skills/news.py
from __future__ import annotations
import time
import re
from typing import List, Tuple
import requests
import feedparser

NAME = "news"
DESCRIPTION = "Top headlines via RSS (no API key)."
TRIGGERS = [r"\b(news|headline[s]?|top stor(?:y|ies)|breaking)\b"]


FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.npr.org/rss/rss.php?id=1001",
    "https://apnews.com/hub/ap-top-news?output=rss",
]

HEADERS = {"User-Agent": "Orion/1.0 (+https://example.local)"}
TIMEOUT = 8  # seconds
MAX_ITEMS = 9
PER_FEED = 4  # pull a few per feed, then trim/dedupe to MAX_ITEMS

def _keywords_from_query(q: str) -> List[str]:
    if not q:
        return []
    # strip leading trigger words like "news", "headlines", "top stories", "about"
    s = re.sub(r"^\s*(news|headline[s]?|top stor(?:y|ies)|about)\s*[:\-]?\s*", "", q, flags=re.I).strip()
    # split on whitespace; keep words >=3 chars (very small heuristic)
    words = [w for w in re.findall(r"[A-Za-z0-9\-]+", s) if len(w) >= 3]
    return [w.lower() for w in words]

def _fetch_feed(url: str):
    # requests → pass bytes to feedparser so we control timeout/headers
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return feedparser.parse(r.content)

def _fmt_time(entry) -> str:
    # prefer published_parsed, fallback to updated_parsed
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return ""
    # format as e.g., "Oct 4, 2025"
    return time.strftime("%b %d, %Y", t)

def _entry_text(entry) -> str:
    title = getattr(entry, "title", "") or ""
    summ = getattr(entry, "summary", "") or ""
    return f"{title} {summ}".lower()

def _match_keywords(entry, kws: List[str]) -> bool:
    if not kws:
        return True
    blob = _entry_text(entry)
    return all(k in blob for k in kws)

def run(query: str, context: dict) -> str:
    kws = _keywords_from_query(query)
    seen_titles = set()
    seen_links = set()
    items: List[Tuple[str, str, str]] = []  # (title, link, date_str)

    for url in FEEDS:
        try:
            feed = _fetch_feed(url)
        except Exception:
            continue

        count = 0
        for e in getattr(feed, "entries", []):
            if count >= PER_FEED:
                break
            title = (getattr(e, "title", "") or "").strip()
            link = (getattr(e, "link", "") or "").strip()
            if not title or not link:
                continue
            if not _match_keywords(e, kws):
                continue
            # dedupe on title/link
            key_title = title.lower()
            if key_title in seen_titles or link in seen_links:
                continue

            date_str = _fmt_time(e)
            items.append((title, link, date_str))
            seen_titles.add(key_title)
            seen_links.add(link)
            count += 1

        if len(items) >= MAX_ITEMS:
            break

    if not items:
        if kws:
            return f"Sorry, I couldn't find headlines for: {', '.join(kws)}."
        return "Sorry, I couldn't fetch headlines right now."

    # Trim and format
    items = items[:MAX_ITEMS]
    lines = []
    for title, link, date_str in items:
        if date_str:
            lines.append(f"• {title} ({date_str}) — {link}")
        else:
            lines.append(f"• {title} — {link}")

    header = "Top headlines" if not kws else f"Top headlines on: {', '.join(kws)}"
    return header + ":\n" + "\n".join(lines)