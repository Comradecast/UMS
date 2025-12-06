"""
Migration 002: Add v3 columns to players table

This migration adds columns to the players table to prepare for consolidation
of the legacy rank table and players_new. No behavior changes - services continue using
the legacy table until a future migration switches the read path.

Columns added:
- Elo ratings (per-mode Elo columns for 1v1, 2v2, 3v3)
- Provisional counters (per-mode provisional game tracking)
- Rank verification (rank_locked, rank_label, rank, verified)
- Extended stats (total_wins, total_losses, streaks, etc.)
- Queue management (queue_leaves, queue_banned_until)
- Smurf detection (smurf_flagged, smurf_flagged_at)

SAFE: Idempotent, can be run multiple times
"""

import logging
import aiosqlite

log = logging.getLogger(__name__)

MIGRATION_VERSION = "002_add_players_v3_columns"


async def check_if_migration_needed(db: aiosqlite.Connection) -> bool:
    """Check if this migration has already been applied."""
    try:
        # Check if schema_migrations table exists
        async with db.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_migrations'
            """
        ) as cursor:
            if not await cursor.fetchone():
                # Create migration tracking table
                await db.execute(
                    """
                    CREATE TABLE schema_migrations (
                        version   TEXT PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                    """
                )
                await db.commit()

        # Check if this migration was already applied
        async with db.execute(
            """
            SELECT version FROM schema_migrations WHERE version = ?
            """,
            (MIGRATION_VERSION,),
        ) as cursor:
            if await cursor.fetchone():
                log.debug(f"Migration {MIGRATION_VERSION} already applied, skipping.")
                return False

        return True

    except Exception as e:
        log.error(f"Error checking migration status: {e}", exc_info=True)
        return False


async def add_column_if_not_exists(
    db: aiosqlite.Connection, table: str, column: str, column_def: str
) -> None:
    """Add a column to a table if it doesn't already exist."""
    try:
        # Check if column exists
        async with db.execute(f"PRAGMA table_info({table})") as cursor:
            columns = [row[1] async for row in cursor]

        if column in columns:
            log.debug(f"  Column {column} already exists, skipping")
            return

        # Add the column
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
        log.info(f"  ✅ Added column: {column}")

    except Exception as e:
        log.error(f"Error adding column {column}: {e}", exc_info=True)
        raise


async def migrate(db: aiosqlite.Connection) -> bool:
    """
    Add v3 columns to the players table.

    Returns:
        True if migration succeeded, False otherwise
    """
    try:
        # Check if migration is needed
        if not await check_if_migration_needed(db):
            return True

        log.info("=" * 60)
        log.info(f"Starting migration: {MIGRATION_VERSION}")
        log.info("=" * 60)

        # Add Elo rating columns
        log.info("Adding Elo rating columns...")
        await add_column_if_not_exists(db, "players", "elo_1v1", "INTEGER DEFAULT 1000")
        await add_column_if_not_exists(db, "players", "elo_2v2", "INTEGER DEFAULT 1000")
        await add_column_if_not_exists(db, "players", "elo_3v3", "INTEGER DEFAULT 1000")

        # Add provisional game counters
        log.info("Adding provisional game counters...")
        await add_column_if_not_exists(
            db, "players", "provisional_games_1v1", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(
            db, "players", "provisional_games_2v2", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(
            db, "players", "provisional_games_3v3", "INTEGER DEFAULT 0"
        )

        # Add rank verification columns
        log.info("Adding rank verification columns...")
        await add_column_if_not_exists(
            db, "players", "rank_locked", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(db, "players", "rank_label", "TEXT")
        await add_column_if_not_exists(db, "players", "rank", "TEXT")
        await add_column_if_not_exists(db, "players", "verified", "INTEGER DEFAULT 0")

        # Add extended stats
        log.info("Adding extended stats columns...")
        await add_column_if_not_exists(db, "players", "total_wins", "INTEGER DEFAULT 0")
        await add_column_if_not_exists(
            db, "players", "total_losses", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(
            db, "players", "current_win_streak", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(
            db, "players", "best_win_streak", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(
            db, "players", "tournaments_won", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(
            db, "players", "last_tournament_at", "INTEGER DEFAULT 0"
        )

        # Add queue management columns
        log.info("Adding queue management columns...")
        await add_column_if_not_exists(
            db, "players", "queue_leaves", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(db, "players", "queue_banned_until", "INTEGER")

        # Add smurf detection columns
        log.info("Adding smurf detection columns...")
        await add_column_if_not_exists(
            db, "players", "smurf_flagged", "INTEGER DEFAULT 0"
        )
        await add_column_if_not_exists(
            db, "players", "smurf_flagged_at", "INTEGER DEFAULT 0"
        )

        # Mark migration as complete
        await db.execute(
            """
            INSERT INTO schema_migrations (version, applied_at)
            VALUES (?, datetime('now'))
            """,
            (MIGRATION_VERSION,),
        )

        await db.commit()

        log.info("=" * 60)
        log.info(f"✅ Migration {MIGRATION_VERSION} completed successfully!")
        log.info("=" * 60)

        return True

    except Exception as e:
        log.error(f"❌ Migration failed: {e}", exc_info=True)
        await db.rollback()
        log.error("   Database rolled back to previous state")
        return False


async def run(db: aiosqlite.Connection) -> None:
    """Entry point for migration runner."""
    await migrate(db)
