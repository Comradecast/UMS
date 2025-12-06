"""
create matches_unified table

Revision ID: 003
Revises: 002
Create Date: 2025-12-03 19:35:00

"""

import aiosqlite

MIGRATION_VERSION = "003_create_matches_unified"


async def apply(db: aiosqlite.Connection):
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS matches_unified (
            id              INTEGER PRIMARY KEY,
            guild_id        INTEGER NOT NULL,
            mode            TEXT NOT NULL,
            source          TEXT NOT NULL,
            team1_score     INTEGER NOT NULL,
            team2_score     INTEGER NOT NULL,
            winner_team     INTEGER,
            created_at      INTEGER NOT NULL,
            completed_at    INTEGER
        )
    """
    )
    await db.commit()


async def rollback(db: aiosqlite.Connection):
    await db.execute("DROP TABLE IF EXISTS matches_unified")
    await db.commit()


async def run(db: aiosqlite.Connection) -> None:
    """Entry point for migration runner."""
    await apply(db)
