# orion/core/router.py
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class SkillHit:
    name: str
    match: Optional[re.Match] = None  # optional match object, handy later

RULES = [
    # weather triggers
    ("weather", re.compile(r"\b(weather|forecast|temp(?:erature)?|rain|wind|snow|humidity|humid)\b", re.I)),

    # news triggers
    ("news", re.compile(r"\b(news|headline[s]?|top stor(?:y|ies)|breaking)\b", re.I)),

    # search triggers
    ("search", re.compile(r"\b(search|look\s*up|lookup|find|query)\b", re.I)),

    # memory
    ("remember", re.compile(r"^\s*remember\s*:", re.I)),
]

def route(text: str) -> Optional[SkillHit]:
    s = text or ""
    for name, rx in RULES:
        m = rx.search(s)
        if m:
            return SkillHit(name=name, match=m)
    return None