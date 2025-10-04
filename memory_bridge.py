# orion/core/memory_bridge.py
from __future__ import annotations
import re
from typing import List, Tuple, Optional

# Map common questions → memory keys → response template
QMAP: List[Tuple[str, str, str]] = [
    (r"\bwhat(?:'s| is)\s+my\s+name\b",            "user_name",      "Your name is {v}."),
    (r"\bwho\s+am\s+i\b",                          "user_name",      "You are {v}."),
    (r"\bwhere\s+(?:do\s+i\s+live|is\s+my\s+home)\b", "home_city",   "You live in {v}."),
    (r"\bwhat(?:'s| is)\s+my\s+role\b",            "role",           "Your role is {v}."),
    (r"\bwhat(?:'s| is)\s+my\s+favorite\s+color\b","favorite_color", "Your favorite color is {v}."),
    (r"\bwhat(?:'s| is)\s+my\s+coffee\s+order\b",  "coffee_order",   "Your coffee order is {v}."),
    (r"\bwhat(?:'s| is)\s+my\s+timezone\b",        "timezone",       "Your timezone is {v}."),
]

def memory_answer(mem, text: str) -> Optional[str]:
    """Try to directly answer a user question from memory facts."""
    s = (text or "").lower().strip()

    # Exact patterns first
    for rx, key, template in QMAP:
        if re.search(rx, s):
            val = mem.recall(key)
            return template.format(v=val) if val else f"I don't have your {key.replace('_',' ')} yet."

    # Generic form: "what is my X" → key "x" or "favorite_x"
    m = re.search(r"\bwhat(?:'s| is)\s+my\s+([a-z][a-z _-]{1,40})\??$", s)
    if m:
        key = m.group(1).strip().lower().replace("-", "_").replace(" ", "_")
        val = mem.recall(key) or mem.recall(f"favorite_{key}")
        if val:
            return f"Your {key.replace('_',' ')} is {val}."
        return f"I don't have your {key.replace('_',' ')} yet."

    return None

PREFERRED_FACT_KEYS = [
    "user_name","role","home_city","home_country",
    "weather_default","units","favorite_color","coffee_order","timezone"
]

def relevant_facts(mem, text: str, limit: int = 6) -> list[tuple[str,str]]:
    """Pick a handful of facts to help the LLM; naive keyword match, else preferred set."""
    all_facts = mem.facts_like("") or []
    if not all_facts:
        return []

    s = (text or "").lower()
    picks = [(k,v) for (k,v) in all_facts if any(w in s for w in k.lower().split("_"))]

    # If nothing matched the query terms, take preferred facts in order
    if not picks:
        for k in PREFERRED_FACT_KEYS:
            v = mem.recall(k)
            if v:
                picks.append((k,v))

    # Deduplicate & clamp
    out, seen = [], set()
    for k,v in picks:
        if k in seen:
            continue
        out.append((k,v))
        seen.add(k)
        if len(out) >= limit:
            break
    return out

def format_fact_context(facts: list[tuple[str,str]]) -> str:
    if not facts:
        return ""
    lines = [f"- {k.replace('_',' ').title()}: {v}" for (k,v) in facts]
    return "Known user facts:\n" + "\n".join(lines)