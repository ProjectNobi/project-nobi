#!/usr/bin/env python3
"""
Project Nobi — Encrypt Existing Memories Migration
====================================================
Encrypts all existing plaintext memories in SQLite databases.
Run once after deploying Privacy Phase A encryption.

Handles:
  - Bot DB: ~/.nobi/bot_memories.db
  - Miner DB: ~/.nobi/memories.db

Usage:
  python3 scripts/encrypt_existing_memories.py [--dry-run]
"""

import os
import sys
import sqlite3
import argparse
import logging

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.memory.encryption import (
    encrypt_memory,
    is_encrypted,
    ensure_master_secret,
)

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("encrypt-migration")


def encrypt_table(conn: sqlite3.Connection, table: str, dry_run: bool = False) -> tuple:
    """
    Encrypt all plaintext content in a table.
    Returns (encrypted_count, skipped_count, error_count).
    """
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        f"SELECT id, user_id, content FROM {table}"
    ).fetchall()

    total = len(rows)
    encrypted = 0
    skipped = 0
    errors = 0

    for i, row in enumerate(rows):
        content = row["content"]
        user_id = row["user_id"]
        row_id = row["id"]

        # Skip already-encrypted content
        if is_encrypted(content):
            skipped += 1
            continue

        try:
            encrypted_content = encrypt_memory(user_id, content)

            # Verify it actually encrypted (not returned as plaintext)
            if encrypted_content == content:
                logger.warning(f"  [{table}] Row {row_id}: encryption returned plaintext (key issue?)")
                errors += 1
                continue

            if not dry_run:
                conn.execute(
                    f"UPDATE {table} SET content = ? WHERE id = ?",
                    (encrypted_content, row_id),
                )

            encrypted += 1
        except Exception as e:
            logger.error(f"  [{table}] Row {row_id}: {e}")
            errors += 1

        # Progress update every 100 rows
        if (i + 1) % 100 == 0:
            logger.info(f"  [{table}] Progress: {i + 1}/{total}")

    if not dry_run:
        conn.commit()

    return encrypted, skipped, errors


def encrypt_conversations(conn: sqlite3.Connection, dry_run: bool = False) -> tuple:
    """
    Encrypt all plaintext conversation content.
    Conversations use auto-increment integer IDs.
    Returns (encrypted_count, skipped_count, error_count).
    """
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, user_id, content FROM conversations"
    ).fetchall()

    total = len(rows)
    encrypted = 0
    skipped = 0
    errors = 0

    for i, row in enumerate(rows):
        content = row["content"]
        user_id = row["user_id"]
        row_id = row["id"]

        if is_encrypted(content):
            skipped += 1
            continue

        try:
            encrypted_content = encrypt_memory(user_id, content)

            if encrypted_content == content:
                logger.warning(f"  [conversations] Row {row_id}: encryption returned plaintext")
                errors += 1
                continue

            if not dry_run:
                conn.execute(
                    "UPDATE conversations SET content = ? WHERE id = ?",
                    (encrypted_content, row_id),
                )

            encrypted += 1
        except Exception as e:
            logger.error(f"  [conversations] Row {row_id}: {e}")
            errors += 1

        if (i + 1) % 100 == 0:
            logger.info(f"  [conversations] Progress: {i + 1}/{total}")

    if not dry_run:
        conn.commit()

    return encrypted, skipped, errors


def process_db(db_path: str, dry_run: bool = False):
    """Process a single database file."""
    expanded = os.path.expanduser(db_path)
    if not os.path.exists(expanded):
        logger.info(f"Database not found: {expanded} — skipping")
        return

    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {expanded}")
    logger.info(f"{'='*60}")

    conn = sqlite3.connect(expanded)
    conn.execute("PRAGMA journal_mode=WAL")

    # Check which tables exist
    tables = [
        row[0] for row in
        conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    ]

    # Encrypt memories table
    if "memories" in tables:
        logger.info(f"\n📦 Encrypting memories table...")
        enc, skip, err = encrypt_table(conn, "memories", dry_run)
        logger.info(f"  ✅ Encrypted: {enc} | ⏭️ Already encrypted: {skip} | ❌ Errors: {err}")

    # Encrypt archived_memories table
    if "archived_memories" in tables:
        logger.info(f"\n📦 Encrypting archived_memories table...")
        enc, skip, err = encrypt_table(conn, "archived_memories", dry_run)
        logger.info(f"  ✅ Encrypted: {enc} | ⏭️ Already encrypted: {skip} | ❌ Errors: {err}")

    # Encrypt conversations table
    if "conversations" in tables:
        logger.info(f"\n💬 Encrypting conversations table...")
        enc, skip, err = encrypt_conversations(conn, dry_run)
        logger.info(f"  ✅ Encrypted: {enc} | ⏭️ Already encrypted: {skip} | ❌ Errors: {err}")

    conn.close()
    logger.info(f"\n✅ Done: {expanded}")


def main():
    parser = argparse.ArgumentParser(description="Encrypt existing Nobi memories")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be encrypted without making changes",
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Path to a specific database file (overrides default paths)",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("🔍 DRY RUN — no changes will be made\n")

    # Ensure master secret exists
    secret = ensure_master_secret()
    if not secret:
        logger.error("❌ No encryption secret available! Set NOBI_ENCRYPTION_SECRET or run the bot first.")
        sys.exit(1)

    logger.info("🔐 Encryption secret loaded\n")

    if args.db:
        process_db(args.db, args.dry_run)
    else:
        # Process both standard database locations
        process_db("~/.nobi/bot_memories.db", args.dry_run)
        process_db("~/.nobi/memories.db", args.dry_run)

    logger.info("\n🎉 Migration complete!")
    if args.dry_run:
        logger.info("   (This was a dry run — no data was modified)")


if __name__ == "__main__":
    main()
