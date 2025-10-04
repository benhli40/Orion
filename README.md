Orion — a voice-first JARVIS-style assistant (Gemini + ElevenLabs)

Orion is a modular, voice-activated desktop assistant. Speak the wake word (“Orion”), ask for weather/news/search, manage skills on the fly, store facts in long-term memory, and get natural replies via Google Gemini with spoken output from ElevenLabs.

✨ Features

Wake word activation + sleep terms

Live STT (RealtimeSTT / Whisper small model downloads on first run)

LLM responses (Gemini) with streaming → fallback → self-reset

TTS (ElevenLabs) with pluggable voice

Skills system with hot reload, enable/disable, scaffolding

Memory you can set/get/list; answers can pull from memory automatically

Diagnostics skill (optional) and boot-time checks

Clean architecture: runtime loop + admin handlers + LLM path split into modules

🧰 Requirements

Python 3.10+

Mic + speakers

CPU with AVX (recommended by CTranslate2/Whisper)

(Windows) You may need Visual C++ Build Tools; (macOS) Xcode CLT

First run of STT may download the Whisper model (e.g., tiny.en) which can take a minute.

📦 Installation
