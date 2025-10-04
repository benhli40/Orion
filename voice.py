# core/voice.py
from typing import Optional
from RealtimeSTT import AudioToTextRecorder
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
from elevenlabs.core.api_error import ApiError

def make_recorder(model: str = "tiny.en", language: str = "en", spinner: bool = False):
    return AudioToTextRecorder(model=model, language=language, spinner=spinner)

class TTS:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY missing")
        self.client = ElevenLabs(api_key=api_key)

    def speak(
        self,
        text: str,
        voice_id: str,
        model_id: str = "eleven_flash_v2_5",
        fmt: str = "mp3_44100_128",
    ):
        if not text:
            return
        try:
            audio_iter = self.client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format=fmt,
            )
        except ApiError as e:
            # Make the two most common issues crystal clear
            status = None
            try:
                status = (e.body or {}).get("detail", {}).get("status")
            except Exception:
                pass
            if status == "voice_not_found":
                raise RuntimeError(
                    f"ElevenLabs voice not found: '{voice_id}'. "
                    "Set a valid ELEVEN_VOICE_ID in your .env (from your ElevenLabs Voice page)."
                ) from e
            if status == "missing_permissions":
                raise RuntimeError(
                    "Your ElevenLabs API key is missing permissions for text_to_speech.convert. "
                    "Create a key with at least 'text_to_speech_convert' (and 'voices_read' if you want name->ID resolution)."
                ) from e
            raise

        # Join stream to bytes and play
        play(b"".join(audio_iter))

def resolve_voice_id(tts_client: ElevenLabs, preferred: Optional[str] = None) -> str:
    """
    If a voice *ID* is provided (ELEVEN_VOICE_ID), use it directly (no permissions needed).
    If a *name* is provided (ELEVEN_VOICE_NAME), we must list voices (requires 'voices_read').
    Otherwise, try to pick a common default or the first available voice.
    """
    # Fast-path: looks like an ID (no spaces, long-ish)
    if preferred and " " not in preferred and len(preferred) >= 12:
        return preferred

    # If we reached here, we need to list voices (to match a name or choose a default)
    try:
        voices = tts_client.voices.get_all()
    except ApiError as e:
        status = None
        try:
            status = (e.body or {}).get("detail", {}).get("status")
        except Exception:
            pass
        if status == "missing_permissions":
            raise RuntimeError(
                "Your ElevenLabs API key is missing 'voices_read'. "
                "Either set ELEVEN_VOICE_ID in .env to a specific voice id (no listing required), "
                "or create a key with 'voices_read' permission."
            ) from e
        raise

    items = getattr(voices, "voices", []) or []

    # If a preferred *name* was provided, try match by name
    if preferred:
        pref_lower = preferred.strip().lower()
        for v in items:
            if v.name.lower() == pref_lower:
                return v.voice_id

    # Try common defaults
    for v in items:
        if v.name.lower() in {"rachel", "alloy", "bella"}:
            return v.voice_id

    if items:
        return items[0].voice_id

    raise RuntimeError("No ElevenLabs voices available on this account.")