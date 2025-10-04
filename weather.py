# orion/skills/weather.py
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import requests
from core.config import settings

NAME = "weather"
DESCRIPTION = "Current conditions and simple forecasts via OpenWeather."
TRIGGERS = [r"\b(weather|forecast|temp(?:erature)?|rain|wind|snow|humidity|humid)\b"]

IMPERIAL_COUNTRIES = {"US"}  # add more if you like
HEADERS = {"User-Agent": "Orion/1.0 (+https://example.local)"}
TIMEOUT = 8

# --- ASR/typo normalization helpers ---
_ALIASES = {
    "muddle falls": "marble falls",
    "marvel falls": "marble falls",
    "marbel falls": "marble falls",
    "marble falls texas": "marble falls, tx",
    "marble falls, texas": "marble falls, tx",
}

def _normalize_loc_text(s: str) -> str:
    s = (s or "").strip().strip(" .,!?:;\"'()[]{}")
    low = s.lower()
    # fix common mis-hearings first
    for bad, good in _ALIASES.items():
        low = low.replace(bad, good)
    # common STT: "and X" -> "in X"
    low = re.sub(r"\band\b\s+(?=[a-z])", "in ", low)
    # Title-case words, but keep short codes (tx, us, fr) uppercased
    parts = [w.upper() if len(w) <= 3 and w.isalpha() else w.title() for w in low.split()]
    return " ".join(parts)

def _units_for(country: Optional[str]) -> str:
    if country and country.upper() in IMPERIAL_COUNTRIES:
        return "imperial"
    return "metric"

def _api_key() -> str:
    key = settings.OPENWEATHER_API_KEY
    if not key:
        raise ValueError("OPENWEATHER_API_KEY not set for weather.")
    return key

def _extract_location_text(query: str) -> str:
    """
    Be forgiving:
      - "Orion, what's the weather and Marble Falls, Texas?"
      - "Weather, Marble Falls" (reverse)
      - "forecast for London" / "weather near Austin"
    """
    q = (query or "").strip()

    # Strip leading wake word if present
    q = re.sub(r"^\s*orion[\s,:\-]+", "", q, flags=re.I).strip()

    # Remove 'weather/forecast' for easier parsing
    core = re.sub(r"\b(weather|forecast)\b", "", q, flags=re.I).strip()

    # 1) Canonical: "... in/for/at/near/around/and <loc>"
    m = re.search(r"\b(?:in|for|at|near|around|and)\b\s+(.+)$", core, flags=re.I)
    if m:
        return _normalize_loc_text(m.group(1))

    # 2) Reverse order: "<loc> ,? weather"
    m = re.search(r"^(.+?)\s*,?\s*(?:weather|forecast)\b", q, flags=re.I)
    if m:
        return _normalize_loc_text(m.group(1))

    # 3) Fallback: if there's a comma, take the trailing part
    if "," in q:
        tail = q.split(",", maxsplit=1)[-1]
        return _normalize_loc_text(tail)

    # 4) Last resort: whatever's left
    return _normalize_loc_text(core or q)

def _geocode(loc_text: str) -> Optional[Tuple[float, float, str, Optional[str]]]:
    """
    Return (lat, lon, display_name, country_code) using OpenWeather geocoding.
    If nothing is found, try again with ', US' for common U.S. towns.
    """
    if not loc_text:
        loc_text = "Austin, US"
    params = {"q": loc_text, "limit": 1, "appid": _api_key()}
    r = requests.get("https://api.openweathermap.org/geo/1.0/direct",
                     params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json() or []
    if not data and "," not in loc_text:
        # second chance: append country
        params["q"] = f"{loc_text}, US"
        r = requests.get("https://api.openweathermap.org/geo/1.0/direct",
                         params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json() or []
    if not data:
        return None

    item = data[0]
    lat = float(item["lat"])
    lon = float(item["lon"])
    name = str(item.get("name") or loc_text)
    country = item.get("country")
    state = item.get("state")
    if state and country:
        display = f"{name}, {state}, {country}"
    elif country:
        display = f"{name}, {country}"
    else:
        display = name
    return lat, lon, display, country

def _fmt_wind_speed(speed: float, units: str) -> str:
    return f"{speed:.0f} {'mph' if units == 'imperial' else 'm/s'}"

def _fmt_temp(val: float, units: str) -> str:
    return f"{val:.0f}°{'F' if units == 'imperial' else 'C'}"

def _current_weather(lat: float, lon: float, units: str) -> dict:
    params = {"lat": lat, "lon": lon, "appid": _api_key(), "units": units}
    r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                     params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def _forecast(lat: float, lon: float, units: str) -> dict:
    params = {"lat": lat, "lon": lon, "appid": _api_key(), "units": units, "cnt": 8}  # ~next 24h (3h steps)
    r = requests.get("https://api.openweathermap.org/data/2.5/forecast",
                     params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def _format_current(name: str, units: str, j: dict) -> str:
    desc = (j["weather"][0]["description"] or "").title()
    temp = _fmt_temp(j["main"]["temp"], units)
    feels = _fmt_temp(j["main"]["feels_like"], units)
    wind = _fmt_wind_speed(j["wind"]["speed"], units)
    humidity = j["main"].get("humidity")
    humidity_str = f", humidity {humidity}%" if humidity is not None else ""
    return f"{name}: {desc}. Temp {temp} (feels {feels}), wind {wind}{humidity_str}."

def _format_forecast(name: str, units: str, j: dict) -> str:
    tz_shift = j.get("city", {}).get("timezone", 0)  # seconds offset from UTC
    tz = timezone(timedelta(seconds=tz_shift))
    rows = []
    for e in (j.get("list") or [])[:4]:  # next ~12 hours
        dt_utc = datetime.utcfromtimestamp(e["dt"]).replace(tzinfo=timezone.utc)
        local = dt_utc.astimezone(tz)
        # cross-platform hour format (strip leading zero)
        hhmm = local.strftime("%I%p").lstrip("0")
        desc = (e["weather"][0]["description"] or "").title()
        t = _fmt_temp(e["main"]["temp"], units)
        rows.append(f"{hhmm}: {desc}, {t}")
    if not rows:
        return f"{name}: No forecast data available."
    return f"{name} — next 12 hours:\n" + "; ".join(rows)

def run(query: str, context: dict) -> str:
    try:
        loc_text = _extract_location_text(query)
        geo = _geocode(loc_text)
        if not geo:
            return f"Sorry, I couldn’t find that location: {loc_text!r}."
        lat, lon, display, country = geo
        units = _units_for(country)

        is_forecast = bool(re.search(r"\bforecast\b", query or "", flags=re.I))
        if is_forecast:
            data = _forecast(lat, lon, units)
            return _format_forecast(display, units, data)
        else:
            data = _current_weather(lat, lon, units)
            return _format_current(display, units, data)

    except requests.HTTPError as e:
        try:
            payload = e.response.json()
        except Exception:
            payload = {}
        msg = payload.get("message") or str(e)
        return f"Weather error: {msg}"
    except Exception as e:
        return f"Weather error: {e}"