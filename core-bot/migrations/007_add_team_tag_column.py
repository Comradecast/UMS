"""
Add team_tag column to teams table.

Revision ID: 007
Revises: 006
Create Date: 2025-12-03 21:20:00
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)

MIGRATION_VERSION = "007_add_team_tag_column"


async def run(db: aiosqlite.Connection) -> None:
    """Add team_tag column to teams table."""
    log.debug(f"Checking migration: {MIGRATION_VERSION}")

    # Check if column already exists
    async with db.execute("PRAGMA table_info(teams)") as cursor:
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "team_tag" in column_names:
            log.debug(
                f"Migration {MIGRATION_VERSION}: Column team_tag already exists, skipping."
            )
            return

        # Add the column
        await db.execute("ALTER TABLE teams ADD COLUMN team_tag TEXT")
        await db.commit()
        log.info(
            f"Migration {MIGRATION_VERSION}: Added team_tag column to teams table."
        )
