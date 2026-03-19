# Project Nobi — Internationalization (i18n)
# Multi-language support for Nori companion

from nobi.i18n.languages import SUPPORTED_LANGUAGES
from nobi.i18n.detector import detect_language, LanguageDetector
from nobi.i18n.prompts import get_language_prompt, get_cultural_notes

__all__ = [
    "SUPPORTED_LANGUAGES",
    "detect_language",
    "LanguageDetector",
    "get_language_prompt",
    "get_cultural_notes",
]
