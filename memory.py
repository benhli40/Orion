# orion/core/memory.py
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

MAX_CONVERSATIONS = 500  # cap growth so the file doesn't balloon

class Memory:
    def __init__(self, base_dir: Path):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self.mem_path = self.base / "memory.json"
        if not self.mem_path.exists():
            self._safe_write({"facts": {}, "conversations": []})
        else:
            # If the file is corrupted, reset it instead of crashing.
            try:
                _ = self._read()
            except Exception:
                self._safe_write({"facts": {}, "conversations": []})

    def _read(self) -> Dict[str, Any]:
        text = self.mem_path.read_text(encoding="utf-8")
        return json.loads(text) if text.strip() else {"facts": {}, "conversations": []}

    def _safe_write(self, obj: Dict[str, Any]):
        tmp = self.mem_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.mem_path)  # atomic on most platforms

    # Long-term facts (self-learn)
    def remember(self, key: str, value: str):
        data = self._read()
        data.setdefault("facts", {})[key] = value
        self._safe_write(data)

    def recall(self, key: str) -> Optional[str]:
        return self._read().get("facts", {}).get(key)

    def facts_like(self, needle: str) -> List[tuple]:
        needle = (needle or "").lower()
        items = self._read().get("facts", {}).items()
        return [(k, v) for k, v in items if needle in k.lower() or needle in v.lower()]

    # Conversation log
    def append_conversation(self, user: Optional[str] = None, bot: Optional[str] = None):
        data = self._read()
        entry: Dict[str, Any] = {}
        if user is not None:
            entry["user"] = user
        if bot is not None:
            entry["bot"] = bot
        if entry:
            conv = data.setdefault("conversations", [])
            conv.append(entry)
            # Trim to max size
            if len(conv) > MAX_CONVERSATIONS:
                conv[:] = conv[-MAX_CONVERSATIONS:]
            self._safe_write(data)

    # Convenience
    def recent(self, n: int = 5) -> List[Dict[str, Any]]:
        """Return the last n conversation turns (best-effort)."""
        return self._read().get("conversations", [])[-n:]

    def dump(self) -> Dict[str, Any]:
        """Return the full memory dict (debug/export)."""
        return self._read()