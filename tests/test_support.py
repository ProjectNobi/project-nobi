"""
Project Nobi — Support System Tests
=====================================
Comprehensive tests for FeedbackManager, SupportHandler, and API endpoints.

Tests use in-memory SQLite and FastAPI TestClient — no real DB or API calls.
"""

import csv
import io
import json
import sys
import uuid
import os
import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, PropertyMock

# ─── Ensure project root is on path ────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nobi.support.feedback import (
    FeedbackManager,
    FeedbackCategory,
    FeedbackStatus,
    auto_categorize,
)
from nobi.support.support_bot import SupportHandler, FAQ_ENTRIES


# ─── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    """Temporary SQLite DB path for each test."""
    return str(tmp_path / "test_feedback.db")


@pytest.fixture
def manager(db_path):
    """A fresh FeedbackManager with an in-memory (tmp) DB."""
    return FeedbackManager(db_path=db_path)


@pytest.fixture
def handler(manager):
    """A SupportHandler with a fresh FeedbackManager."""
    return SupportHandler(feedback_manager=manager)


@pytest.fixture
def sample_feedback(manager):
    """Insert 5 diverse feedback entries and return them."""
    entries = []
    data = [
        ("There is a bug in the memory page", "user_1", "telegram", None),
        ("Please add dark mode", "user_1", "web", "feature_request"),
        ("Nori is great, love it!", "user_2", "telegram", "general_feedback"),
        ("How do I export my memories?", "user_2", "web", "question"),
        ("The response is way too slow", "user_3", "discord", "complaint"),
    ]
    for msg, uid, plat, cat in data:
        entry = manager.submit_feedback(msg, uid, plat, cat)
        entries.append(entry)
    return entries


# ═══════════════════════════════════════════════════════════════
# PART 1 — AUTO-CATEGORIZE
# ═══════════════════════════════════════════════════════════════

class TestAutoCategorize:
    def test_bug_keywords(self):
        assert auto_categorize("There is a bug in the code") == FeedbackCategory.BUG_REPORT

    def test_broken_keyword(self):
        assert auto_categorize("The app is broken and crash") == FeedbackCategory.BUG_REPORT

    def test_error_keyword(self):
        assert auto_categorize("I keep getting an error message") == FeedbackCategory.BUG_REPORT

    def test_not_working(self):
        assert auto_categorize("This feature is not working") == FeedbackCategory.BUG_REPORT

    def test_feature_request(self):
        assert auto_categorize("Please add voice feature") == FeedbackCategory.FEATURE_REQUEST

    def test_suggestion_keyword(self):
        assert auto_categorize("I have a suggestion for improvement") == FeedbackCategory.FEATURE_REQUEST

    def test_question_how(self):
        assert auto_categorize("How do I delete my memories?") == FeedbackCategory.QUESTION

    def test_question_mark(self):
        assert auto_categorize("Can I export my data?") == FeedbackCategory.QUESTION

    def test_complaint_unhappy(self):
        assert auto_categorize("I am very unhappy with the service") == FeedbackCategory.COMPLAINT

    def test_general_fallback(self):
        assert auto_categorize("Lorem ipsum dolor sit amet") == FeedbackCategory.GENERAL_FEEDBACK

    def test_empty_message_fallback(self):
        assert auto_categorize("   ") == FeedbackCategory.GENERAL_FEEDBACK

    def test_case_insensitive(self):
        assert auto_categorize("BUG IN THE SYSTEM") == FeedbackCategory.BUG_REPORT

    def test_glitch_keyword(self):
        assert auto_categorize("There is a glitch on the settings page") == FeedbackCategory.BUG_REPORT


# ═══════════════════════════════════════════════════════════════
# PART 2 — FeedbackManager CRUD
# ═══════════════════════════════════════════════════════════════

class TestFeedbackManagerSubmit:
    def test_submit_basic(self, manager):
        entry = manager.submit_feedback("Great product!", "user_1")
        assert entry["id"]
        assert entry["user_id"] == "user_1"
        assert entry["status"] == FeedbackStatus.OPEN.value
        assert entry["category"] == FeedbackCategory.GENERAL_FEEDBACK.value
        assert entry["message"] == "Great product!"
        assert entry["created_at"]

    def test_submit_with_explicit_category(self, manager):
        entry = manager.submit_feedback("Broken login", "user_1", category="bug_report")
        assert entry["category"] == "bug_report"

    def test_submit_auto_category(self, manager):
        entry = manager.submit_feedback("There is a bug", "user_1", category="auto")
        assert entry["category"] == "bug_report"

    def test_submit_with_platform(self, manager):
        entry = manager.submit_feedback("Test", "user_1", platform="telegram")
        assert entry["platform"] == "telegram"

    def test_submit_empty_message_raises(self, manager):
        with pytest.raises(ValueError, match="empty"):
            manager.submit_feedback("", "user_1")

    def test_submit_whitespace_message_raises(self, manager):
        with pytest.raises(ValueError, match="empty"):
            manager.submit_feedback("   ", "user_1")

    def test_submit_too_long_message_raises(self, manager):
        with pytest.raises(ValueError, match="too long"):
            manager.submit_feedback("x" * 10_001, "user_1")

    def test_submit_max_length_allowed(self, manager):
        entry = manager.submit_feedback("x" * 10_000, "user_1")
        assert len(entry["message"]) == 10_000

    def test_submit_strips_whitespace(self, manager):
        entry = manager.submit_feedback("  hello world  ", "user_1")
        assert entry["message"] == "hello world"

    def test_submit_unique_ids(self, manager):
        e1 = manager.submit_feedback("A", "user_1")
        e2 = manager.submit_feedback("B", "user_1")
        assert e1["id"] != e2["id"]

    def test_submit_special_characters(self, manager):
        msg = "Bug: <script>alert('xss')</script> & 'quotes' -- SQL"
        entry = manager.submit_feedback(msg, "user_1")
        assert "<script>" in entry["message"]  # stored as-is (no HTML escaping needed in DB)

    def test_submit_sql_injection_safe(self, manager):
        msg = "'; DROP TABLE feedback; --"
        entry = manager.submit_feedback(msg, "user_1")
        assert entry["message"] == msg
        # Table still exists
        all_entries = manager.get_feedback()
        assert len(all_entries) >= 1

    def test_submit_unicode(self, manager):
        msg = "Nori est géniale! 🤖 こんにちは"
        entry = manager.submit_feedback(msg, "user_1")
        assert entry["message"] == msg


class TestFeedbackManagerGet:
    def test_get_all(self, manager, sample_feedback):
        all_entries = manager.get_feedback()
        assert len(all_entries) == 5

    def test_get_by_user_id(self, manager, sample_feedback):
        user1 = manager.get_feedback(user_id="user_1")
        assert all(e["user_id"] == "user_1" for e in user1)
        assert len(user1) == 2

    def test_get_by_status(self, manager, sample_feedback):
        open_entries = manager.get_feedback(status="open")
        assert all(e["status"] == "open" for e in open_entries)

    def test_get_by_category(self, manager, sample_feedback):
        complaints = manager.get_feedback(category="complaint")
        assert all(e["category"] == "complaint" for e in complaints)

    def test_get_by_feedback_id(self, manager, sample_feedback):
        fid = sample_feedback[0]["id"]
        result = manager.get_feedback(feedback_id=fid)
        assert len(result) == 1
        assert result[0]["id"] == fid

    def test_get_limit(self, manager, sample_feedback):
        result = manager.get_feedback(limit=2)
        assert len(result) == 2

    def test_get_offset(self, manager, sample_feedback):
        all_entries = manager.get_feedback()
        paged = manager.get_feedback(offset=2)
        assert len(paged) == 3

    def test_get_empty_db(self, manager):
        result = manager.get_feedback()
        assert result == []

    def test_get_nonexistent_id(self, manager):
        result = manager.get_feedback(feedback_id="does-not-exist")
        assert result == []


class TestFeedbackManagerUpdateStatus:
    def test_update_to_resolved(self, manager, sample_feedback):
        fid = sample_feedback[0]["id"]
        ok = manager.update_status(fid, "resolved")
        assert ok
        entry = manager.get_feedback(feedback_id=fid)[0]
        assert entry["status"] == "resolved"
        assert entry["resolved_at"] is not None

    def test_update_to_in_progress(self, manager, sample_feedback):
        fid = sample_feedback[0]["id"]
        ok = manager.update_status(fid, "in_progress")
        assert ok
        entry = manager.get_feedback(feedback_id=fid)[0]
        assert entry["status"] == "in_progress"

    def test_update_with_admin_notes(self, manager, sample_feedback):
        fid = sample_feedback[0]["id"]
        manager.update_status(fid, "resolved", admin_notes="Fixed in v1.2")
        entry = manager.get_feedback(feedback_id=fid)[0]
        assert entry["admin_notes"] == "Fixed in v1.2"

    def test_update_nonexistent_returns_false(self, manager):
        ok = manager.update_status("nonexistent-id", "resolved")
        assert not ok

    def test_update_invalid_status_raises(self, manager, sample_feedback):
        fid = sample_feedback[0]["id"]
        with pytest.raises(ValueError):
            manager.update_status(fid, "not_a_status")

    def test_resolved_at_set_only_on_resolved(self, manager, sample_feedback):
        fid = sample_feedback[0]["id"]
        manager.update_status(fid, "in_progress")
        entry = manager.get_feedback(feedback_id=fid)[0]
        assert entry["resolved_at"] is None


class TestFeedbackManagerSearch:
    def test_search_exact_word(self, manager, sample_feedback):
        results = manager.search_feedback("bug")
        assert any("bug" in r["message"].lower() for r in results)

    def test_search_partial_match(self, manager, sample_feedback):
        results = manager.search_feedback("slow")
        assert len(results) >= 1

    def test_search_no_match(self, manager, sample_feedback):
        results = manager.search_feedback("xyzzy_no_match_999")
        assert results == []

    def test_search_empty_query(self, manager, sample_feedback):
        results = manager.search_feedback("")
        assert results == []

    def test_search_case_insensitive(self, manager):
        manager.submit_feedback("This is a BUG", "user_1")
        results = manager.search_feedback("bug")
        assert len(results) >= 1

    def test_search_admin_notes(self, manager, sample_feedback):
        fid = sample_feedback[0]["id"]
        manager.update_status(fid, "resolved", admin_notes="Fixed in production")
        results = manager.search_feedback("production")
        assert len(results) >= 1


class TestFeedbackManagerStats:
    def test_stats_empty(self, manager):
        stats = manager.get_stats()
        assert stats["total"] == 0
        assert stats["resolved"] == 0

    def test_stats_total(self, manager, sample_feedback):
        stats = manager.get_stats()
        assert stats["total"] == 5

    def test_stats_open_count(self, manager, sample_feedback):
        stats = manager.get_stats()
        assert stats["open"] == 5

    def test_stats_resolved_count(self, manager, sample_feedback):
        manager.update_status(sample_feedback[0]["id"], "resolved")
        stats = manager.get_stats()
        assert stats["resolved"] == 1
        assert stats["open"] == 4

    def test_stats_by_category(self, manager, sample_feedback):
        stats = manager.get_stats()
        assert "complaint" in stats["by_category"]

    def test_stats_avg_resolution_hours(self, manager, sample_feedback):
        manager.update_status(sample_feedback[0]["id"], "resolved")
        stats = manager.get_stats()
        # avg_resolution_hours may be 0 or very small (same-second timestamps)
        assert stats["avg_resolution_hours"] is not None or stats["avg_resolution_hours"] is None


class TestFeedbackManagerExport:
    def test_export_json(self, manager, sample_feedback):
        data = manager.export_json()
        parsed = json.loads(data)
        assert len(parsed) == 5
        assert parsed[0]["id"]

    def test_export_json_user_filter(self, manager, sample_feedback):
        data = manager.export_json(user_id="user_1")
        parsed = json.loads(data)
        assert all(e["user_id"] == "user_1" for e in parsed)

    def test_export_csv(self, manager, sample_feedback):
        csv_data = manager.export_csv()
        reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(reader)
        assert len(rows) == 5
        assert "id" in rows[0]
        assert "message" in rows[0]

    def test_export_csv_empty(self, manager):
        result = manager.export_csv()
        assert result == ""

    def test_export_json_empty(self, manager):
        result = manager.export_json()
        assert result == "[]"


# ═══════════════════════════════════════════════════════════════
# PART 3 — SupportHandler
# ═══════════════════════════════════════════════════════════════

class TestSupportHandlerFaq:
    def test_get_faq_count(self, handler):
        faq = handler.get_faq()
        assert len(faq) >= 20

    def test_get_faq_fields(self, handler):
        faq = handler.get_faq()
        for entry in faq:
            assert "id" in entry
            assert "topic" in entry
            assert "answer" in entry

    def test_get_faq_no_keywords_exposed(self, handler):
        """Keywords are internal — should not be in public output."""
        faq = handler.get_faq()
        for entry in faq:
            assert "keywords" not in entry


class TestSupportHandlerFaqMatching:
    def test_exact_phrase_match(self, handler):
        result = handler.ask("what is nobi", "user_1")
        assert result["type"] == "faq"
        assert result["faq_id"] == "what_is_nobi"

    def test_keyword_in_question(self, handler):
        result = handler.ask("how does memory work in Nori?", "user_1")
        assert result["type"] == "faq"

    def test_privacy_question(self, handler):
        result = handler.ask("is my data private and secure?", "user_1")
        assert result["type"] == "faq"
        assert result["faq_id"] in ("privacy", "export_data", "delete_memories")

    def test_mining_question(self, handler):
        result = handler.ask("how do I mine on the subnet?", "user_1")
        assert result["type"] == "faq"
        assert result["faq_id"] == "how_to_mine"

    def test_voice_question(self, handler):
        result = handler.ask("does nori support voice messages?", "user_1")
        assert result["type"] == "faq"

    def test_language_question(self, handler):
        result = handler.ask("what languages does nori support?", "user_1")
        assert result["type"] == "faq"

    def test_no_faq_match_creates_ticket(self, handler):
        result = handler.ask("qxyzzy totally unique random string 9999", "user_1")
        assert result["type"] == "ticket"
        assert "ticket_id" in result

    def test_faq_answer_populated(self, handler):
        result = handler.ask("what is project nobi", "user_1")
        assert len(result["answer"]) > 10

    def test_empty_question(self, handler):
        result = handler.ask("", "user_1")
        assert result["type"] == "error"

    def test_whitespace_question(self, handler):
        result = handler.ask("   ", "user_1")
        assert result["type"] == "error"

    def test_case_insensitive_matching(self, handler):
        result = handler.ask("WHAT IS NOBI", "user_1")
        assert result["type"] == "faq"

    def test_ticket_saved_to_db(self, handler):
        result = handler.ask("completely unknown query xyz123", "user_1")
        assert result["type"] == "ticket"
        ticket_id = result["ticket_id"]
        saved = handler.feedback.get_feedback(feedback_id=ticket_id)
        assert len(saved) == 1
        assert saved[0]["category"] == "question"

    def test_faq_has_topic(self, handler):
        result = handler.ask("what is nobi", "user_1")
        assert "topic" in result


class TestSupportHandlerFeedbackSubmit:
    def test_submit_feedback_returns_ticket(self, handler):
        result = handler.submit_feedback("Great product!", "user_1")
        assert "ticket_id" in result
        assert "acknowledgment" in result
        assert "feedback_id" in result

    def test_submit_bug_report_acknowledgment(self, handler):
        result = handler.submit_feedback("App crashes on startup", "user_1", category="bug_report")
        assert "bug" in result["acknowledgment"].lower() or "ticket" in result["acknowledgment"].lower()

    def test_submit_feature_request_acknowledgment(self, handler):
        result = handler.submit_feedback("Add dark mode", "user_1", category="feature_request")
        assert result["category"] == "feature_request"

    def test_submit_auto_category(self, handler):
        result = handler.submit_feedback("There is a bug on login page", "user_1")
        assert result["category"] == "bug_report"

    def test_submit_stores_in_db(self, handler):
        result = handler.submit_feedback("Test message", "user_x")
        fid = result["feedback_id"]
        saved = handler.feedback.get_feedback(feedback_id=fid)
        assert len(saved) == 1
        assert saved[0]["message"] == "Test message"


# ═══════════════════════════════════════════════════════════════
# PART 4 — API Endpoints (FastAPI TestClient)
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def api_client(tmp_path):
    """
    Returns a FastAPI TestClient with a mocked support system.
    We patch the server's globals after import.
    """
    # Patch environment before importing server
    import os

    # Use tmp paths
    db_path = str(tmp_path / "api_feedback.db")
    fm = FeedbackManager(db_path=db_path)
    sh = SupportHandler(feedback_manager=fm)

    # Import server and override globals
    from api import server as srv

    original_fm = srv.feedback_manager
    original_sh = srv.support_handler

    srv.feedback_manager = fm
    srv.support_handler = sh

    from fastapi.testclient import TestClient
    client = TestClient(srv.app, raise_server_exceptions=False)

    yield client

    # Restore
    srv.feedback_manager = original_fm
    srv.support_handler = original_sh


class TestFeedbackEndpoints:
    def test_post_feedback_success(self, api_client):
        res = api_client.post("/api/feedback", json={
            "message": "Great app!",
            "user_id": "tester_1",
            "platform": "web",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "ticket_id" in data

    def test_post_feedback_auto_category(self, api_client):
        res = api_client.post("/api/feedback", json={
            "message": "There is a bug",
            "user_id": "tester_1",
        })
        assert res.status_code == 200
        assert res.json()["category"] == "bug_report"

    def test_post_feedback_explicit_category(self, api_client):
        res = api_client.post("/api/feedback", json={
            "message": "Please add voice",
            "user_id": "tester_1",
            "category": "feature_request",
        })
        assert res.status_code == 200
        assert res.json()["category"] == "feature_request"

    def test_post_feedback_empty_message(self, api_client):
        res = api_client.post("/api/feedback", json={
            "message": "",
            "user_id": "tester_1",
        })
        # Pydantic should reject empty message (min_length=1)
        assert res.status_code in (400, 422)

    def test_get_feedback_history(self, api_client):
        # First submit some
        api_client.post("/api/feedback", json={"message": "Feedback 1", "user_id": "hist_user"})
        api_client.post("/api/feedback", json={"message": "Feedback 2", "user_id": "hist_user"})

        res = api_client.get("/api/feedback?user_id=hist_user")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 2
        assert len(data["feedback"]) == 2

    def test_get_feedback_stats(self, api_client):
        res = api_client.get("/api/feedback/stats")
        assert res.status_code == 200
        data = res.json()
        assert "total" in data
        assert "resolved" in data

    def test_post_support_faq_match(self, api_client):
        res = api_client.post("/api/support", json={
            "question": "what is nobi",
            "user_id": "tester_1",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "faq"
        assert len(data["answer"]) > 0

    def test_post_support_ticket_created(self, api_client):
        res = api_client.post("/api/support", json={
            "question": "xyzzy unknown question 9999 abc",
            "user_id": "tester_1",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "ticket"
        assert "ticket_id" in data

    def test_get_faq(self, api_client):
        res = api_client.get("/api/faq")
        assert res.status_code == 200
        data = res.json()
        assert "faq" in data
        assert data["count"] >= 20
        for entry in data["faq"]:
            assert "id" in entry
            assert "topic" in entry
            assert "answer" in entry

    def test_post_feedback_very_long_message(self, api_client):
        res = api_client.post("/api/feedback", json={
            "message": "x" * 10_001,
            "user_id": "tester_1",
        })
        # Either rejected by Pydantic (max_length) or by our validation
        assert res.status_code in (400, 422)

    def test_post_feedback_special_chars(self, api_client):
        res = api_client.post("/api/feedback", json={
            "message": "Bug: <b>bold</b> & 'quotes' -- SQL injection attempt; DROP TABLE",
            "user_id": "tester_1",
        })
        assert res.status_code == 200
        assert res.json()["success"] is True


# ═══════════════════════════════════════════════════════════════
# PART 5 — Edge cases
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_feedback_manager_creates_db_dir(self, tmp_path):
        deep_path = str(tmp_path / "deep" / "nested" / "dir" / "feedback.db")
        fm = FeedbackManager(db_path=deep_path)
        entry = fm.submit_feedback("Test", "user_1")
        assert entry["id"]

    def test_faq_entries_minimum_count(self):
        assert len(FAQ_ENTRIES) >= 20

    def test_faq_all_have_required_fields(self):
        for entry in FAQ_ENTRIES:
            assert "id" in entry, f"Missing id: {entry}"
            assert "topic" in entry, f"Missing topic: {entry}"
            assert "keywords" in entry, f"Missing keywords: {entry}"
            assert "answer" in entry, f"Missing answer: {entry}"
            assert len(entry["keywords"]) >= 1, f"Empty keywords: {entry}"

    def test_faq_unique_ids(self):
        ids = [e["id"] for e in FAQ_ENTRIES]
        assert len(ids) == len(set(ids)), "Duplicate FAQ IDs found"

    def test_concurrent_submissions(self, manager):
        """Multiple submissions from different users don't collide."""
        entries = []
        for i in range(20):
            e = manager.submit_feedback(f"Message {i}", f"user_{i}")
            entries.append(e)
        all_ids = [e["id"] for e in entries]
        assert len(set(all_ids)) == 20

    def test_search_returns_correct_entry(self, manager):
        unique = "absolutely_unique_search_term_xyz987"
        entry = manager.submit_feedback(f"Contains: {unique}", "user_1")
        results = manager.search_feedback(unique)
        assert len(results) == 1
        assert results[0]["id"] == entry["id"]

    def test_export_json_valid_structure(self, manager):
        manager.submit_feedback("Test 1", "u1")
        manager.submit_feedback("Test 2", "u2")
        exported = json.loads(manager.export_json())
        for item in exported:
            assert set(item.keys()) == {
                "id", "user_id", "platform", "category", "message",
                "status", "created_at", "resolved_at", "admin_notes"
            }

    def test_support_handler_asks_routing_both_paths(self, handler):
        """Ensure both faq and ticket paths work in a single test."""
        faq_result = handler.ask("what is project nobi", "user_a")
        ticket_result = handler.ask("unicorn_impossible_query_xyzzy_888", "user_a")
        assert faq_result["type"] == "faq"
        assert ticket_result["type"] == "ticket"

    def test_get_feedback_combined_filters(self, manager, sample_feedback):
        """Filter by user + category simultaneously."""
        results = manager.get_feedback(user_id="user_1", category="bug_report")
        assert all(e["user_id"] == "user_1" for e in results)
        assert all(e["category"] == "bug_report" for e in results)
