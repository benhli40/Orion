# orion/core/context.py
from dataclasses import dataclass
from core.llm import LLM
from core.voice import TTS
from core.memory import Memory
from core.plugins import PluginRouter
from core.wake import WakeWord

@dataclass
class Ctx:
    llm: LLM
    tts: TTS
    voice_id: str
    mem: Memory
    skills: dict
    router: PluginRouter
    wake: WakeWord

def say(ctx: "Ctx", text: str):
    """Print, speak, and log bot output."""
    print("Orion:", text)
    try:
        ctx.tts.speak(text, voice_id=ctx.voice_id)
    except Exception as e:
        print(f"[TTS] {e}")
    ctx.mem.append_conversation(bot=text)