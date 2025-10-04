# orion/skills/registry.py
from __future__ import annotations

from typing import Callable, Dict, Any, Tuple
from . import weather, news, search

NAME = "registry"
DESCRIPTION = "Skill registry."
TRIGGERS = [r"\bregistry\b"]  # fixed: use single backslashes inside the raw string

# Skill functions take (query, context) and return a string
SkillFunc = Callable[[str, Dict[str, Any]], str]

_REGISTRY: Dict[str, SkillFunc] = {
    "weather": weather.run,
    "news": news.run,
    "search": search.run,
    # "remember" is handled inline below
}

def _parse_remember(rest: str) -> Tuple[str, str]:
    """
    Parse the text after 'remember:' into (key, value).
    Accepts:
      - 'topic = value'
      - 'topic value'
      - 'free text note' -> ('note', text)
    """
    s = (rest or "").strip()
    if not s:
        return ("note", "")
    if "=" in s:
        k, v = s.split("=", 1)
        return (k.strip() or "note", v.strip())
    parts = s.split()
    if len(parts) >= 2:
        return (parts[0].strip(), " ".join(parts[1:]).strip())
    return ("note", s)

def run(name: str, query: str, context: Dict[str, Any]) -> str:
    if name == "remember":
        if ":" not in query:
            return "Usage: remember: key = value  (or)  remember: some note"
        rest = query.split(":", 1)[1]
        key, val = _parse_remember(rest)

        mem = context.get("mem")
        if not mem:
            return "I couldn't access memory. (No 'mem' in context.)"

        if not val and key != "note":
            return "What should I store for that key? Try: remember: favorite_color = navy"

        mem.remember(key, val)
        return f"Got it. I’ll remember {key}: {val or '(empty)'}."

    fn = _REGISTRY.get(name)
    if not fn:
        raise ValueError(f"Unknown skill '{name}'")
    return fn(query, context)

def skills() -> Dict[str, str]:
    """Optional helper: advertise available skills (for help menus)."""
    return {
        "weather": "Weather/temperature/forecast queries",
        "news": "Top headlines (RSS, no API key)",
        "search": "DuckDuckGo HTML search with Wikipedia fallback",
        "remember": "Store facts: 'remember: key = value' or 'remember: some note'",
    }