# orion/core/wake.py
from __future__ import annotations
import os, re
from dataclasses import dataclass
from typing import List

def _to_terms(env_value: str, default: List[str]) -> List[str]:
    """
    Parse env like "wake_close|sleep|go to sleep" into a list. Empty -> default.
    """
    if not env_value:
        return default
    parts = [p.strip() for p in env_value.split("|")]
    return [p for p in parts if p]

@dataclass
class WakeWord:
    """
    Simple wake-word / sleep-word manager.

    Env overrides:
      WAKE_WORD      -> single word or short phrase, default "orion"
      WAKE_CLOSE     -> bar-separated phrases, default "wake_close|sleep|go to sleep|goodnight"
    """
    wake: str = os.getenv("WAKE_WORD", "orion")
    sleep_terms: List[str] = None

    def __post_init__(self):
        defaults = ["wake_close", "sleep", "go to sleep", "goodnight", "orion sleep"]
        self.sleep_terms = _to_terms(os.getenv("WAKE_CLOSE", ""), defaults)
        # Build regex for wake word w/ word boundaries, allow leading/trailing punctuation
        pat = r"\b" + re.escape(self.wake.lower()) + r"\b"
        self._wake_rx = re.compile(pat, re.I)
        # Precompile sleep regexes
        self._sleep_rx = [re.compile(r"\b" + re.escape(s.lower()) + r"\b", re.I) for s in self.sleep_terms]

    def heard_wake(self, text: str) -> bool:
        return bool(self._wake_rx.search(text or ""))

    def strip_wake(self, text: str) -> str:
        """
        Remove the first occurrence of the wake word and return the remainder.
        E.g., "Orion what's the weather?" -> "what's the weather?"
        """
        s = text or ""
        return self._wake_rx.sub("", s, count=1).strip(" ,.:;!?-—\t")

    def heard_sleep(self, text: str) -> bool:
        s = text or ""
        return any(rx.search(s) for rx in self._sleep_rx)