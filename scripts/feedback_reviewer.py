#!/usr/bin/env python3
"""
Daily Feedback Reviewer — Checks all feedback, generates report, 
auto-fixes what it can, and drafts replies.
Runs via cron daily at 08:00 UTC.
"""
import sqlite3
import json
import os
import sys
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.expanduser("~/.nobi/feedback.db")
REPORT_DIR = os.path.expanduser("~/.nobi/feedback_reports")

def get_db():
    if not os.path.exists(DB_PATH):
        print("No feedback database found.")
        return None
    return sqlite3.connect(DB_PATH)

def get_open_feedback():
    conn = get_db()
    if not conn:
        return []
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM feedback WHERE status = 'open' ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_feedback_since(hours=24):
    conn = get_db()
    if not conn:
        return []
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT * FROM feedback WHERE created_at > ? ORDER BY created_at ASC",
        (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_db()
    if not conn:
        return {}
    stats = {}
    stats['total'] = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    stats['open'] = conn.execute("SELECT COUNT(*) FROM feedback WHERE status='open'").fetchone()[0]
    stats['resolved'] = conn.execute("SELECT COUNT(*) FROM feedback WHERE status='resolved'").fetchone()[0]
    stats['in_progress'] = conn.execute("SELECT COUNT(*) FROM feedback WHERE status='in_progress'").fetchone()[0]
    
    # By category
    cats = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM feedback GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    stats['by_category'] = {r[0]: r[1] for r in cats}
    
    # By platform
    plats = conn.execute(
        "SELECT platform, COUNT(*) as cnt FROM feedback GROUP BY platform ORDER BY cnt DESC"
    ).fetchall()
    stats['by_platform'] = {r[0]: r[1] for r in plats}
    
    # Last 24h
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    stats['last_24h'] = conn.execute(
        "SELECT COUNT(*) FROM feedback WHERE created_at > ?", (cutoff,)
    ).fetchone()[0]
    
    conn.close()
    return stats

def generate_report():
    stats = get_stats()
    open_tickets = get_open_feedback()
    recent = get_all_feedback_since(24)
    
    report = []
    report.append(f"# 📋 Feedback Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    report.append("")
    report.append(f"## Summary")
    report.append(f"- **Total tickets:** {stats.get('total', 0)}")
    report.append(f"- **Open:** {stats.get('open', 0)}")
    report.append(f"- **In Progress:** {stats.get('in_progress', 0)}")
    report.append(f"- **Resolved:** {stats.get('resolved', 0)}")
    report.append(f"- **Last 24h:** {stats.get('last_24h', 0)}")
    report.append("")
    
    if stats.get('by_category'):
        report.append("## By Category")
        for cat, cnt in stats['by_category'].items():
            emoji = {'bug_report': '🐛', 'feature_request': '💡', 'complaint': '😤', 'question': '❓', 'general_feedback': '💬'}.get(cat, '📝')
            report.append(f"- {emoji} **{cat}:** {cnt}")
        report.append("")
    
    if stats.get('by_platform'):
        report.append("## By Platform")
        for plat, cnt in stats['by_platform'].items():
            report.append(f"- **{plat}:** {cnt}")
        report.append("")
    
    if open_tickets:
        report.append(f"## 🔴 Open Tickets ({len(open_tickets)})")
        for t in open_tickets:
            report.append(f"### #{t['id'][:12]}")
            report.append(f"- **Category:** {t['category']}")
            report.append(f"- **Platform:** {t['platform']}")
            report.append(f"- **User:** {t['user_id']}")
            report.append(f"- **Date:** {t['created_at']}")
            report.append(f"- **Message:** {t['message']}")
            report.append("")
    
    if recent:
        report.append(f"## 📨 Last 24h ({len(recent)} tickets)")
        for t in recent:
            status_emoji = {'open': '🔴', 'in_progress': '🟡', 'resolved': '✅'}.get(t['status'], '⚪')
            report.append(f"- {status_emoji} [{t['category']}] {t['message'][:80]}")
        report.append("")
    
    return "\n".join(report)

def save_report(report_text):
    os.makedirs(REPORT_DIR, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    path = os.path.join(REPORT_DIR, f"feedback-{date_str}.md")
    with open(path, 'w') as f:
        f.write(report_text)
    return path

if __name__ == "__main__":
    report = generate_report()
    path = save_report(report)
    print(report)
    print(f"\n📄 Report saved to: {path}")
