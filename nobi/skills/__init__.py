"""
Nori Skills — pluggable capabilities for the companion bot.
"""
from .weather import fetch_weather, detect_weather_query
from .search import search_web, detect_search_query
from .reminders import (
    ReminderManager,
    detect_reminder_query,
    parse_reminder_time,
    extract_reminder_text,
    format_confirmation,
    reminder_delivery_loop,
)

__all__ = [
    # Weather
    "fetch_weather",
    "detect_weather_query",
    # Search
    "search_web",
    "detect_search_query",
    # Reminders
    "ReminderManager",
    "detect_reminder_query",
    "parse_reminder_time",
    "extract_reminder_text",
    "format_confirmation",
    "reminder_delivery_loop",
]
