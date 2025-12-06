"""
Migration 009: Add channel_created tracking columns to guild_config
-------------------------------------------------------------------
Adds columns to track which channels were created by the bot
so factory reset can delete only bot-created channels.
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)


async def run(db: aiosqlite.Connection) -> None:
    """Add channel_created tracking columns to guild_config."""
    try:
        # Check if columns exist
        cursor = await db.execute("PRAGMA table_info(guild_config)")
        columns = [row[1] for row in await cursor.fetchall()]

        # Add columns if missing
        if "onboarding_channel_created" not in columns:
            await db.execute(
                "ALTER TABLE guild_config ADD COLUMN onboarding_channel_created INTEGER DEFAULT 0"
            )
            log.info("[MIGRATION-009] Added onboarding_channel_created column")

        if "admin_channel_created" not in columns:
            await db.execute(
                "ALTER TABLE guild_config ADD COLUMN admin_channel_created INTEGER DEFAULT 0"
            )
            log.info("[MIGRATION-009] Added admin_channel_created column")

        if "announce_channel_created" not in columns:
            await db.execute(
                "ALTER TABLE guild_config ADD COLUMN announce_channel_created INTEGER DEFAULT 0"
            )
            log.info("[MIGRATION-009] Added announce_channel_created column")

        await db.commit()

    except Exception as e:
        log.error(f"[MIGRATION-009] Failed: {e}")
        raise
