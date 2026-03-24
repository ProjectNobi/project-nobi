"""
Weather skill for Nori — uses wttr.in API (free, no key needed).
"""
import asyncio
import json
import logging
import re
from typing import Optional

logger = logging.getLogger("nobi-skills-weather")


async def fetch_weather(city: str) -> str:
    """
    Fetch current weather for a city from wttr.in.
    Returns a formatted string ready to inject into LLM context.
    """
    city_clean = city.strip().strip('"').strip("'")
    if not city_clean:
        return ""

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _fetch_weather_sync, city_clean)
        return result
    except Exception as e:
        logger.warning(f"[Weather] Error fetching weather for '{city_clean}': {e}")
        return f"[Weather API unavailable — could not fetch weather for {city_clean}]"


def _fetch_weather_sync(city: str) -> str:
    """Synchronous weather fetch using urllib (no extra deps)."""
    import urllib.request
    import urllib.parse
    import urllib.error

    city_encoded = urllib.parse.quote(city)
    url = f"https://wttr.in/{city_encoded}?format=j1"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "NoriBot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"[Weather: city '{city}' not found]"
        raise
    except json.JSONDecodeError:
        return f"[Weather: could not parse response for '{city}']"

    try:
        current = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]

        # Location name
        area_name = area.get("areaName", [{}])[0].get("value", city)
        country = area.get("country", [{}])[0].get("value", "")
        location = f"{area_name}, {country}" if country else area_name

        temp_c = current.get("temp_C", "?")
        temp_f = current.get("temp_F", "?")
        feels_c = current.get("FeelsLikeC", "?")
        feels_f = current.get("FeelsLikeF", "?")
        humidity = current.get("humidity", "?")
        wind_kmph = current.get("windspeedKmph", "?")
        wind_dir = current.get("winddir16Point", "?")

        # Description
        desc_list = current.get("weatherDesc", [{}])
        condition = desc_list[0].get("value", "Unknown") if desc_list else "Unknown"

        # Visibility
        visibility = current.get("visibility", "?")

        result = (
            f"[Current Weather for {location}]\n"
            f"Condition: {condition}\n"
            f"Temperature: {temp_c}°C / {temp_f}°F\n"
            f"Feels like: {feels_c}°C / {feels_f}°F\n"
            f"Humidity: {humidity}%\n"
            f"Wind: {wind_kmph} km/h {wind_dir}\n"
            f"Visibility: {visibility} km"
        )

        # Add forecast if available (tomorrow + day after)
        forecasts = data.get("weather", [])
        if len(forecasts) > 1:
            result += "\n\n[Forecast]"
            for day in forecasts[1:3]:  # tomorrow + day after
                date = day.get("date", "?")
                max_c = day.get("maxtempC", "?")
                min_c = day.get("mintempC", "?")
                max_f = day.get("maxtempF", "?")
                min_f = day.get("mintempF", "?")
                hourly = day.get("hourly", [{}])
                # Use midday condition as representative
                mid = hourly[len(hourly)//2] if hourly else {}
                desc = mid.get("weatherDesc", [{}])
                fcst_cond = desc[0].get("value", "?") if desc else "?"
                rain = mid.get("chanceofrain", "?")
                result += (
                    f"\n{date}: {fcst_cond}, {min_c}-{max_c}°C / {min_f}-{max_f}°F"
                    f", rain chance: {rain}%"
                )

        return result

    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"[Weather] Parse error for '{city}': {e}")
        return f"[Weather: could not parse data for '{city}']"


# ── Regex patterns for extracting city from user message ────

_WEATHER_PATTERNS = [
    # "weather in London", "weather for London", "weather at London"
    r"weather\s+(?:in|for|at|of)\s+([A-Za-z\s\-']+?)(?:\?|$|\.|\s+(?:today|now|tonight|tomorrow|this\s+week))",
    # "what's the weather in London"
    r"what(?:'s|s|is)\s+the\s+weather\s+(?:like\s+)?(?:in|for|at)?\s*([A-Za-z\s\-']+?)(?:\?|$|\.)",
    # "how's the weather in London"
    r"how(?:'s|s|is)\s+the\s+weather\s+(?:in|for|at)?\s*([A-Za-z\s\-']+?)(?:\?|$|\.)",
    # "temperature in London"
    r"temperature\s+(?:in|for|at|of)\s+([A-Za-z\s\-']+?)(?:\?|$|\.)",
    # "is it raining in London"
    r"(?:is it|will it)\s+(?:raining|sunny|cold|hot|snowing|cloudy)\s+(?:in|at)\s+([A-Za-z\s\-']+?)(?:\?|$|\.)",
    # "London weather"
    r"([A-Za-z\s\-']{2,30})\s+weather(?:\?|$|\.)",
]

_WEATHER_TRIGGER = re.compile(
    r"\b(?:weather|temperature|raining|sunny|cloudy|snowing|forecast|hot|cold)\b",
    re.IGNORECASE,
)


def detect_weather_query(message: str) -> Optional[str]:
    """
    Check if message is a weather query. Returns city name if found, else None.
    """
    if not _WEATHER_TRIGGER.search(message):
        return None

    msg = message.strip()
    for pattern in _WEATHER_PATTERNS:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            city = m.group(1).strip().rstrip("?.,!")
            # Sanity check — reject obviously wrong matches
            if 2 <= len(city) <= 50 and not city.lower() in ("the", "a", "an", "it", "me", "you"):
                return city
    return None
# Patch: additional weather patterns (appended)
_WEATHER_PATTERNS.extend([
    # "how hot is it in Tokyo", "how cold is it in London"
    r"how\s+(?:hot|cold|warm|cool)\s+is\s+it\s+(?:in|at)\s+([A-Za-z\s\-']+?)(?:\?|$|\.)",
    # "what's the temperature in London"
    r"what(?:'s|s|is)\s+the\s+temperature\s+(?:in|for|at)\s+([A-Za-z\s\-']+?)(?:\?|$|\.)",
])

# Patch: handle "how/what is the weather [today] in {city}"
_WEATHER_PATTERNS.append(
    r"(?:how|what)(?:'s|s| is)\s+the\s+weather\s+(?:like\s+)?(?:today|tonight|tomorrow)?\s*(?:in|for|at)\s+([A-Za-z\s\-']+?)(?:\?|$|\.)"
)
