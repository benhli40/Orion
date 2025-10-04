# orion/core/plugins.py
from __future__ import annotations
import importlib, json, re, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
STATE_PATH = SKILLS_DIR / "_enabled.json"  # which skills are enabled

@dataclass
class LoadedSkill:
    name: str
    run: Callable[[str, dict], str]
    patterns: List[re.Pattern]
    description: str

def _read_state() -> Dict[str, bool]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}  # empty means: default enable everything found

def _write_state(state: Dict[str, bool]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

def _is_enabled(name: str, state: Dict[str, bool]) -> bool:
    # default to enabled unless explicitly false
    return state.get(name, True)

def _iter_skill_modules() -> List[str]:
    """Return module names under 'skills.' (skip dunders, registry, __init__)."""
    mods = []
    for p in SKILLS_DIR.glob("*.py"):
        stem = p.stem
        if stem.startswith("_") or stem in {"__init__", "registry"}:
            continue
        mods.append(f"skills.{stem}")
    return mods

def _compile_triggers(triggers: List[str]) -> List[re.Pattern]:
    out = []
    for t in triggers or []:
        try:
            out.append(re.compile(t, re.I))
        except re.error:
            pass
    return out

def _load_one(modname: str) -> Optional[LoadedSkill]:
    try:
        mod = importlib.import_module(modname)
    except Exception:
        return None
    run = getattr(mod, "run", None)
    if not callable(run):
        return None
    name = getattr(mod, "NAME", modname.split(".")[-1])
    triggers = getattr(mod, "TRIGGERS", [])
    desc = getattr(mod, "DESCRIPTION", f"{name} skill")
    return LoadedSkill(
        name=name,
        run=run,
        patterns=_compile_triggers(triggers),
        description=str(desc),
    )

def load_skills() -> Dict[str, LoadedSkill]:
    """Import all skills/*.py and return enabled ones as a dict by name."""
    sys.path.insert(0, str(SKILLS_DIR.parent))  # ensure 'skills' is importable
    state = _read_state()
    result: Dict[str, LoadedSkill] = {}
    for modname in _iter_skill_modules():
        sk = _load_one(modname)
        if not sk:
            continue
        if not _is_enabled(sk.name, state):
            continue
        result[sk.name] = sk
    return result

def list_all() -> List[Tuple[str, bool, str]]:
    """(name, enabled, description) for each discovered skill."""
    state = _read_state()
    out = []
    for modname in _iter_skill_modules():
        sk = _load_one(modname)
        if not sk:
            continue
        out.append((sk.name, _is_enabled(sk.name, state), sk.description))
    return out

def set_enabled(name: str, enabled: bool) -> str:
    state = _read_state()
    state[name] = bool(enabled)
    _write_state(state)
    return f"{'Enabled' if enabled else 'Disabled'} skill '{name}'. Say 'skill reload' to apply."

class PluginRouter:
    """Routes text to the first matching skill trigger (if any)."""
    def __init__(self, skills: Dict[str, LoadedSkill]):
        self.skills = skills
        # build flat rule list [(name, pattern)]
        self.rules: List[Tuple[str, re.Pattern]] = []
        for name, sk in skills.items():
            for pat in sk.patterns:
                self.rules.append((name, pat))

    def route(self, text: str) -> Optional[LoadedSkill]:
        s = text or ""
        for name, pat in self.rules:
            if pat.search(s):
                return self.skills.get(name)
        return None

def scaffold(name: str) -> Path:
    """
    Create a new skill file skills/<name>.py with a minimal template.
    Returns the created path.
    """
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
    path = SKILLS_DIR / f"{safe}.py"
    if path.exists():
        return path
    template = f'''# skills/{safe}.py
NAME = "{safe}"
DESCRIPTION = "Describe what {safe} does."
TRIGGERS = [r"\\\\b{safe}\\\\b"]  # adjust as needed

def run(query: str, context: dict) -> str:
    # implement your logic here
    return "Hello from {safe}!"
'''
    path.write_text(template, encoding="utf-8")
    return path