# orion/core/llm.py
from typing import Iterable, Optional
from google import genai
from google.genai import types

class LLM:
    def __init__(
        self,
        api_key: str,
        system_instruction: str,
        model: str = "gemini-2.5-flash",
        max_tokens: int = 200,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY missing")

        self._api_key = api_key
        self._model = model
        self._system_instruction = system_instruction
        self._max_tokens = max_tokens

        self.client = genai.Client(api_key=api_key)
        self._new_chat()

    def _new_chat(self):
        self.chat = self.client.chats.create(
            model=self._model,
            config=types.GenerateContentConfig(
                system_instruction=self._system_instruction,
                max_output_tokens=self._max_tokens,
            ),
        )

    def stream(self, user_text: str) -> Iterable[str]:
        """
        Yield text chunks as they arrive; ignore non-text events.
        On error, quietly stop yielding (main.py already falls back to send()).
        """
        try:
            resp = self.chat.send_message_stream(user_text)
            for chunk in resp:
                txt = getattr(chunk, "text", None)
                if txt:
                    yield txt
        except Exception:
            # Optionally refresh chat so the next turn is clean
            try:
                self._new_chat()
            except Exception:
                pass
            # Do not re-raise; main.py will call send() as a fallback.

    def send(self, user_text: str) -> str:
        """
        Non-streaming single call that returns the full text (fallback path).
        Returns empty string on error (main.py checks and continues).
        """
        try:
            resp = self.chat.send_message(user_text)
            return (getattr(resp, "text", "") or "").strip()
        except Exception:
            try:
                self._new_chat()
            except Exception:
                pass
            return ""

    def reset(self):
        """Reset the conversation with the current config."""
        self._new_chat()

    def update_system_instruction(self, new_instruction: Optional[str] = None):
        """
        Update the system prompt at runtime and start a new chat.
        If new_instruction is None, just resets with the existing prompt.
        """
        if new_instruction is not None:
            self._system_instruction = new_instruction
        self._new_chat()