# core/config.py
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Load .env as soon as this module imports (works even when run from subfolders)
ENV_PATH = find_dotenv(usecwd=True) or (Path(__file__).resolve().parents[1] / ".env")
load_dotenv(ENV_PATH, override=True)

class _Settings:
    DATA_DIR = Path.home() / ".orion"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY") or os.getenv("OPEN_WEATHER_API_KEY") or ""

    SYSTEM_INSTRUCTION = os.getenv(
        "SYSTEM_INSTRUCTION",
        "My name is Benjamin. I am a developer. You are Orion, a helpful JARVIS-like assistant.",
    )

settings = _Settings()