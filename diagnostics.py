# orion/core/diagnostics.py
from __future__ import annotations
import importlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional

@dataclass
class DiagResult:
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def line(self, s: str): self.notes.append(s)
    def warn(self, s: str): self.warnings.append(s)
    def fix(self, s: str): self.fixes.append(s)
    def err(self, s: str): self.errors.append(s)

    def render(self) -> str:
        out = []
        if self.errors:   out.append("❌ Errors:\n- " + "\n- ".join(self.errors))
        if self.warnings: out.append("⚠️  Warnings:\n- " + "\n- ".join(self.warnings))
        if self.fixes:    out.append("🛠  Applied fixes:\n- " + "\n- ".join(self.fixes))
        if self.notes:    out.append("ℹ️  Notes:\n- " + "\n- ".join(self.notes))
        return "\n\n".join(out) if out else "All checks passed."

ROOT = Path(__file__).resolve().parents[1]  # orion/
CORE = ROOT / "core"
SKILLS = ROOT / "skills"
STATE = SKILLS / "_enabled.json"

# Directories to skip when scanning for .py files
SKIP_DIRS = {
    ".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "venv", ".venv", "env", ".env", "node_modules", "build", "dist"
}

# ------- utils -------
def _safe_write(path: Path, text: str):
    bak = path.with_suffix(path.suffix + ".bak")
    try:
        if path.exists():
            bak.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    except Exception:
        # if even backup read fails, ignore — we’ll still write the new file
        pass
    path.write_text(text, encoding="utf-8")

def _iter_py_files(base: Path):
    for p in base.rglob("*.py"):
        parts = set(p.parts)
        if parts & SKIP_DIRS:
            continue
        # Also avoid hidden folders anywhere in the path
        if any(seg.startswith(".") and seg not in {".", ".."} for seg in p.parts):
            continue
        yield p

def _read_text_utf8(path: Path) -> str:
    # strict utf-8 read (for syntax/fix operations). Raise on decode error.
    return path.read_text(encoding="utf-8")

def _try_read_utf8(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None

# ------- checks/fixes -------
def check_env(settings, r: DiagResult):
    missing = []
    if not settings.GEMINI_API_KEY:      missing.append("GEMINI_API_KEY")
    if not settings.ELEVENLABS_API_KEY:  missing.append("ELEVENLABS_API_KEY")
    if not settings.OPENWEATHER_API_KEY:
        r.warn("OPENWEATHER_API_KEY missing (weather skill will fail).")
    if missing:
        r.err("Missing env keys: " + ", ".join(missing))
    else:
        r.line("Environment keys present.")

def check_requirements(r: DiagResult):
    req = ROOT / "requirements.txt"
    if not req.exists():
        r.warn("requirements.txt not found.")
        return
    try:
        want = req.read_text(encoding="utf-8", errors="ignore").lower()
        needed = ["google-genai", "realtimestt", "elevenlabs", "feedparser", "requests", "beautifulsoup4"]
        for pkg in needed:
            if pkg not in want:
                r.warn(f"{pkg} not listed in requirements.txt")
    except Exception as e:
        r.warn(f"Could not read requirements.txt: {e}")

def check_syntax(r: DiagResult):
    bad = []
    skipped = 0
    for p in _iter_py_files(ROOT):
        src = _try_read_utf8(p)
        if src is None:
            skipped += 1
            r.warn(f"Non-UTF8 source skipped: {p}")
            continue
        try:
            compile(src, str(p), "exec")
        except SyntaxError as e:
            bad.append((p, f"{e.msg} at line {e.lineno}"))
    if bad:
        for p,msg in bad: r.err(f"Syntax error in {p}: {msg}")
    else:
        r.line("Python syntax OK in project.")
    if skipped:
        r.line(f"Skipped {skipped} non-UTF8 file(s).")

COMMON_FIXES: List[Tuple[re.Pattern,str]] = [
    (re.compile(r"My name is\b"), "My name is"),
    (re.compile(r"model_id\s*=\s*[\"']elevenlabs_flash_v2_5[\"']"), "model_id=\"eleven_flash_v2_5\""),
    (re.compile(r"from\s+elevenlabs\s+import\s+play"), "from elevenlabs.play import play"),
]

def fix_common_strings(r: DiagResult, apply: bool):
    for p in _iter_py_files(ROOT):
        src = _try_read_utf8(p)
        if src is None:
            r.warn(f"Skipped (non-UTF8): {p}")
            continue
        new = src
        for pat, rep in COMMON_FIXES:
            new = pat.sub(rep, new)
        if new != src:
            if apply:
                _safe_write(p, new)
                r.fix(f"Applied common string fixes in {p}")
            else:
                r.warn(f"Would fix strings in {p} (run diagnostics fix to apply)")

def ensure_skill_headers(r: DiagResult, apply: bool):
    if not SKILLS.exists():
        r.warn("skills/ directory not found.")
        return
    for p in SKILLS.glob("*.py"):
        if p.name.startswith("_") or p.stem == "__init__":
            continue
        src = _try_read_utf8(p)
        if src is None:
            r.warn(f"Skipped header check (non-UTF8): {p}")
            continue
        has_name = re.search(r"^NAME\s*=\s*['\"]", src, re.M)
        has_desc = re.search(r"^DESCRIPTION\s*=\s*['\"]", src, re.M)
        has_trig = re.search(r"^TRIGGERS\s*=\s*\[", src, re.M)
        if has_name and has_desc and has_trig:
            continue
        head = []
        if not has_name: head.append(f'NAME = "{p.stem}"')
        if not has_desc: head.append(f'DESCRIPTION = "Skill {p.stem}."')
        if not has_trig: head.append(f'TRIGGERS = [r"\\\\b{p.stem}\\\\b"]')
        insertion = "\n".join(head) + "\n"
        if apply:
            _safe_write(p, insertion + src)
            r.fix(f"Inserted skill headers in {p.name}")
        else:
            r.warn(f"Missing headers in {p.name} (would insert)")

def ensure_enabled_json(r: DiagResult, apply: bool):
    discovered = [p.stem for p in SKILLS.glob("*.py") if not p.name.startswith("_") and p.stem != "__init__"]
    current: Dict[str,bool] = {}
    if STATE.exists():
        try:
            current = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            if apply:
                _safe_write(STATE, json.dumps({}, indent=2))
                r.fix("_enabled.json corrupted; reset.")
            else:
                r.warn("_enabled.json corrupted (would reset)")
    missing_keys = [n for n in discovered if n not in current]
    if missing_keys:
        for k in missing_keys:
            current[k] = True
        if apply:
            _safe_write(STATE, json.dumps(current, indent=2))
            r.fix(f"Added {len(missing_keys)} skills to _enabled.json")
        else:
            r.warn(f"{len(missing_keys)} skills missing in _enabled.json (would add)")

def check_memory_health(r: DiagResult, apply: bool):
    mem = (Path.home() / ".orion" / "memory.json")
    if not mem.exists():
        r.line("memory.json not present yet (will be created on first run).")
        return
    try:
        _ = json.loads(mem.read_text(encoding="utf-8"))
        r.line("memory.json OK.")
    except Exception:
        if apply:
            _safe_write(mem, json.dumps({"facts": {}, "conversations": []}, indent=2))
            r.fix("memory.json was corrupted; reset to empty.")
        else:
            r.warn("memory.json corrupted (would reset).")

def check_imports(r: DiagResult):
    mods = ["core.config","core.llm","core.voice","core.memory","core.router","core.wake","core.plugins"]
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:
            r.err(f"Import failed: {m}: {e}")
    r.line("Core imports OK.")

def preflight_apis(settings, r: DiagResult):
    # Gemini
    try:
        from google import genai
        from google.genai import types
        g = genai.Client(api_key=settings.GEMINI_API_KEY)
        chat = g.chats.create(model="gemini-2.5-flash", config=types.GenerateContentConfig(max_output_tokens=8))
        resp = chat.send_message("ping")
        if not getattr(resp, "text", ""):
            r.warn("Gemini responded with empty text.")
        else:
            r.line("Gemini preflight OK.")
    except Exception as e:
        r.warn(f"Gemini preflight issue: {e}")

    # ElevenLabs (presence only; avoids voices_read list call)
    try:
        from elevenlabs.client import ElevenLabs
        if settings.ELEVENLABS_API_KEY:
            _ = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
            r.line("ElevenLabs key present (TTS exercised at runtime).")
        else:
            r.warn("ElevenLabs key missing.")
    except Exception as e:
        r.warn(f"ElevenLabs preflight issue: {e}")

def run_diagnostics(settings, apply: bool = False, deep: bool = False) -> str:
    r = DiagResult()
    check_env(settings, r)
    check_requirements(r)
    check_syntax(r)
    fix_common_strings(r, apply)
    ensure_skill_headers(r, apply)
    ensure_enabled_json(r, apply)
    check_memory_health(r, apply)
    check_imports(r)
    if deep:
        preflight_apis(settings, r)
    return r.render()