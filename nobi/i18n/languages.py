"""
Project Nobi — Supported Languages
Top 20 most spoken languages by total speakers.
"""

SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "native": "English", "greeting": "Hey!"},
    "zh": {"name": "Chinese", "native": "中文", "greeting": "你好!"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "greeting": "नमस्ते!"},
    "es": {"name": "Spanish", "native": "Español", "greeting": "¡Hola!"},
    "fr": {"name": "French", "native": "Français", "greeting": "Salut!"},
    "ar": {"name": "Arabic", "native": "العربية", "greeting": "مرحبا!"},
    "bn": {"name": "Bengali", "native": "বাংলা", "greeting": "হ্যালো!"},
    "pt": {"name": "Portuguese", "native": "Português", "greeting": "Olá!"},
    "ru": {"name": "Russian", "native": "Русский", "greeting": "Привет!"},
    "ja": {"name": "Japanese", "native": "日本語", "greeting": "こんにちは!"},
    "ms": {"name": "Malay/Indonesian", "native": "Bahasa", "greeting": "Halo!"},
    "de": {"name": "German", "native": "Deutsch", "greeting": "Hallo!"},
    "ko": {"name": "Korean", "native": "한국어", "greeting": "안녕!"},
    "tr": {"name": "Turkish", "native": "Türkçe", "greeting": "Merhaba!"},
    "vi": {"name": "Vietnamese", "native": "Tiếng Việt", "greeting": "Xin chào!"},
    "it": {"name": "Italian", "native": "Italiano", "greeting": "Ciao!"},
    "th": {"name": "Thai", "native": "ไทย", "greeting": "สวัสดี!"},
    "pl": {"name": "Polish", "native": "Polski", "greeting": "Cześć!"},
    "uk": {"name": "Ukrainian", "native": "Українська", "greeting": "Привіт!"},
    "nl": {"name": "Dutch", "native": "Nederlands", "greeting": "Hoi!"},
}

# Default fallback language
DEFAULT_LANGUAGE = "en"


def get_language_name(code: str) -> str:
    """Get the English name of a language by its code."""
    lang = SUPPORTED_LANGUAGES.get(code)
    return lang["name"] if lang else "English"


def get_native_name(code: str) -> str:
    """Get the native name of a language by its code."""
    lang = SUPPORTED_LANGUAGES.get(code)
    return lang["native"] if lang else "English"


def get_greeting(code: str) -> str:
    """Get a greeting in the specified language."""
    lang = SUPPORTED_LANGUAGES.get(code)
    return lang["greeting"] if lang else "Hey!"


def is_supported(code: str) -> bool:
    """Check if a language code is supported."""
    return code in SUPPORTED_LANGUAGES
