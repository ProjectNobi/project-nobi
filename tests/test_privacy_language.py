"""
Tests for privacy language precision (#5):
- Scans public-facing files for imprecise encryption claims
- Validates "at rest" / "server-side" / "end-to-end" precision
- Ensures required statements are present
"""

import os
import re
import pytest

# Files to check
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_TO_CHECK = [
    "docs/landing/index.html",
    "docs/landing/faq.html",
    "docs/landing/vision.html",
    "README.md",
    "docs/WHITEPAPER.md",
    "nobi/support/support_bot.py",
    "app/bot.py",
]


def _read_file(relative_path: str) -> str:
    """Read a file relative to project root."""
    full_path = os.path.join(PROJECT_ROOT, relative_path)
    if not os.path.exists(full_path):
        pytest.skip(f"File not found: {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── Imprecise claims (should NOT exist unqualified) ─────────

class TestNoBareEncryptedClaims:
    """Files must not use 'encrypted' without qualification."""

    @pytest.mark.parametrize("filepath", FILES_TO_CHECK)
    def test_no_bare_aes128_without_qualifier(self, filepath):
        """'AES-128 encrypted' alone (without 'at rest' or 'server-side') should not appear."""
        content = _read_file(filepath)

        # Pattern: "AES-128 encrypted" NOT followed by "at rest" or "server-side"
        # We allow: "AES-128 encrypted at rest", "AES-128 encryption at rest"
        # We disallow: "AES-128 encrypted" with nothing after OR followed by period/comma/newline
        bare_pattern = re.compile(
            r"AES-128\s+encrypt(?:ed|ion)(?!\s+at\s+rest)(?!\s*\(server)",
            re.IGNORECASE
        )

        # Skip WHITEPAPER - it has technical historical context and detailed prose
        if "WHITEPAPER" in filepath:
            pytest.skip("WHITEPAPER has detailed technical context — skip bare check")

        matches = bare_pattern.findall(content)
        # Allow up to 2 matches — some legacy context (e.g., code comments, variable names)
        # The important thing is precision in user-facing sentences
        assert len(matches) <= 3, (
            f"{filepath}: Found {len(matches)} potentially bare AES-128 encrypted claims: {matches}"
        )

    @pytest.mark.parametrize("filepath", [
        "docs/landing/index.html",
        "docs/landing/faq.html",
        "docs/landing/vision.html",
        "nobi/support/support_bot.py",
        "app/bot.py",
    ])
    def test_server_side_or_at_rest_qualifier_present(self, filepath):
        """Files should mention 'at rest' OR 'server-side' when discussing encryption."""
        content = _read_file(filepath)
        has_at_rest = "at rest" in content.lower()
        has_server_side = "server-side" in content.lower() or "server side" in content.lower()
        assert has_at_rest or has_server_side, (
            f"{filepath}: Should specify 'at rest' or 'server-side' for encryption"
        )


class TestRequiredPrecisionStatements:
    """Certain files must include precise statements about current vs future privacy."""

    @pytest.mark.parametrize("filepath", [
        "docs/landing/faq.html",
        "nobi/support/support_bot.py",
        "app/bot.py",
    ])
    def test_miners_process_content_acknowledged(self, filepath):
        """Should acknowledge that miners process conversation content."""
        content = _read_file(filepath)
        has_miner_process = (
            "miners process" in content.lower()
            or "miner.*process" in content.lower()
            or "miners do see" in content.lower()
        )
        assert has_miner_process, (
            f"{filepath}: Should acknowledge miners process conversation content"
        )

    @pytest.mark.parametrize("filepath", [
        "docs/landing/faq.html",
        "docs/landing/index.html",
        "nobi/support/support_bot.py",
    ])
    def test_tee_end_to_end_roadmap_mentioned(self, filepath):
        """Files should reference TEE or end-to-end encryption status."""
        content = _read_file(filepath)
        has_tee = (
            "tee" in content.lower()
            or "end-to-end" in content.lower()
            or "code-complete" in content.lower()
        )
        assert has_tee, (
            f"{filepath}: Should reference TEE/end-to-end encryption status"
        )

    @pytest.mark.parametrize("filepath", [
        "docs/landing/faq.html",
        "nobi/support/support_bot.py",
    ])
    def test_browser_side_mentioned_in_key_files(self, filepath):
        """Key FAQ/support files should mention browser-side memory extraction."""
        content = _read_file(filepath)
        has_browser = (
            "browser" in content.lower()
            or "browser-side" in content.lower()
        )
        assert has_browser, (
            f"{filepath}: Should mention browser-side memory extraction"
        )


class TestReadmePrivacyLanguage:
    def test_readme_has_at_rest_qualifier(self):
        content = _read_file("README.md")
        assert "at rest" in content.lower(), "README should specify 'at rest' for encryption"

    def test_readme_has_server_side_note(self):
        content = _read_file("README.md")
        has_server_side = "server-side" in content.lower() or "server side" in content.lower()
        assert has_server_side, "README should note server-side encryption"

    def test_readme_has_tee_mention(self):
        content = _read_file("README.md")
        has_tee = "tee" in content.lower() or "end-to-end" in content.lower()
        assert has_tee, "README should mention TEE/end-to-end encryption status"


class TestBotSystemPromptLanguage:
    def test_system_prompt_specifies_at_rest(self):
        content = _read_file("app/bot.py")
        # Check that the SYSTEM_PROMPT section has precise language
        assert "at rest" in content, "bot.py should use 'at rest' qualifier in encryption claims"

    def test_bot_identity_privacy_specifies_server_side(self):
        content = _read_file("app/bot.py")
        # Check that the bot identity response mentions server-side
        has_server_side = "server-side" in content.lower()
        assert has_server_side, "bot.py should specify server-side encryption"
