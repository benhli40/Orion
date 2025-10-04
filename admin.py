# orion/core/admin.py
import re
from core.context import Ctx, say
from core.plugins import load_skills, PluginRouter, list_all, set_enabled, scaffold

# Compile once
ADMIN_RELOAD_RE = re.compile(r"^(reload|reload it|reload now|refresh|refresh it|refresh now)[.!]?$", re.I)
LIST_SKILLS_RE = re.compile(r"^(list skills|show skills|what skills|skills\??)[.!]?$", re.I)
SKILL_CMD_RE   = re.compile(r"\bskills?\b[,\s:\-]+(.*)$", re.I)

MEM_LIST_RE = re.compile(r"^(list memory|show memory|dump memory|memory list)[.!]?$", re.I)
MEM_GET_RE  = re.compile(r"^memory get\s+([a-z0-9_ \-]{1,40})[.!]?$", re.I)
MEM_SET_RE  = re.compile(r"^memory set\s+([a-z0-9_ \-]{1,40})\s*=\s*(.+)$", re.I)

def reload_skills(ctx: Ctx) -> str:
    ctx.skills = load_skills()
    ctx.router = PluginRouter(ctx.skills)
    return f"Reloaded skills: {', '.join(ctx.skills.keys()) if ctx.skills else '(none)'}"

def handle_skill_admin(ctx: Ctx, low: str) -> bool:
    """Handle 'reload', 'list skills', and 'skills ...'. Return True if handled."""
    if ADMIN_RELOAD_RE.fullmatch(low):
        say(ctx, reload_skills(ctx)); return True

    if LIST_SKILLS_RE.fullmatch(low):
        rows = [f"• {n} [{'on' if en else 'off'}] — {desc}" for (n, en, desc) in list_all()]
        say(ctx, "Installed skills:\n" + ("\n".join(rows) if rows else "(none)"))
        return True

    m = SKILL_CMD_RE.search(low)
    if not m:
        return False

    cmd = m.group(1).strip()
    cmd = cmd.rstrip(".!,?")
    cmd = re.sub(r"\b(it|please|now|thanks?)\b$", "", cmd).strip()
    cmd = re.sub(r"^(gaffled|scaf|scafold)\b", "scaffold", cmd)

    if cmd == "list":
        rows = [f"• {n} [{'on' if en else 'off'}] — {desc}" for (n, en, desc) in list_all()]
        say(ctx, "Installed skills:\n" + ("\n".join(rows) if rows else "(none)")); return True

    if cmd == "reload":
        say(ctx, reload_skills(ctx)); return True

    if cmd.startswith("enable "):
        name = cmd.split(" ", 1)[1].strip()
        say(ctx, set_enabled(name, True)); return True

    if cmd.startswith("disable "):
        name = cmd.split(" ", 1)[1].strip()
        say(ctx, set_enabled(name, False)); return True

    if cmd.startswith("scaffold "):
        parts = cmd.split(" ", 1)
        if len(parts) == 1 or not parts[1].strip():
            say(ctx, "Usage: skill scaffold <name>")
        else:
            name = parts[1].strip()
            p = scaffold(name)
            say(ctx, f"Created {p.name}. Edit it, then say 'skill reload'.")
        return True

    say(ctx, "Usage: skill list | skill reload | skill enable <name> | skill disable <name> | skill scaffold <name>")
    return True

def handle_memory_admin(ctx: Ctx, low: str) -> bool:
    """Handle show/list/get/set memory. Return True if handled."""
    if MEM_LIST_RE.fullmatch(low):
        pairs = ctx.mem.facts_like("") or []
        if pairs:
            rows = [f"• {k.replace('_',' ').title()}: {v}" for k, v in sorted(pairs)]
            say(ctx, "Memory facts:\n" + "\n".join(rows[:50]))
        else:
            say(ctx, ("Your memory is empty. Try adding some:\n"
                      "  remember: user_name = Benjamin\n"
                      "  remember: favorite_color = navy\n"
                      "  remember: weather_default = Marble Falls, TX, US"))
        return True

    m = MEM_GET_RE.fullmatch(low)
    if m:
        key = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
        val = ctx.mem.recall(key) or ctx.mem.recall(f"favorite_{key}")
        say(ctx, f"{key.replace('_',' ').title()}: {val}" if val else f"No value saved for {key.replace('_',' ').title()}.")
        return True

    m = MEM_SET_RE.fullmatch(low)
    if m:
        key = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
        val = m.group(2).strip()
        ctx.mem.remember(key, val)
        say(ctx, f"Saved {key.replace('_',' ').title()}: {val}")
        return True

    return False