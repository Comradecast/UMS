"""
Migration 012: Add archive fields to tournaments
-------------------------------------------------
Adds winner_player_id, runner_up_player_id, completed_at for trophy preservation.
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)


async def run(db: aiosqlite.Connection) -> None:
    """Add archive fields to tournaments table."""
    try:
        # Check existing columns
        cursor = await db.execute("PRAGMA table_info(tournaments)")
        columns = [row[1] for row in await cursor.fetchall()]

        # Add columns if missing
        if "winner_player_id" not in columns:
            await db.execute(
                "ALTER TABLE tournaments ADD COLUMN winner_player_id INTEGER"
            )
            log.info("[MIGRATION-012] Added winner_player_id column")

        if "runner_up_player_id" not in columns:
            await db.execute(
                "ALTER TABLE tournaments ADD COLUMN runner_up_player_id INTEGER"
            )
            log.info("[MIGRATION-012] Added runner_up_player_id column")

        if "completed_at" not in columns:
            await db.execute("ALTER TABLE tournaments ADD COLUMN completed_at INTEGER")
            log.info("[MIGRATION-012] Added completed_at column")

        await db.commit()
        log.info("[MIGRATION-012] Tournament archive fields complete")

    except Exception as e:
        log.error(f"[MIGRATION-012] Failed: {e}")
        raise
