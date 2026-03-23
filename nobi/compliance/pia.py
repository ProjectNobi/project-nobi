"""
Project Nobi — Privacy Impact Assessment (PIA)
================================================
Documents all data processing activities for GDPR compliance review.

Generates a structured report covering:
- Data processing activities catalogue
- Data flow maps (data → storage → access → retention)
- Risk assessment
- Technical and organisational measures (TOMs)
- Data subject rights procedures

Output: structured dict (JSON-serialisable) or formatted text report.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

# ─── Data Processing Activities Catalogue ─────────────────────────────────────

PROCESSING_ACTIVITIES: List[Dict[str, Any]] = [
    {
        "id": "mem-001",
        "name": "Memory Storage",
        "description": "LLM-extracted facts, preferences, and events from user conversations",
        "legal_basis": "Consent (Art. 6(1)(a)) / Legitimate Interest (Art. 6(1)(f))",
        "data_categories": ["conversation content", "personal facts", "preferences", "emotional context"],
        "data_subjects": ["registered users"],
        "storage": {
            "location": "SQLite database on Bittensor miner nodes",
            "encryption": "AES-128 at rest (per-user key derivation)",
            "geographic_scope": "Distributed across Bittensor network (global)",
        },
        "access": ["miner operator (encrypted)", "user (decrypted via API)"],
        "retention": "12 months from last update (configurable)",
        "automated_decision_making": False,
        "third_party_sharing": False,
        "risk_level": "medium",
        "mitigation": "End-to-end encryption; user-controlled deletion; GDPR erasure endpoint",
    },
    {
        "id": "conv-001",
        "name": "Conversation History",
        "description": "Turn-by-turn conversation log for context window and analytics",
        "legal_basis": "Consent (Art. 6(1)(a))",
        "data_categories": ["messages", "timestamps", "user identifiers"],
        "data_subjects": ["registered users"],
        "storage": {
            "location": "SQLite on miner nodes and API server",
            "encryption": "AES-128 at rest",
            "geographic_scope": "Server region (Hetzner EU) + miner network",
        },
        "access": ["API server process", "user (via /export)"],
        "retention": "6 months (configurable)",
        "automated_decision_making": False,
        "third_party_sharing": False,
        "risk_level": "medium",
        "mitigation": "Retention scheduler; user erasure right; minimal logging",
    },
    {
        "id": "prof-001",
        "name": "User Profile",
        "description": "Aggregated personality summary and preference notes built from memories",
        "legal_basis": "Consent (Art. 6(1)(a))",
        "data_categories": ["personality traits", "behavioural patterns", "interests"],
        "data_subjects": ["registered users"],
        "storage": {
            "location": "SQLite on miner nodes",
            "encryption": "AES-128 at rest",
            "geographic_scope": "Miner network (global)",
        },
        "access": ["Nori inference process"],
        "retention": "12 months from last activity",
        "automated_decision_making": True,
        "automated_decision_notes": "Profile used to personalise AI responses (not binding decisions)",
        "third_party_sharing": False,
        "risk_level": "medium",
        "mitigation": "User can view (/memories), correct (rectification API), delete (/forget)",
    },
    {
        "id": "bill-001",
        "name": "Subscription & Usage Records",
        "description": "Subscription tier, daily usage counters, billing history",
        "legal_basis": "Contract (Art. 6(1)(b)) / Legal Obligation (Art. 6(1)(c))",
        "data_categories": ["usage metrics", "subscription status", "payment identifiers"],
        "data_subjects": ["registered users"],
        "storage": {
            "location": "SQLite on API server",
            "encryption": "Database-level encryption",
            "geographic_scope": "EU server",
        },
        "access": ["billing module", "Stripe (payment processor)"],
        "retention": "7 years (legal requirement for financial records)",
        "automated_decision_making": False,
        "third_party_sharing": True,
        "third_party_details": "Stripe Inc. (payment processor) — under DPA",
        "risk_level": "low",
        "mitigation": "Minimal data collection; Stripe PCI-compliant; DPA in place",
    },
    {
        "id": "feed-001",
        "name": "User Feedback",
        "description": "Bug reports, feature requests, satisfaction ratings",
        "legal_basis": "Consent (Art. 6(1)(a))",
        "data_categories": ["feedback text", "category", "user identifier", "timestamps"],
        "data_subjects": ["registered users"],
        "storage": {
            "location": "SQLite on API server",
            "encryption": "At-rest encryption",
            "geographic_scope": "EU server",
        },
        "access": ["support team"],
        "retention": "24 months",
        "automated_decision_making": False,
        "third_party_sharing": False,
        "risk_level": "low",
        "mitigation": "User can request deletion; feedback anonymised after 24 months",
    },
    {
        "id": "auth-001",
        "name": "Session Tokens / API Keys",
        "description": "Ephemeral session identifiers and API keys for authentication",
        "legal_basis": "Legitimate Interest (Art. 6(1)(f)) — security",
        "data_categories": ["hashed tokens", "creation timestamps", "IP address hash"],
        "data_subjects": ["registered users"],
        "storage": {
            "location": "In-memory and SQLite on API server",
            "encryption": "Tokens are hashed (SHA-256) before storage",
            "geographic_scope": "EU server",
        },
        "access": ["authentication middleware"],
        "retention": "Session tokens: 24 hours. API keys: until revoked.",
        "automated_decision_making": False,
        "third_party_sharing": False,
        "risk_level": "low",
        "mitigation": "Short-lived tokens; hashed storage; no plaintext retention",
    },
    {
        "id": "cons-001",
        "name": "Consent Records",
        "description": "GDPR consent choices and audit trail",
        "legal_basis": "Legal Obligation (Art. 7) — demonstrate consent",
        "data_categories": ["consent flags", "timestamps", "policy version", "IP hash"],
        "data_subjects": ["registered users"],
        "storage": {
            "location": "SQLite on API server",
            "encryption": "At-rest encryption",
            "geographic_scope": "EU server",
        },
        "access": ["compliance module"],
        "retention": "3 years after consent withdrawn (legal obligation to prove consent)",
        "automated_decision_making": False,
        "third_party_sharing": False,
        "risk_level": "low",
        "mitigation": "Minimal data; required by law; IP stored as hash only",
    },
]

# ─── Technical & Organisational Measures (TOMs) ────────────────────────────

TECHNICAL_MEASURES = [
    "AES-128 encryption at rest for all user memory data",
    "Per-user key derivation (PBKDF2) — keys not shared between users",
    "HTTPS/TLS for all API communication",
    "Session tokens are short-lived (24h) and stored as SHA-256 hashes",
    "Rate limiting on all public API endpoints",
    "No plaintext passwords stored (OAuth/token-based auth)",
    "Database access controlled via application layer only",
    "Memory data encrypted on miner nodes — miners cannot read user content",
    "Automated retention scheduler purges data per policy",
]

ORGANISATIONAL_MEASURES = [
    "Privacy by design: data minimisation principle applied at architecture level",
    "GDPR DSR procedures documented and automated",
    "30-day response SLA for all data subject requests (logged)",
    "All GDPR requests logged to immutable audit trail",
    "Data Processing Agreements (DPAs) with Stripe (payment processor)",
    "Bittensor miner operators cannot decrypt user data",
    "Security incident response procedure defined in SECURITY.md",
    "No sale of user data — ever",
    "Users can view, correct, export, and delete all their data via self-service",
]

# ─── Risk Assessment ──────────────────────────────────────────────────────────

RISKS = [
    {
        "id": "risk-001",
        "title": "Unauthorised access to memory database",
        "likelihood": "low",
        "impact": "high",
        "residual_risk": "low",
        "mitigation": "AES-128 encryption; access controls; no direct DB exposure",
    },
    {
        "id": "risk-002",
        "title": "Incomplete erasure leaving orphaned data",
        "likelihood": "medium",
        "impact": "high",
        "residual_risk": "low",
        "mitigation": "GDPRHandler.handle_erasure_request() deletes across all tables; audit log confirms completion",
    },
    {
        "id": "risk-003",
        "title": "Data subject request not fulfilled within 30 days",
        "likelihood": "low",
        "impact": "medium",
        "residual_risk": "low",
        "mitigation": "All DSRs timestamped; automated handlers respond immediately; audit log for monitoring",
    },
    {
        "id": "risk-004",
        "title": "Miner node data retention beyond policy",
        "likelihood": "medium",
        "impact": "medium",
        "residual_risk": "medium",
        "mitigation": "Retention policy applied on API server; miner sync purge endpoint planned for v2",
        "open_action": "Implement miner-side retention enforcement in v2",
    },
    {
        "id": "risk-005",
        "title": "Consent not re-obtained after policy change",
        "likelihood": "low",
        "impact": "medium",
        "residual_risk": "low",
        "mitigation": "Policy versioning in ConsentManager; list_users_needing_reconsent() API available",
    },
    {
        "id": "risk-006",
        "title": "Under-18 users accessing service",
        "likelihood": "medium",
        "impact": "high",
        "residual_risk": "medium",
        "mitigation": "Age verification flag in consent; ToS requires 18+; enforcement strengthened in v2",
        "open_action": "Implement age verification gate in onboarding flow",
    },
]


class PIAReport:
    """Generate Privacy Impact Assessment reports."""

    def __init__(self):
        self.generated_at = datetime.now(timezone.utc).isoformat()

    def generate(self) -> Dict[str, Any]:
        """Return the full PIA as a structured dict (JSON-serialisable)."""
        return {
            "document": "Privacy Impact Assessment",
            "project": "Project Nobi",
            "version": "1.0.0",
            "generated_at": self.generated_at,
            "controller": {
                "name": "Project Nobi",
                "contact": "privacy@projectnobi.ai",
                "dpo_contact": "privacy@projectnobi.ai",
            },
            "scope": (
                "This PIA covers all personal data processing activities in the "
                "Project Nobi AI companion system, including the Telegram bot (Nori), "
                "web application, API server, and Bittensor miner network."
            ),
            "processing_activities": PROCESSING_ACTIVITIES,
            "data_flows": self._data_flows(),
            "technical_measures": TECHNICAL_MEASURES,
            "organisational_measures": ORGANISATIONAL_MEASURES,
            "risk_assessment": RISKS,
            "data_subject_rights": self._dsr_procedures(),
            "open_actions": [r for r in RISKS if r.get("open_action")],
            "overall_risk": "medium",
            "recommendation": (
                "The system can proceed to production with the current controls in place. "
                "Open actions (miner-side retention, age verification gate) should be "
                "addressed before scaling to 10k+ users."
            ),
        }

    def _data_flows(self) -> List[Dict[str, Any]]:
        return [
            {
                "flow": "User message → Memory extraction",
                "data": "Conversation text",
                "source": "Telegram / Web App",
                "destination": "LLM (Chutes.ai) → MemoryManager → SQLite",
                "encryption": "TLS in transit; AES-128 at rest",
                "retention": "12 months",
            },
            {
                "flow": "Memory retrieval → Response generation",
                "data": "Decrypted memory context",
                "source": "MemoryManager SQLite",
                "destination": "LLM inference (in-memory only; not persisted)",
                "encryption": "Decrypted in application memory only",
                "retention": "Request lifetime only",
            },
            {
                "flow": "User export request → JSON download",
                "data": "All user memories + profile",
                "source": "MemoryManager",
                "destination": "User (HTTPS download)",
                "encryption": "TLS in transit",
                "retention": "Not stored after delivery",
            },
            {
                "flow": "Payment processing",
                "data": "User email (optional), subscription tier",
                "source": "Billing module",
                "destination": "Stripe Inc. (under DPA)",
                "encryption": "TLS; Stripe handles card data (PCI-DSS)",
                "retention": "7 years (legal)",
            },
        ]

    def _dsr_procedures(self) -> Dict[str, str]:
        return {
            "access_art15": "POST /api/v1/gdpr/access — automated, responds within 30 days",
            "erasure_art17": "POST /api/v1/gdpr/erasure — automated, immediate deletion with audit log",
            "portability_art20": "GET /api/v1/gdpr/export — JSON export, automated",
            "rectification_art16": "POST /api/v1/gdpr/rectify — user corrects specific memories",
            "restriction_art18": "POST /api/v1/gdpr/restrict — flags account, stops new processing",
            "objection_art21": "Email privacy@projectnobi.ai — manual review within 30 days",
            "complaint": "Users may lodge complaints with their national supervisory authority",
        }

    def to_json(self, indent: int = 2) -> str:
        """Return PIA as formatted JSON string."""
        return json.dumps(self.generate(), indent=indent, ensure_ascii=False)

    def to_text(self) -> str:
        """Return PIA as a human-readable text report."""
        data = self.generate()
        lines = [
            f"{'='*60}",
            f"PRIVACY IMPACT ASSESSMENT",
            f"Project Nobi — {data['generated_at']}",
            f"{'='*60}",
            "",
            "SCOPE",
            data["scope"],
            "",
            f"DATA CONTROLLER: {data['controller']['name']} <{data['controller']['contact']}>",
            "",
            "─" * 60,
            "PROCESSING ACTIVITIES",
            "─" * 60,
        ]
        for act in data["processing_activities"]:
            lines += [
                f"\n[{act['id']}] {act['name']}",
                f"  Legal basis: {act['legal_basis']}",
                f"  Data: {', '.join(act['data_categories'])}",
                f"  Storage: {act['storage']['location']}",
                f"  Retention: {act['retention']}",
                f"  Risk: {act['risk_level']}",
            ]

        lines += ["", "─" * 60, "RISK ASSESSMENT", "─" * 60]
        for risk in data["risk_assessment"]:
            lines.append(
                f"[{risk['id']}] {risk['title']} "
                f"| Residual: {risk['residual_risk']}"
            )

        lines += ["", "─" * 60, "RECOMMENDATION", "─" * 60, data["recommendation"], ""]
        return "\n".join(lines)
