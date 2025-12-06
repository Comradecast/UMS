"""
add status column to matches_unified

Revision ID: 005
Revises: 004
Create Date: 2025-12-03 19:53:00

"""

import aiosqlite

MIGRATION_VERSION = "005_add_match_status"


async def apply(db: aiosqlite.Connection):
    """Add status column to matches_unified with default 'COMPLETED'."""
    # Check if column already exists (idempotent)
    async with db.execute("PRAGMA table_info(matches_unified)") as cursor:
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "status" not in column_names:
            await db.execute(
                """
                ALTER TABLE matches_unified
                ADD COLUMN status TEXT NOT NULL DEFAULT 'COMPLETED'
            """
            )
            await db.commit()


async def rollback(db: aiosqlite.Connection):
    """
    Remove status column from matches_unified.
    Note: SQLite doesn't support DROP COLUMN in older versions,
    so this would require table recreation. For now, we document
    that rollback is not fully supported for this migration.
    """
    # SQLite ALTER TABLE DROP COLUMN is only available in 3.35.0+
    # For production, consider table recreation if needed
    pass


async def run(db: aiosqlite.Connection) -> None:
    """Entry point for migration runner."""
    await apply(db)
