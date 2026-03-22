"""
Project Nobi — Language-specific Prompt Generation
Adds language instructions and cultural sensitivity notes to system prompts.
"""

from nobi.i18n.languages import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE


# Cultural notes per language — formality, communication style, etc.
CULTURAL_NOTES = {
    "en": "",  # Default, no special notes
    "zh": (
        "Use simplified Chinese characters by default. "
        "Be respectful and slightly formal unless the user is clearly casual. "
        "Chinese internet slang is okay if the user uses it first."
    ),
    "hi": (
        "You can mix Hindi and English naturally (Hinglish) if the user does. "
        "Use respectful forms. Be warm and encouraging."
    ),
    "es": (
        "Use 'tú' (informal) by default unless the user uses 'usted'. "
        "Be warm and expressive — Spanish speakers appreciate emotional engagement."
    ),
    "fr": (
        "Use 'tu' (informal) by default unless the user uses 'vous'. "
        "French speakers appreciate wit and nuance."
    ),
    "ar": (
        "Be aware of right-to-left text direction. "
        "Use Modern Standard Arabic unless the user clearly uses a dialect. "
        "Respectful and warm tone is important."
    ),
    "bn": (
        "Use standard Bengali (Bangla). Be warm and respectful. "
        "Mix of formal and informal is common in everyday conversation."
    ),
    "pt": (
        "Default to Brazilian Portuguese unless the user indicates European Portuguese. "
        "Brazilian communication tends to be warm and informal."
    ),
    "ru": (
        "Use 'ты' (informal) for friendly conversation unless the user uses 'вы'. "
        "Russian communication can be direct — match the user's tone."
    ),
    "ja": (
        "Use polite form (です/ます) by default. "
        "Switch to casual form only if the user clearly uses casual Japanese. "
        "Japanese communication values subtlety and reading between the lines. "
        "Avoid being overly direct with criticism."
    ),
    "ms": (
        "Use standard Bahasa. Be friendly and respectful. "
        "Malay/Indonesian speakers appreciate a warm, helpful tone."
    ),
    "de": (
        "Use 'du' (informal) by default unless the user uses 'Sie'. "
        "German speakers appreciate precision and clarity."
    ),
    "ko": (
        "Use polite speech level (해요체) by default. "
        "Switch to casual (반말) only if the user clearly uses it first. "
        "Korean communication values respect for social hierarchy. "
        "Age and familiarity matter in tone selection."
    ),
    "tr": (
        "Use 'sen' (informal) by default unless the user uses 'siz'. "
        "Turkish speakers appreciate warmth and hospitality in communication."
    ),
    "vi": (
        "Vietnamese pronouns vary by age and relationship. "
        "Use 'bạn' (neutral/friendly) by default. "
        "Be respectful and warm."
    ),
    "it": (
        "Use 'tu' (informal) by default unless the user uses 'Lei'. "
        "Italian communication is expressive and warm."
    ),
    "th": (
        "Use polite particles (ครับ/ค่ะ) appropriately. "
        "Thai communication values politeness and respect. "
        "Avoid being too direct with disagreements."
    ),
    "pl": (
        "Use 'ty' (informal) by default unless the user uses formal 'Pan/Pani'. "
        "Polish speakers appreciate directness with warmth."
    ),
    "uk": (
        "Use 'ти' (informal) for friendly conversation. "
        "Be warm and supportive. Ukrainian communication values sincerity."
    ),
    "nl": (
        "Use 'je/jij' (informal) by default. "
        "Dutch speakers appreciate directness and honesty."
    ),
}


def get_language_prompt(lang_code: str) -> str:
    """
    Generate a language instruction to prepend/append to the system prompt.
    Returns empty string for English (no instruction needed).
    """
    if lang_code == DEFAULT_LANGUAGE or lang_code not in SUPPORTED_LANGUAGES:
        return ""

    lang = SUPPORTED_LANGUAGES[lang_code]
    lang_name = lang["name"]
    native_name = lang["native"]

    prompt_parts = [
        f"\n== LANGUAGE INSTRUCTION ==",
        f"The user is communicating in {lang_name} ({native_name}).",
        f"Respond in {lang_name}. Match the user's language naturally.",
        "If the user switches languages mid-conversation, follow them seamlessly.",
        "Keep your personality and warmth — just express it in their language.",
    ]

    cultural = get_cultural_notes(lang_code)
    if cultural:
        prompt_parts.append(f"\nCultural note: {cultural}")

    return "\n".join(prompt_parts)


def get_cultural_notes(lang_code: str) -> str:
    """Get cultural sensitivity notes for a language."""
    return CULTURAL_NOTES.get(lang_code, "")


def build_multilingual_system_prompt(base_prompt: str, lang_code: str) -> str:
    """
    Append language instructions to an existing system prompt.
    Always includes an explicit language instruction, even for English.
    """
    lang_instruction = get_language_prompt(lang_code)
    if not lang_instruction:
        # Default to English but allow switching if user writes in another language
        return base_prompt + "\n\n== LANGUAGE RULE ==\nDefault to English. If the user writes in another language, reply in THAT language naturally. You support 20+ languages. Never refuse to speak a language the user is using."
    return base_prompt + "\n" + lang_instruction
