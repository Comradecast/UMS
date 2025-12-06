"""
Migration 011: Add allowed_regions and allowed_ranks to tournaments
--------------------------------------------------------------------
Adds optional restriction columns for tournament registration.
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)


async def run(db: aiosqlite.Connection) -> None:
    """Add allowed_regions and allowed_ranks columns to tournaments."""
    try:
        # Check if columns exist
        cursor = await db.execute("PRAGMA table_info(tournaments)")
        columns = [row[1] for row in await cursor.fetchall()]

        # Add columns if missing
        if "allowed_regions" not in columns:
            await db.execute("ALTER TABLE tournaments ADD COLUMN allowed_regions TEXT")
            log.info("[MIGRATION-011] Added allowed_regions column")

        if "allowed_ranks" not in columns:
            await db.execute("ALTER TABLE tournaments ADD COLUMN allowed_ranks TEXT")
            log.info("[MIGRATION-011] Added allowed_ranks column")

        await db.commit()

    except Exception as e:
        log.error(f"[MIGRATION-011] Failed: {e}")
        raise
