"""
Content Safety Filter
=====================
Checks user messages and bot responses for safety issues.
Adds disclaimers automatically or refuses with helpful redirects.
Keeps an audit log for compliance.

Usage:
    from nobi.safety import ContentFilter

    cf = ContentFilter()
    decision = cf.check_user_message(user_id, message_text)
    if not decision.is_safe:
        return decision.response  # pre-built safe response

    response = generate_response(...)
    final = cf.check_bot_response(user_id, message_text, response)
    return final.response  # may have disclaimers appended
"""

import re
import os
import json
import logging
import sqlite3
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("nobi-safety")

SAFETY_DB_PATH = os.environ.get("NOBI_SAFETY_DB_PATH", "~/.nobi/safety.db")


class SafetyLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"          # Add disclaimer but allow
    BLOCKED = "blocked"          # Refuse with redirect
    CRITICAL = "critical"        # Refuse + log for review


@dataclass
class SafetyDecision:
    """Result of a content safety check."""
    is_safe: bool
    level: SafetyLevel
    category: str                # e.g. "self_harm", "medical_advice"
    response: str                # Final response to send (may be modified/replaced)
    original_response: str       # Original before any modification
    action_taken: str            # "allowed", "disclaimer_added", "blocked", "redirected"
    flags: list = field(default_factory=list)  # Which patterns triggered


# ─── Pattern Library ─────────────────────────────────────────

# Self-harm patterns — detect risk, respond with care + resources
_SELF_HARM_PATTERNS = [
    r"\b(want to|going to|planning to|thinking about|considering).{0,30}(kill myself|end my life|commit suicide|take my (own )?life)\b",
    r"\b(suicide|suicidal|self.harm|self.hurt|cutting myself|want to die|wish i was dead)\b",
    r"\b(hurt myself|harming myself|don't want to live|no reason to live|better off dead)\b",
    r"\bhow (do i|to).{0,20}(kill myself|end my life|commit suicide)\b",
]

# Child exploitation patterns — always block, zero tolerance
_CSAM_PATTERNS = [
    r"\b(child|minor|underage|kid|teen|boy|girl).{0,40}(sexual|nude|naked|explicit|erotic|porn)\b",
    r"\b(sexual|nude|naked|explicit).{0,40}(child|minor|underage|kid|teen)\b",
    r"\b(csam|cp|child porn|loli|shota)\b",
]

# Extreme violence patterns — block or disclaim
_EXTREME_VIOLENCE_PATTERNS = [
    r"\b(how to|instructions for|steps to|guide to).{0,30}(make a bomb|build a weapon|building a weapon|create explosives|mass shooting|attack a)\b",
    r"\b(bomb making|explosives recipe|chemical weapons|biological weapons|nerve agent|ricin|anthrax)\b",
    r"\b(killing spree|mass murder|terrorist attack|how to attack)\b",
]

# Illegal activity patterns
_ILLEGAL_PATTERNS = [
    r"\b(how to|teach me|help me).{0,20}(hack|break into|steal|defraud|launder money|traffic)\b",
    r"\b(drug synthesis|make meth|cook meth|cook heroin|synthesize fentanyl)\b",
    r"\b(how to traffick|human trafficking|child trafficking)\b",
]

# ─── Response Disclaimer Templates ───────────────────────────

_MEDICAL_DISCLAIMER = (
    "\n\n⚠️ Important: I'm an AI companion, not a medical professional. "
    "This information is general and not a substitute for professional medical advice. "
    "Please consult a qualified healthcare provider for medical decisions."
)

_MENTAL_HEALTH_DISCLAIMER = (
    "\n\n💙 If you're going through something difficult, please consider reaching out to "
    "a mental health professional. In the UK: Samaritans 116 123. "
    "In the US: Crisis Text Line — text HOME to 741741."
)

_FINANCIAL_DISCLAIMER = (
    "\n\n⚠️ Note: I'm an AI companion, not a regulated financial advisor. "
    "Nothing I say constitutes financial advice. "
    "Please consult a qualified financial professional before making investment decisions."
)

_LEGAL_DISCLAIMER = (
    "\n\n⚠️ Note: I'm an AI companion, not a solicitor or attorney. "
    "Nothing I say constitutes legal advice. "
    "Please consult a qualified lawyer for matters with legal implications."
)

# Medical topic keywords in bot responses
_MEDICAL_RESPONSE_KEYWORDS = [
    "diagnosis", "diagnose", "symptoms", "treatment", "medication", "dosage",
    "prescription", "disease", "condition", "disorder", "therapy", "surgery",
    "take this drug", "you should take", "recommended dose", "side effects",
]

_FINANCIAL_RESPONSE_KEYWORDS = [
    "invest in", "buy stock", "sell stock", "you should invest", "financial advice",
    "portfolio", "trading strategy", "buy bitcoin", "sell crypto", "put your money",
    "guaranteed return", "investment opportunity",
]

_LEGAL_RESPONSE_KEYWORDS = [
    "you should sue", "legal action", "file a lawsuit", "your rights are",
    "under the law you", "legally speaking", "consult a lawyer",
]

# Mental health keywords in user messages
_MENTAL_HEALTH_KEYWORDS = [
    "feeling depressed", "i'm depressed", "struggling with anxiety", "panic attack",
    "i feel empty", "i feel hopeless", "nothing matters", "feeling really low",
    "mental health", "therapy", "therapist", "psychiatrist",
]


# ─── ContentFilter Class ─────────────────────────────────────

class ContentFilter:
    """
    Production-grade content safety filter for Nori.

    Checks:
      - User messages: self-harm, CSAM, extreme violence, illegal requests
      - Bot responses: medical/financial/legal advice without disclaimers

    Logs all flagged interactions for audit.
    """

    def __init__(self, db_path: str = SAFETY_DB_PATH, log_safe: bool = False):
        """
        Args:
            db_path: Path to SQLite database for safety audit log.
            log_safe: If True, also log safe interactions (verbose mode).
        """
        self.db_path = os.path.expanduser(db_path)
        self.log_safe = log_safe
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """Initialise the safety audit log database."""
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS safety_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                direction   TEXT NOT NULL,    -- 'user' or 'bot'
                level       TEXT NOT NULL,    -- SafetyLevel value
                category    TEXT NOT NULL,
                action      TEXT NOT NULL,
                flags       TEXT,             -- JSON list of triggered patterns
                message_snippet TEXT,         -- First 200 chars (no PII)
                platform    TEXT DEFAULT 'unknown'
            )
        """)
        self._conn.commit()

    def _log(
        self,
        user_id: str,
        direction: str,
        level: SafetyLevel,
        category: str,
        action: str,
        flags: list,
        message_snippet: str,
        platform: str = "unknown",
    ):
        """Write a safety event to the audit log."""
        if not self._conn:
            return
        try:
            ts = datetime.now(timezone.utc).isoformat()
            snippet = message_snippet[:200] if message_snippet else ""
            self._conn.execute(
                """INSERT INTO safety_log (ts, user_id, direction, level, category, action, flags, message_snippet, platform)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ts, user_id, direction, level.value, category, action, json.dumps(flags), snippet, platform),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning(f"[Safety] Log write error: {e}")

    @staticmethod
    def _match_patterns(text: str, patterns: list) -> list:
        """Return list of pattern strings that match the text (case-insensitive)."""
        text_lower = text.lower()
        triggered = []
        for p in patterns:
            try:
                if re.search(p, text_lower, re.IGNORECASE | re.DOTALL):
                    triggered.append(p)
            except re.error:
                pass
        return triggered

    # ─── User Message Checks ─────────────────────────────────

    def check_user_message(
        self,
        user_id: str,
        message: str,
        platform: str = "unknown",
    ) -> SafetyDecision:
        """
        Check a user message for safety issues.

        Returns a SafetyDecision. If is_safe is False, use decision.response
        as the reply to the user instead of generating a normal response.
        """

        # 1. CSAM — highest severity, zero tolerance
        csam_flags = self._match_patterns(message, _CSAM_PATTERNS)
        if csam_flags:
            logger.critical(f"[Safety] CSAM detected from user {user_id}")
            self._log(user_id, "user", SafetyLevel.CRITICAL, "csam",
                      "blocked", csam_flags, message, platform)
            return SafetyDecision(
                is_safe=False,
                level=SafetyLevel.CRITICAL,
                category="csam",
                response=(
                    "I can't help with that. Content involving minors in a sexual context "
                    "is strictly prohibited and may be illegal. "
                    "This interaction has been flagged."
                ),
                original_response="",
                action_taken="blocked",
                flags=csam_flags,
            )

        # 2. Self-harm — respond with care + crisis resources
        harm_flags = self._match_patterns(message, _SELF_HARM_PATTERNS)
        if harm_flags:
            logger.warning(f"[Safety] Self-harm signals from user {user_id}")
            self._log(user_id, "user", SafetyLevel.CRITICAL, "self_harm",
                      "redirected", harm_flags, message, platform)
            return SafetyDecision(
                is_safe=False,
                level=SafetyLevel.CRITICAL,
                category="self_harm",
                response=(
                    "I'm really glad you reached out. What you're feeling sounds really heavy, "
                    "and I want you to know you're not alone. 💙\n\n"
                    "Please reach out to someone who can truly help right now:\n"
                    "🇬🇧 Samaritans: 116 123 (free, 24/7)\n"
                    "🇺🇸 988 Suicide & Crisis Lifeline: call or text 988\n"
                    "🌍 Crisis Text Line: text HOME to 741741\n\n"
                    "If you're in immediate danger, please call emergency services (999 / 911).\n\n"
                    "I'm here to talk too — please don't go through this alone."
                ),
                original_response="",
                action_taken="redirected",
                flags=harm_flags,
            )

        # 3. Extreme violence / weapons
        violence_flags = self._match_patterns(message, _EXTREME_VIOLENCE_PATTERNS)
        if violence_flags:
            logger.warning(f"[Safety] Extreme violence request from user {user_id}")
            self._log(user_id, "user", SafetyLevel.BLOCKED, "extreme_violence",
                      "blocked", violence_flags, message, platform)
            return SafetyDecision(
                is_safe=False,
                level=SafetyLevel.BLOCKED,
                category="extreme_violence",
                response=(
                    "I'm not able to help with that. I can't provide instructions for "
                    "weapons, explosives, or violence. If you're working on a creative "
                    "project, I'm happy to help in a different way."
                ),
                original_response="",
                action_taken="blocked",
                flags=violence_flags,
            )

        # 4. Illegal activities
        illegal_flags = self._match_patterns(message, _ILLEGAL_PATTERNS)
        if illegal_flags:
            logger.warning(f"[Safety] Illegal activity request from user {user_id}")
            self._log(user_id, "user", SafetyLevel.BLOCKED, "illegal",
                      "blocked", illegal_flags, message, platform)
            return SafetyDecision(
                is_safe=False,
                level=SafetyLevel.BLOCKED,
                category="illegal",
                response=(
                    "I can't help with that. I'm not able to assist with illegal activities. "
                    "Is there something else I can help you with?"
                ),
                original_response="",
                action_taken="blocked",
                flags=illegal_flags,
            )

        # 5. Mental health discussion — safe, but flag for potential disclaimer in response
        mh_flags = [kw for kw in _MENTAL_HEALTH_KEYWORDS if kw in message.lower()]
        if mh_flags:
            # Allowed — but note that the response should be gentle
            if self.log_safe:
                self._log(user_id, "user", SafetyLevel.WARNING, "mental_health",
                          "allowed_with_note", mh_flags, message, platform)
            return SafetyDecision(
                is_safe=True,
                level=SafetyLevel.WARNING,
                category="mental_health",
                response="",  # Will be filled by normal generation
                original_response="",
                action_taken="allowed",
                flags=mh_flags,
            )

        # All clear
        if self.log_safe:
            self._log(user_id, "user", SafetyLevel.SAFE, "none",
                      "allowed", [], message, platform)
        return SafetyDecision(
            is_safe=True,
            level=SafetyLevel.SAFE,
            category="none",
            response="",
            original_response="",
            action_taken="allowed",
            flags=[],
        )

    # ─── Bot Response Checks ─────────────────────────────────

    def check_bot_response(
        self,
        user_id: str,
        user_message: str,
        bot_response: str,
        platform: str = "unknown",
    ) -> SafetyDecision:
        """
        Check a bot response for safety issues.

        Priority order:
          1. CSAM in response → CRITICAL: block entirely, replace with safe refusal
          2. Self-harm content in response → CRITICAL: block, replace with crisis resources
          3. Extreme violence / illegal instructions in response → BLOCKED: replace with refusal
          4. Unqualified professional advice → WARNING: append disclaimer
        """
        if not bot_response:
            return SafetyDecision(
                is_safe=True, level=SafetyLevel.SAFE, category="none",
                response=bot_response, original_response=bot_response,
                action_taken="allowed", flags=[],
            )

        # ── 1. CSAM in bot response — zero tolerance, block entirely ──────────
        csam_flags = self._match_patterns(bot_response, _CSAM_PATTERNS)
        if csam_flags:
            logger.critical(f"[Safety] CSAM detected in bot response for user {user_id} — BLOCKING")
            self._log(user_id, "bot", SafetyLevel.CRITICAL, "csam",
                      "blocked", csam_flags, bot_response, platform)
            return SafetyDecision(
                is_safe=False,
                level=SafetyLevel.CRITICAL,
                category="csam",
                response=(
                    "I can't send that response. Content involving minors in a sexual context "
                    "is strictly prohibited. This incident has been flagged for review."
                ),
                original_response=bot_response,
                action_taken="blocked",
                flags=csam_flags,
            )

        # ── 2. Self-harm instructions/encouragement in bot response ────────────
        # Only trigger if the response contains actionable harm guidance (not crisis support)
        # Use a targeted sub-pattern list to avoid blocking our own crisis resources
        _RESPONSE_SELF_HARM_PATTERNS = [
            r"\b(here('s| is) how (to|you can).{0,40}(kill yourself|end your life|commit suicide))\b",
            r"\b(step[s]? (to|for).{0,30}(self.harm|suicide|kill yourself))\b",
            r"\b(best way to (kill yourself|end your life|commit suicide|self.harm))\b",
            r"\b(you should (kill yourself|end your life|hurt yourself))\b",
            r"\b(try (killing yourself|ending your life|self.harming))\b",
        ]
        harm_flags = self._match_patterns(bot_response, _RESPONSE_SELF_HARM_PATTERNS)
        if harm_flags:
            logger.critical(f"[Safety] Self-harm instructions in bot response for user {user_id} — BLOCKING")
            self._log(user_id, "bot", SafetyLevel.CRITICAL, "self_harm",
                      "blocked", harm_flags, bot_response, platform)
            return SafetyDecision(
                is_safe=False,
                level=SafetyLevel.CRITICAL,
                category="self_harm",
                response=(
                    "I'm not the right help for this. Please reach out to someone who can truly help:\n"
                    "🇬🇧 Samaritans: 116 123 (free, 24/7)\n"
                    "🇺🇸 988 Suicide & Crisis Lifeline: call or text 988\n"
                    "🌍 Crisis Text Line: text HOME to 741741\n\n"
                    "If you're in immediate danger, please call emergency services (999 / 911). 💙"
                ),
                original_response=bot_response,
                action_taken="blocked",
                flags=harm_flags,
            )

        # ── 3. Extreme violence / weapons instructions in bot response ──────────
        # Additional patterns for response-side instruction text (no "how to" prefix needed)
        _RESPONSE_VIOLENCE_PATTERNS = _EXTREME_VIOLENCE_PATTERNS + [
            r"\b(to (make|build|create|assemble).{0,20}(bomb|explosive|weapon)).{0,30}(step|first|gather|mix|here)\b",
            r"\b(first,? gather.{0,40}(explosive|bomb|weapon))\b",
            r"\b(step \d+.{0,30}(bomb|explosive|weapon|poison))\b",
            r"\bhere('s| is) (how|what).{0,30}(bomb|explosive|kill|attack|poison)\b",
            r"\b(ingredients.{0,30}(bomb|explosive)|mix.{0,30}explosive|assemble.{0,20}bomb)\b",
        ]
        violence_flags = self._match_patterns(bot_response, _RESPONSE_VIOLENCE_PATTERNS)
        if violence_flags:
            logger.warning(f"[Safety] Extreme violence content in bot response for user {user_id} — BLOCKING")
            self._log(user_id, "bot", SafetyLevel.BLOCKED, "extreme_violence",
                      "blocked", violence_flags, bot_response, platform)
            return SafetyDecision(
                is_safe=False,
                level=SafetyLevel.BLOCKED,
                category="extreme_violence",
                response=(
                    "I can't send that response — it contains content I'm not able to share. "
                    "Is there something else I can help with?"
                ),
                original_response=bot_response,
                action_taken="blocked",
                flags=violence_flags,
            )

        # ── 4. Illegal activity instructions in bot response ───────────────────
        illegal_flags = self._match_patterns(bot_response, _ILLEGAL_PATTERNS)
        if illegal_flags:
            logger.warning(f"[Safety] Illegal content in bot response for user {user_id} — BLOCKING")
            self._log(user_id, "bot", SafetyLevel.BLOCKED, "illegal",
                      "blocked", illegal_flags, bot_response, platform)
            return SafetyDecision(
                is_safe=False,
                level=SafetyLevel.BLOCKED,
                category="illegal",
                response=(
                    "I can't send that response — it involves assistance I'm not able to provide. "
                    "Is there something else I can help with?"
                ),
                original_response=bot_response,
                action_taken="blocked",
                flags=illegal_flags,
            )

        response_lower = bot_response.lower()
        disclaimers_to_add = []
        categories = []
        all_flags = []

        # Check for medical advice
        medical_flags = [kw for kw in _MEDICAL_RESPONSE_KEYWORDS if kw in response_lower]
        if medical_flags:
            disclaimers_to_add.append(_MEDICAL_DISCLAIMER)
            categories.append("medical_advice")
            all_flags.extend(medical_flags)

        # Check for financial advice
        financial_flags = [kw for kw in _FINANCIAL_RESPONSE_KEYWORDS if kw in response_lower]
        if financial_flags:
            disclaimers_to_add.append(_FINANCIAL_DISCLAIMER)
            categories.append("financial_advice")
            all_flags.extend(financial_flags)

        # Check for legal advice
        legal_flags = [kw for kw in _LEGAL_RESPONSE_KEYWORDS if kw in response_lower]
        if legal_flags:
            disclaimers_to_add.append(_LEGAL_DISCLAIMER)
            categories.append("legal_advice")
            all_flags.extend(legal_flags)

        # Check user message for mental health context — add resource line to response
        mh_user_flags = self._match_patterns(user_message, _SELF_HARM_PATTERNS)
        mh_keyword_flags = [kw for kw in _MENTAL_HEALTH_KEYWORDS if kw in user_message.lower()]
        if mh_user_flags or mh_keyword_flags:
            disclaimers_to_add.append(_MENTAL_HEALTH_DISCLAIMER)
            categories.append("mental_health")
            all_flags.extend(mh_user_flags or mh_keyword_flags)

        if disclaimers_to_add:
            # Deduplicate disclaimers
            seen = set()
            unique_disclaimers = []
            for d in disclaimers_to_add:
                if d not in seen:
                    seen.add(d)
                    unique_disclaimers.append(d)

            modified_response = bot_response + "".join(unique_disclaimers)
            category_str = ", ".join(set(categories))
            logger.info(f"[Safety] Disclaimer added to bot response for user {user_id}: {category_str}")
            self._log(user_id, "bot", SafetyLevel.WARNING, category_str,
                      "disclaimer_added", all_flags, bot_response, platform)
            return SafetyDecision(
                is_safe=True,
                level=SafetyLevel.WARNING,
                category=category_str,
                response=modified_response,
                original_response=bot_response,
                action_taken="disclaimer_added",
                flags=all_flags,
            )

        if self.log_safe:
            self._log(user_id, "bot", SafetyLevel.SAFE, "none",
                      "allowed", [], bot_response, platform)
        return SafetyDecision(
            is_safe=True,
            level=SafetyLevel.SAFE,
            category="none",
            response=bot_response,
            original_response=bot_response,
            action_taken="allowed",
            flags=[],
        )

    # ─── Audit Queries ────────────────────────────────────────

    def get_safety_log(
        self,
        limit: int = 100,
        user_id: Optional[str] = None,
        level: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list:
        """Retrieve safety log entries for audit."""
        if not self._conn:
            return []
        query = "SELECT * FROM safety_log WHERE 1=1"
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if level:
            query += " AND level = ?"
            params.append(level)
        if category:
            query += " AND category LIKE ?"
            params.append(f"%{category}%")
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        try:
            rows = self._conn.execute(query, params).fetchall()
            cols = [d[0] for d in self._conn.execute(query, params).description] if rows else [
                "id", "ts", "user_id", "direction", "level", "category",
                "action", "flags", "message_snippet", "platform"
            ]
            return [dict(zip(cols, row)) for row in rows]
        except Exception as e:
            logger.warning(f"[Safety] Log read error: {e}")
            return []

    def get_stats(self) -> dict:
        """Get summary statistics from the safety log."""
        if not self._conn:
            return {}
        try:
            total = self._conn.execute("SELECT COUNT(*) FROM safety_log").fetchone()[0]
            by_level = dict(self._conn.execute(
                "SELECT level, COUNT(*) FROM safety_log GROUP BY level"
            ).fetchall())
            by_category = dict(self._conn.execute(
                "SELECT category, COUNT(*) FROM safety_log GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10"
            ).fetchall())
            by_action = dict(self._conn.execute(
                "SELECT action, COUNT(*) FROM safety_log GROUP BY action"
            ).fetchall())
            return {
                "total_events": total,
                "by_level": by_level,
                "by_category": by_category,
                "by_action": by_action,
            }
        except Exception as e:
            logger.warning(f"[Safety] Stats error: {e}")
            return {}

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# ─── Module-level singleton ───────────────────────────────────

_default_filter: Optional[ContentFilter] = None


def get_filter() -> ContentFilter:
    """Get (or create) the module-level singleton content filter."""
    global _default_filter
    if _default_filter is None:
        _default_filter = ContentFilter()
    return _default_filter
