"""
Add standings_message_id column to tournaments table.

Revision ID: 008
Revises: 007
Create Date: 2025-12-04 10:14:00
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)

MIGRATION_VERSION = "008_add_standings_message_id"


async def run(db: aiosqlite.Connection) -> None:
    """Add standings_message_id column to tournaments table."""
    log.debug(f"Checking migration: {MIGRATION_VERSION}")

    # Check if column already exists
    async with db.execute("PRAGMA table_info(tournaments)") as cursor:
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "standings_message_id" in column_names:
            log.debug(
                f"Migration {MIGRATION_VERSION}: Column standings_message_id already exists, skipping."
            )
            return

        # Add the column
        await db.execute(
            "ALTER TABLE tournaments ADD COLUMN standings_message_id INTEGER"
        )
        await db.commit()
        log.info(
            f"Migration {MIGRATION_VERSION}: Added standings_message_id column to tournaments table."
        )
