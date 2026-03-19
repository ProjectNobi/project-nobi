"""
Tests for Project Nobi i18n (internationalization) module.
Tests language detection, prompt generation, and cultural sensitivity.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from nobi.i18n.detector import detect_language, LanguageDetector, _detect_language_core
from nobi.i18n.languages import SUPPORTED_LANGUAGES, get_language_name, get_greeting, is_supported
from nobi.i18n.prompts import get_language_prompt, get_cultural_notes, build_multilingual_system_prompt


# ─── Language Detection Tests ─────────────────────────────────

class TestLanguageDetection:
    """Test language detection for all major languages."""

    def test_english(self):
        assert detect_language("Hello, how are you doing today?") == "en"
        assert detect_language("I love programming and reading books") == "en"

    def test_chinese(self):
        assert detect_language("你好，今天天气怎么样？") == "zh"
        assert detect_language("我很喜欢编程") == "zh"

    def test_hindi(self):
        assert detect_language("नमस्ते, आप कैसे हैं?") == "hi"
        assert detect_language("मुझे प्रोग्रामिंग पसंद है") == "hi"

    def test_spanish(self):
        assert detect_language("Hola, ¿cómo estás? Yo estoy muy bien hoy") == "es"
        assert detect_language("Tengo una pregunta para hacer") == "es"

    def test_french(self):
        assert detect_language("Bonjour, comment allez-vous aujourd'hui? Je suis bien") == "fr"
        assert detect_language("Je suis très content de vous rencontrer") == "fr"

    def test_arabic(self):
        assert detect_language("مرحبا، كيف حالك؟") == "ar"
        assert detect_language("أنا أحب البرمجة") == "ar"

    def test_japanese(self):
        assert detect_language("こんにちは、元気ですか？") == "ja"
        assert detect_language("プログラミングが好きです") == "ja"

    def test_korean(self):
        assert detect_language("안녕하세요, 어떻게 지내세요?") == "ko"
        assert detect_language("프로그래밍을 좋아해요") == "ko"

    def test_russian(self):
        assert detect_language("Привет, как дела? Всё хорошо у меня") == "ru"
        assert detect_language("Мне нравится программирование") == "ru"

    def test_thai(self):
        assert detect_language("สวัสดีครับ วันนี้เป็นอย่างไรบ้าง") == "th"
        assert detect_language("ผมชอบเขียนโปรแกรม") == "th"

    def test_bengali(self):
        assert detect_language("হ্যালো, আপনি কেমন আছেন?") == "bn"

    def test_german(self):
        assert detect_language("Hallo, wie geht es dir? Ich bin sehr gut") == "de"

    def test_italian(self):
        assert detect_language("Ciao, come stai? Io sono molto bene") == "it"

    def test_portuguese(self):
        assert detect_language("Olá, como você está? Eu estou muito bem") == "pt"

    def test_turkish(self):
        assert detect_language("Merhaba, nasılsın? Ben çok iyiyim") == "tr"

    def test_vietnamese(self):
        assert detect_language("Xin chào, bạn khỏe không? Tôi rất vui") == "vi"

    def test_polish(self):
        assert detect_language("Cześć, jak się masz? Jestem bardzo dobrze") == "pl"

    def test_ukrainian(self):
        assert detect_language("Привіт, як справи? Все добре у мене, дякую") == "uk"

    def test_dutch(self):
        assert detect_language("Hallo, hoe gaat het met je? Ik ben heel goed") == "nl"

    def test_malay(self):
        # Malay uses Latin script — detection via word patterns is harder
        # At minimum, it shouldn't crash
        result = detect_language("Halo, apa khabar?")
        assert result in SUPPORTED_LANGUAGES


class TestMixedLanguage:
    """Test detection when user switches or mixes languages."""

    def test_mixed_english_chinese(self):
        # Chinese characters should win
        result = detect_language("I want to learn 中文编程")
        assert result == "zh"

    def test_mixed_english_japanese(self):
        # 日本語 uses only kanji (CJK) — detected as Chinese without hiragana/katakana
        # Use hiragana to trigger Japanese detection
        result = detect_language("Let's study にほんご together")
        assert result == "ja"

    def test_short_text_fallback(self):
        # Very short text should fall back to English
        assert detect_language("ok") == "en"
        assert detect_language("hi") == "en"

    def test_empty_text(self):
        assert detect_language("") == "en"
        assert detect_language("   ") == "en"

    def test_numbers_only(self):
        assert detect_language("12345") == "en"

    def test_emoji_only(self):
        assert detect_language("😊👍🎉") == "en"


class TestDetectionPerformance:
    """Ensure language detection is fast (<1ms per call)."""

    def test_speed_short_text(self):
        text = "Hello, how are you?"
        start = time.perf_counter()
        for _ in range(1000):
            detect_language(text)
        elapsed = (time.perf_counter() - start) / 1000
        assert elapsed < 0.001, f"Detection too slow: {elapsed*1000:.3f}ms per call"

    def test_speed_long_text(self):
        text = "This is a longer text that contains multiple sentences. " * 10
        start = time.perf_counter()
        for _ in range(1000):
            detect_language(text)
        elapsed = (time.perf_counter() - start) / 1000
        assert elapsed < 0.001, f"Detection too slow: {elapsed*1000:.3f}ms per call"

    def test_speed_cjk(self):
        text = "这是一段较长的中文文本，包含多个句子。" * 5
        start = time.perf_counter()
        for _ in range(1000):
            detect_language(text)
        elapsed = (time.perf_counter() - start) / 1000
        assert elapsed < 0.001, f"Detection too slow: {elapsed*1000:.3f}ms per call"


class TestLanguageDetectorStateful:
    """Test the stateful LanguageDetector with user caching."""

    def test_user_cache(self):
        detector = LanguageDetector()
        # First message in French
        lang = detector.detect("Bonjour, comment allez-vous? Je suis content", "user1")
        assert lang == "fr"
        # Short ambiguous message — should use cache
        lang = detector.detect("ok", "user1")
        assert lang == "fr"

    def test_set_user_language(self):
        detector = LanguageDetector()
        assert detector.set_user_language("user1", "ja") is True
        assert detector.get_user_language("user1") == "ja"
        assert detector.set_user_language("user1", "xx") is False

    def test_clear_user(self):
        detector = LanguageDetector()
        detector.set_user_language("user1", "ko")
        detector.clear_user("user1")
        assert detector.get_user_language("user1") == "en"


# ─── Language Prompt Tests ────────────────────────────────────

class TestLanguagePrompts:
    """Test prompt generation for different languages."""

    def test_english_no_instruction(self):
        prompt = get_language_prompt("en")
        assert prompt == ""

    def test_french_instruction(self):
        prompt = get_language_prompt("fr")
        assert "French" in prompt
        assert "Français" in prompt
        assert "Respond in French" in prompt

    def test_japanese_cultural_notes(self):
        notes = get_cultural_notes("ja")
        assert "polite" in notes.lower() or "です" in notes
        assert "formal" in notes.lower() or "casual" in notes.lower()

    def test_korean_cultural_notes(self):
        notes = get_cultural_notes("ko")
        assert "polite" in notes.lower() or "해요" in notes

    def test_arabic_cultural_notes(self):
        notes = get_cultural_notes("ar")
        assert "right-to-left" in notes.lower() or "RTL" in notes

    def test_build_multilingual_prompt(self):
        base = "You are Nori, a friendly companion."
        result = build_multilingual_system_prompt(base, "ja")
        assert base in result
        assert "Japanese" in result
        assert "LANGUAGE INSTRUCTION" in result

    def test_build_english_prompt_unchanged(self):
        base = "You are Nori, a friendly companion."
        result = build_multilingual_system_prompt(base, "en")
        assert result == base

    def test_unsupported_language_prompt(self):
        prompt = get_language_prompt("xx")
        assert prompt == ""


# ─── Language Module Tests ────────────────────────────────────

class TestLanguageModule:
    """Test the languages module utility functions."""

    def test_all_20_languages(self):
        assert len(SUPPORTED_LANGUAGES) == 20

    def test_get_language_name(self):
        assert get_language_name("en") == "English"
        assert get_language_name("ja") == "Japanese"
        assert get_language_name("xx") == "English"  # fallback

    def test_get_greeting(self):
        assert get_greeting("en") == "Hey!"
        assert get_greeting("ja") == "こんにちは!"
        assert get_greeting("xx") == "Hey!"  # fallback

    def test_is_supported(self):
        assert is_supported("en") is True
        assert is_supported("zh") is True
        assert is_supported("xx") is False

    def test_all_languages_have_fields(self):
        for code, lang in SUPPORTED_LANGUAGES.items():
            assert "name" in lang, f"{code} missing 'name'"
            assert "native" in lang, f"{code} missing 'native'"
            assert "greeting" in lang, f"{code} missing 'greeting'"


# ─── Hardcoded Response Language Matching ─────────────────────

class TestIdentityResponseLanguage:
    """Test that identity responses can be language-aware."""

    def test_english_identity_unchanged(self):
        """English identity responses should work as-is."""
        from nobi.i18n.detector import _detect_language_core
        # Simulate: user asks "who are you?" in English
        lang = _detect_language_core("who are you?")
        assert lang == "en"

    def test_chinese_question_detected(self):
        """Chinese identity question should be detected as Chinese."""
        from nobi.i18n.detector import _detect_language_core
        lang = _detect_language_core("你是谁？")
        assert lang == "zh"

    def test_japanese_question_detected(self):
        from nobi.i18n.detector import _detect_language_core
        lang = _detect_language_core("あなたは誰ですか？")
        assert lang == "ja"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
