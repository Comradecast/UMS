"""
Migration 013: Add dashboard fields to tournaments
---------------------------------------------------
Adds dashboard_channel_id and dashboard_message_id for the tournament dashboard.
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)


async def run(db: aiosqlite.Connection) -> None:
    """Add dashboard fields to tournaments table."""
    try:
        # Check existing columns
        cursor = await db.execute("PRAGMA table_info(tournaments)")
        columns = [row[1] for row in await cursor.fetchall()]

        # Add columns if missing
        if "dashboard_channel_id" not in columns:
            await db.execute(
                "ALTER TABLE tournaments ADD COLUMN dashboard_channel_id INTEGER"
            )
            log.info("[MIGRATION-013] Added dashboard_channel_id column")

        if "dashboard_message_id" not in columns:
            await db.execute(
                "ALTER TABLE tournaments ADD COLUMN dashboard_message_id INTEGER"
            )
            log.info("[MIGRATION-013] Added dashboard_message_id column")

        await db.commit()
        log.info("[MIGRATION-013] Tournament dashboard fields complete")

    except Exception as e:
        log.error(f"[MIGRATION-013] Failed: {e}")
        raise
