"""
create match_participants table

Revision ID: 004
Revises: 003
Create Date: 2025-12-03 19:40:00

"""

import aiosqlite

MIGRATION_VERSION = "004_create_match_participants"


async def apply(db: aiosqlite.Connection):
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS match_participants (
            id              INTEGER PRIMARY KEY,
            match_id        INTEGER NOT NULL,
            player_id       INTEGER NOT NULL,
            team_number     INTEGER NOT NULL
        )
    """
    )
    await db.commit()


async def rollback(db: aiosqlite.Connection):
    await db.execute("DROP TABLE IF EXISTS match_participants")
    await db.commit()


async def run(db: aiosqlite.Connection) -> None:
    """Entry point for migration runner."""
    await apply(db)
