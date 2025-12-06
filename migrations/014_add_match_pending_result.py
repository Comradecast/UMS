"""
Migration 014: Add pending result fields to matches
----------------------------------------------------
Adds pending_winner_entry_id and pending_reported_by for result confirmation.
When both players report, results are compared before finalizing.
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)


async def run(db: aiosqlite.Connection) -> None:
    """Add pending result fields to matches table."""
    try:
        # Check existing columns
        cursor = await db.execute("PRAGMA table_info(matches)")
        columns = [row[1] for row in await cursor.fetchall()]

        # Add columns if missing
        if "pending_winner_entry_id" not in columns:
            await db.execute(
                "ALTER TABLE matches ADD COLUMN pending_winner_entry_id INTEGER"
            )
            log.info("[MIGRATION-014] Added pending_winner_entry_id column")

        if "pending_reported_by" not in columns:
            await db.execute(
                "ALTER TABLE matches ADD COLUMN pending_reported_by INTEGER"
            )
            log.info("[MIGRATION-014] Added pending_reported_by column")

        await db.commit()
        log.info("[MIGRATION-014] Match pending result fields complete")

    except Exception as e:
        log.error(f"[MIGRATION-014] Failed: {e}")
        raise
