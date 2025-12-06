"""
Migration 010: Recreate tournaments table with Core schema
----------------------------------------------------------
The old tournaments table uses TEXT key as primary key.
UMS Core needs INTEGER id as primary key.
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)


async def run(db: aiosqlite.Connection) -> None:
    """Recreate tournaments table with new schema if needed."""
    try:
        # Check current schema
        cursor = await db.execute("PRAGMA table_info(tournaments)")
        columns = {row[1]: row[2] for row in await cursor.fetchall()}

        # If 'id' column doesn't exist or 'key' exists, we need to migrate
        if "id" not in columns or "key" in columns:
            log.info("[MIGRATION-010] Recreating tournaments table with Core schema...")

            # Drop old tournaments table (data will be lost but that's expected for Core)
            await db.execute("DROP TABLE IF EXISTS tournaments")

            # Create new schema
            await db.execute(
                """
                CREATE TABLE tournaments (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id            INTEGER NOT NULL,
                    name                TEXT NOT NULL,
                    format              TEXT NOT NULL DEFAULT '1v1',
                    size                INTEGER NOT NULL DEFAULT 8,
                    status              TEXT NOT NULL DEFAULT 'draft',
                    reg_message_id      INTEGER,
                    reg_channel_id      INTEGER,
                    created_at          INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """
            )

            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_tournaments_guild_status ON tournaments(guild_id, status)"
            )

            log.info("[MIGRATION-010] tournaments table recreated with Core schema")

        # Also ensure tournament_entries exists
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tournament_entries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id   INTEGER NOT NULL,
                player1_id      INTEGER NOT NULL,
                player2_id      INTEGER,
                team_name       TEXT,
                seed            INTEGER,
                created_at      INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
            )
        """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_entries_tournament ON tournament_entries(tournament_id)"
        )

        # Ensure matches table exists
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id       INTEGER NOT NULL,
                round               INTEGER NOT NULL,
                match_index         INTEGER NOT NULL,
                entry1_id           INTEGER,
                entry2_id           INTEGER,
                winner_entry_id     INTEGER,
                score_text          TEXT,
                status              TEXT NOT NULL DEFAULT 'pending',
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
            )
        """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament_id)"
        )

        await db.commit()
        log.info("[MIGRATION-010] Core tournament schema complete")

    except Exception as e:
        log.error(f"[MIGRATION-010] Failed: {e}")
        raise
