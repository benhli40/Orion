# orion/core/llm_path.py
from core.context import Ctx
from core.memory_bridge import memory_answer, relevant_facts, format_fact_context

def llm_respond(ctx: Ctx, user: str):
    """Stream → send → reset+send → graceful fallback. Includes relevant facts."""
    facts = relevant_facts(ctx.mem, user, limit=6)
    preface = format_fact_context(facts)
    user_for_llm = f"{preface}\n\nUser: {user}" if preface else user

    full = []
    printed_stream = False

    # 1) Try streaming
    for chunk in ctx.llm.stream(user_for_llm):
        if chunk:
            if not printed_stream:
                print("Orion: ", end="", flush=True)
                printed_stream = True
            print(chunk, end="", flush=True)
            full.append(chunk)

    if printed_stream:
        print()

    reply = "".join(full).strip()

    # 2) Fallback to non-streaming
    if not reply:
        reply = ctx.llm.send(user_for_llm)

    # 3) Reset then try again (transient issues)
    if not reply:
        ctx.llm.reset()
        reply = ctx.llm.send(user_for_llm)

    # 4) Always say something
    if not reply:
        reply = "Sorry, I couldn't generate a response just now. Please try again."

    if not printed_stream:
        print("Orion:", reply)

    try:
        ctx.tts.speak(reply, voice_id=ctx.voice_id)
    except Exception as e:
        print(f"[TTS] {e}")

    ctx.mem.append_conversation(bot=reply)