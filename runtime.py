# orion/core/runtime.py
import json, os, re, threading
from typing import Optional
from dotenv import load_dotenv, find_dotenv

from core.config import settings
from core.llm import LLM
from core.voice import TTS, resolve_voice_id, make_recorder
from core.memory import Memory
from core.router import route as legacy_route
from core.wake import WakeWord
from core.plugins import load_skills, PluginRouter
from core.context import Ctx, say
from core.admin import handle_skill_admin, handle_memory_admin
from core.llm_path import llm_respond
from core.memory_bridge import memory_answer

# Defaults (you can export these to a constants file if you prefer)
MAX_OUTPUT_TOKENS = 50
MIC_TIMEOUT = 10

def clear_screen():
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        print("\033[2J\033[H", end="")

def mic_text(recorder, timeout=MIC_TIMEOUT) -> Optional[str]:
    box = {"text": None, "err": None}
    def worker():
        try:
            box["text"] = recorder.text()
        except Exception as e:
            box["err"] = e
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None
    if box["err"]:
        raise box["err"]
    return (box["text"] or "").strip()

def print_memory_summary(mem: Memory):
    try:
        data = json.loads(mem.mem_path.read_text(encoding="utf-8"))
        n = len(data.get("facts", {}))
    except Exception:
        n = 0
    print(f"[Memory] path: {mem.mem_path} ({n} fact{'s' if n != 1 else ''})")

def boot() -> Optional[Ctx]:
    # Ensure env is loaded if someone calls boot() alone
    load_dotenv(find_dotenv(), override=True)
    print("Orion booting...\n")

    llm = LLM(
        api_key=settings.GEMINI_API_KEY,
        system_instruction=settings.SYSTEM_INSTRUCTION,
        model="gemini-2.5-flash",
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    tts = TTS(api_key=settings.ELEVENLABS_API_KEY)

    pref_voice = os.getenv("ELEVEN_VOICE_ID") or os.getenv("ELEVEN_VOICE_NAME")
    try:
        voice_id = resolve_voice_id(tts.client, pref_voice)
    except Exception as e:
        print(f"[TTS setup] {e}\nTip: set ELEVEN_VOICE_ID in your .env to a valid voice id from your ElevenLabs dashboard.")
        return None

    mem = Memory(base_dir=settings.DATA_DIR)
    print_memory_summary(mem)

    skills = load_skills()
    router = PluginRouter(skills)
    print("[Skills] loaded:", ", ".join(skills.keys()) if skills else "(none)")

    # Optional diagnostics at boot
    diag_flag = (os.getenv("ORION_DIAGNOSTICS_ON_BOOT") or "").strip().lower()
    if diag_flag in {"1", "true", "yes", "on", "y"}:
        try:
            diag_skill = skills.get("diagnostics")
            if diag_skill is None:
                print("[Diagnostics] 'diagnostics' skill not found. Say 'skill reload' after adding skills/diagnostics.py.")
            else:
                result = diag_skill.run("diagnostics", context={"mem": mem, "settings": settings})
                print("Orion (boot diagnostics):\n" + result)
        except Exception as e:
            print(f"[Diagnostics] Boot diagnostics failed: {e!r}")

    wake = WakeWord()
    print(f"[Wake] word: '{wake.wake}' | sleep terms: {wake.sleep_terms}")
    return Ctx(llm=llm, tts=tts, voice_id=voice_id, mem=mem, skills=skills, router=router, wake=wake)

def run_loop(ctx: Ctx):
    print(f"[TTS] using voice_id: {ctx.voice_id}")
    rec = make_recorder(model="tiny.en", language="en")
    print("Say the wake word to activate. Say 'clear.' to clear screen, 'close.' to exit.\n")

    awake = False
    try:
        while True:
            print("You: ", end="", flush=True)
            raw = mic_text(rec, timeout=MIC_TIMEOUT)
            if raw is None:
                print("[no audio detected]")
                raw = input("Type instead (or just press Enter to keep listening): ").strip()
            else:
                print(raw)
            if not raw:
                continue

            norm = raw.lower().strip()

            # Global controls
            if norm in {"clear", "clear."}:
                clear_screen(); continue
            if norm == "close.":
                print("👋 Closing program..."); break

            # Wake logic
            if not awake:
                if ctx.wake.heard_wake(norm):
                    leftover = ctx.wake.strip_wake(raw)
                    awake = True
                    print("[Wake] Orion is now AWAKE")
                    if not leftover:
                        say(ctx, "I'm listening."); continue
                    raw = leftover
                else:
                    continue
            else:
                if ctx.wake.heard_sleep(norm):
                    awake = False
                    print("[Wake] Orion is now SLEEPING")
                    say(ctx, "Going to sleep."); continue

            # Process command
            user = raw
            if user.lower().startswith(ctx.wake.wake.lower()):
                user = re.sub(rf"^\s*{re.escape(ctx.wake.wake)}[\s,:\-]+\s*", "", user, flags=re.I).strip()
            low = user.lower().strip()

            # Admin routes
            if handle_skill_admin(ctx, low):  continue
            if handle_memory_admin(ctx, low): continue

            # Memory Q&A fast path
            ans = memory_answer(ctx.mem, user)
            if ans:
                say(ctx, ans); continue

            # Log user
            ctx.mem.append_conversation(user=user)

            # Plugins → legacy → LLM
            sk = ctx.router.route(user)
            if sk:
                try:
                    result = sk.run(user, context={"mem": ctx.mem, "settings": settings})
                    say(ctx, result); continue
                except Exception as e:
                    print(f"Skill '{sk.name}' error: {e}. Falling back to legacy/LLM.")

            from core.router import route as _legacy_route
            legacy = _legacy_route(user)
            if legacy:
                try:
                    result = __import__("skills.registry", fromlist=["registry"]).registry.run(
                        legacy.name, user, context={"mem": ctx.mem, "settings": settings}
                    )
                    say(ctx, result); continue
                except Exception as e:
                    print(f"Legacy skill '{legacy.name}' error: {e}. Falling back to LLM.")

            llm_respond(ctx, user)

    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received. Exiting safely...")
    finally:
        rec.shutdown()
        print("✅ Recorder shut down. Goodbye!")