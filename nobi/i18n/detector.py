"""
Project Nobi — Language Detection
Pure heuristic language detection using Unicode character ranges and common word patterns.
No external ML dependencies. Target: <1ms per call.
"""

import re
from functools import lru_cache
from nobi.i18n.languages import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE


# ─── Unicode Character Range Patterns ─────────────────────────
# Pre-compiled for speed

# CJK Unified Ideographs (Chinese/Japanese Kanji)
_RE_CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

# Japanese Hiragana + Katakana (distinguishes Japanese from Chinese)
_RE_HIRAGANA = re.compile(r'[\u3040-\u309f]')
_RE_KATAKANA = re.compile(r'[\u30a0-\u30ff]')

# Korean Hangul
_RE_HANGUL = re.compile(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]')

# Arabic script
_RE_ARABIC = re.compile(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]')

# Devanagari (Hindi)
_RE_DEVANAGARI = re.compile(r'[\u0900-\u097f]')

# Bengali
_RE_BENGALI = re.compile(r'[\u0980-\u09ff]')

# Thai
_RE_THAI = re.compile(r'[\u0e00-\u0e7f]')

# Cyrillic (Russian, Ukrainian)
_RE_CYRILLIC = re.compile(r'[\u0400-\u04ff]')

# Vietnamese diacritical marks (Latin + specific tone marks)
_RE_VIETNAMESE = re.compile(r'[ăắằẳẵặâấầẩẫậđêếềểễệôốồổỗộơớờởỡợưứừửữự]', re.IGNORECASE)

# ─── Common Word Patterns (for Latin-script languages) ────────

_WORD_PATTERNS = {
    "es": re.compile(
        r'\b(?:el|la|los|las|es|está|estoy|tengo|pero|como|qué|por|para|con|una?|yo|'
        r'hola|gracias|bien|también|mucho|tiene|esto|eso|todo|más|muy|puede|hacer|'
        r'quiero|soy|siempre|nunca|donde|cuando|porque|bueno|malo)\b',
        re.IGNORECASE
    ),
    "fr": re.compile(
        r'\b(?:le|la|les|des|est|suis|je|tu|il|elle|nous|vous|ils|elles|un|une|'
        r'mais|ou|et|donc|car|avec|pour|dans|sur|pas|que|qui|ce|cette|sont|ont|'
        r'bonjour|salut|merci|bien|aussi|très|peut|faire|avoir|être)\b',
        re.IGNORECASE
    ),
    "pt": re.compile(
        r'\b(?:o|a|os|as|é|está|estou|tenho|mas|como|que|por|para|com|uma?|eu|'
        r'olá|obrigad[oa]|bem|também|muito|tem|isto|isso|tudo|mais|pode|fazer|'
        r'quero|sou|sempre|nunca|onde|quando|porque|bom|mau|não|sim)\b',
        re.IGNORECASE
    ),
    "de": re.compile(
        r'\b(?:der|die|das|ein|eine|ist|bin|habe|aber|wie|was|für|mit|und|oder|'
        r'nicht|auf|von|zu|ich|du|er|sie|wir|ihr|haben|sein|werden|kann|muss|'
        r'hallo|danke|gut|auch|sehr|schon|noch|hier|dort|warum|weil)\b',
        re.IGNORECASE
    ),
    "it": re.compile(
        r'\b(?:il|lo|la|i|gli|le|è|sono|ho|ma|come|che|per|con|un|una|io|tu|'
        r'lui|lei|noi|voi|loro|ciao|grazie|bene|anche|molto|ha|questo|quello|'
        r'tutto|più|può|fare|avere|essere|sempre|mai|dove|quando|perché)\b',
        re.IGNORECASE
    ),
    "nl": re.compile(
        r'\b(?:de|het|een|is|ben|heb|maar|hoe|wat|voor|met|en|of|niet|op|van|'
        r'te|ik|je|jij|hij|zij|wij|jullie|hebben|zijn|worden|kan|moet|'
        r'hallo|hoi|dank|goed|ook|heel|erg|nog|hier|daar|waarom|omdat)\b',
        re.IGNORECASE
    ),
    "pl": re.compile(
        r'\b(?:jest|jestem|mam|ale|jak|co|dla|z|i|lub|nie|na|do|ja|ty|on|ona|'
        r'my|wy|oni|mieć|być|cześć|dzięki|dobrze|też|bardzo|może|'
        r'robić|zawsze|nigdy|gdzie|kiedy|dlaczego|tak|nie)\b',
        re.IGNORECASE
    ),
    "tr": re.compile(
        r'\b(?:bir|bu|şu|ve|ile|için|ama|nasıl|ne|ben|sen|o|biz|siz|onlar|'
        r'var|yok|değil|merhaba|teşekkür|iyi|de|da|çok|daha|olan|olan|'
        r'yapmak|olmak|gelmek|gitmek|neden|çünkü|evet|hayır)\b',
        re.IGNORECASE
    ),
    "vi": re.compile(
        r'\b(?:là|có|không|và|của|cho|với|này|đó|tôi|bạn|anh|chị|em|'
        r'chúng|họ|xin|chào|cảm ơn|tốt|cũng|rất|nhiều|hơn|'
        r'làm|được|đi|đến|tại sao|vì|vâng|dạ)\b',
        re.IGNORECASE
    ),
}

# Ukrainian-specific letters (not in Russian)
_RE_UKRAINIAN = re.compile(r'[іїєґ]', re.IGNORECASE)
# Russian-specific letters (not in Ukrainian)
_RE_RUSSIAN = re.compile(r'[ыэъё]', re.IGNORECASE)


class LanguageDetector:
    """
    Stateful language detector with per-user caching.
    Users tend to stick to one language, so cache their last detected language.
    """

    def __init__(self):
        self._user_cache: dict[str, str] = {}

    def detect(self, text: str, user_id: str = "") -> str:
        """
        Detect the language of the given text.
        If user_id is provided, uses cached language as tiebreaker.
        Returns ISO 639-1 language code.
        """
        detected = _detect_language_core(text)

        # Override: if core says non-English but text clearly looks English (3+ words),
        # trust _looks_english (core often confuses English with Dutch/German)
        if detected != "en" and len(text.split()) >= 5 and _looks_english(text):
            detected = "en"

        if user_id:
            if detected == DEFAULT_LANGUAGE and user_id in self._user_cache:
                # Short ambiguous messages — use cached language
                if len(text.split()) < 3 and not _looks_english(text):
                    detected = self._user_cache[user_id]
            # Update cache for non-ambiguous detections
            if len(text.split()) >= 3:
                self._user_cache[user_id] = detected

        return detected

    def set_user_language(self, user_id: str, lang_code: str) -> bool:
        """Manually set a user's preferred language. Returns True if valid."""
        if lang_code in SUPPORTED_LANGUAGES:
            self._user_cache[user_id] = lang_code
            return True
        return False

    def get_user_language(self, user_id: str) -> str:
        """Get cached language for user, or default."""
        return self._user_cache.get(user_id, DEFAULT_LANGUAGE)

    def clear_user(self, user_id: str):
        """Clear cached language for a user."""
        self._user_cache.pop(user_id, None)


# Module-level singleton for convenience
_detector = LanguageDetector()


def detect_language(text: str, user_id: str = "") -> str:
    """
    Detect language from text. Pure heuristic, <1ms.
    Falls back to 'en' if uncertain.
    """
    return _detector.detect(text, user_id)


def _detect_language_core(text: str) -> str:
    """Core detection logic using character sets and word patterns."""
    if not text or not text.strip():
        return DEFAULT_LANGUAGE

    text = text.strip()

    # Step 1: Script-based detection (fastest, most reliable)
    # Count characters in each script
    thai_count = len(_RE_THAI.findall(text))
    if thai_count >= 2:
        return "th"

    bengali_count = len(_RE_BENGALI.findall(text))
    if bengali_count >= 2:
        return "bn"

    devanagari_count = len(_RE_DEVANAGARI.findall(text))
    if devanagari_count >= 2:
        return "hi"

    arabic_count = len(_RE_ARABIC.findall(text))
    if arabic_count >= 2:
        return "ar"

    hangul_count = len(_RE_HANGUL.findall(text))
    if hangul_count >= 2:
        return "ko"

    # Japanese vs Chinese: check for Hiragana/Katakana first
    hiragana_count = len(_RE_HIRAGANA.findall(text))
    katakana_count = len(_RE_KATAKANA.findall(text))
    cjk_count = len(_RE_CJK.findall(text))

    if hiragana_count >= 1 or katakana_count >= 1:
        return "ja"
    if cjk_count >= 2:
        return "zh"

    # Cyrillic: distinguish Russian vs Ukrainian
    cyrillic_count = len(_RE_CYRILLIC.findall(text))
    if cyrillic_count >= 2:
        ukr_markers = len(_RE_UKRAINIAN.findall(text))
        rus_markers = len(_RE_RUSSIAN.findall(text))
        if ukr_markers > rus_markers:
            return "uk"
        return "ru"

    # Step 2: Vietnamese detection (Latin script with specific diacritics)
    viet_count = len(_RE_VIETNAMESE.findall(text))
    if viet_count >= 2:
        return "vi"

    # Step 3: Latin-script language detection via common word patterns
    # Count pattern matches for each language
    scores: dict[str, int] = {}
    for lang_code, pattern in _WORD_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            scores[lang_code] = len(matches)

    if scores:
        best_lang = max(scores, key=scores.get)
        best_score = scores[best_lang]
        # Need at least 2 matches to be confident
        if best_score >= 2:
            return best_lang
        # Single match: check if English also matches
        if best_score == 1 and not _looks_english(text):
            return best_lang

    # Step 4: Default to English
    return DEFAULT_LANGUAGE


def _looks_english(text: str) -> bool:
    """Quick check if text appears to be English."""
    english_words = re.compile(
        r'\b(?:the|is|am|are|was|were|have|has|had|do|does|did|will|would|'
        r'can|could|should|may|might|must|shall|a|an|it|this|that|I|you|'
        r'he|she|we|they|my|your|his|her|our|their|what|how|why|when|where|'
        r'hello|hi|hey|thanks|yes|no|ok|okay|good|great|nice|love|like)\b',
        re.IGNORECASE
    )
    matches = english_words.findall(text)
    return len(matches) >= 2
