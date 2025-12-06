"""
Phase 1 Migration: Consolidate players and player_ranks into unified players table.

This migration:
1. Backs up the database file
2. Creates a new unified players table
3. Merges data from old players + player_ranks
4. Renames old tables to *_backup (preserved for safety)
5. Adds performance indexes

SAFE: Can be run multiple times (idempotent), preserves all old data.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

MIGRATION_VERSION = "001_consolidate_players"


async def check_if_migration_needed(db: aiosqlite.Connection) -> bool:
    """Check if this migration has already been applied or is even needed."""
    try:
        # Check if migration tracking table exists
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

        # Check that both legacy tables exist
        async with db.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('players', 'player_ranks')
            """
        ) as cursor:
            tables = await cursor.fetchall()

        if len(tables) < 2:
            log.info("Old tables not found, migration not needed.")
            return False

        # *** KEY ADDITION FOR V3 ***
        # Check that player_ranks still has all the legacy columns that this
        # migration expects. If not, we're on the new schema and this legacy
        # consolidation is not applicable.
        cols: list[str] = []
        async with db.execute("PRAGMA table_info(player_ranks)") as cursor:
            async for row in cursor:
                # row[1] is column name
                cols.append(row[1])

        required_cols = {
            "user_id",
            "rank",
            "region",
            "elo_1v1",
            "elo_2v2",
            "elo_3v3",
        }
        missing = sorted(required_cols.difference(cols))
        if missing:
            log.debug(
                "Migration %s: legacy player_ranks missing expected columns (%s); "
                "assuming database is already on new schema; skipping consolidation.",
                MIGRATION_VERSION,
                ", ".join(missing),
            )
            return False

        # If we got here:
        # - schema_migrations doesn't have this version yet
        # - both tables exist
        # - player_ranks still has 'rank'
        # => we should run the migration
        return True

    except Exception as e:
        log.error(f"Error checking migration status: {e}", exc_info=True)
        return False


async def backup_database(db_path: str) -> bool:
    """Create a backup of the database file before migration."""
    try:
        db_file = Path(db_path)
        if not db_file.exists():
            log.error(f"Database file not found: {db_path}")
            return False

        # Create backup with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_file.with_suffix(f".backup_{timestamp}.db")

        shutil.copy2(db_file, backup_path)
        log.info(f"✅ Database backed up to: {backup_path}")
        return True

    except Exception as e:
        log.error(f"Failed to backup database: {e}")
        return False


async def migrate(db: aiosqlite.Connection, db_path: str) -> bool:
    """
    Safely consolidate players and player_ranks tables.

    Returns:
        True if migration succeeded, False otherwise
    """
    try:
        # Step 0: Check if migration is needed
        if not await check_if_migration_needed(db):
            return True

        log.info("=" * 60)
        log.info(f"Starting migration: {MIGRATION_VERSION}")
        log.info("=" * 60)

        # Step 1: Backup database
        log.info("Step 1: Creating database backup...")
        if not await backup_database(db_path):
            log.error("Migration aborted: backup failed")
            return False

        # Step 2: Ensure provisional_games columns exist in player_ranks
        log.info("Step 2: Ensuring provisional_games columns exist...")
        for mode in ["1v1", "2v2", "3v3"]:
            try:
                await db.execute(
                    f"ALTER TABLE player_ranks ADD COLUMN provisional_games_{mode} INTEGER DEFAULT 0"
                )
                log.info(f"  ✅ Added provisional_games_{mode} column")
            except Exception:
                # Column already exists
                pass
        await db.commit()

        # Step 3: Create new unified players table
        log.info("Step 3: Creating unified players_new table...")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS players_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER NOT NULL UNIQUE,

                -- Onboarding & Profile
                claimed_rank TEXT,
                mode_main TEXT,
                region TEXT,
                has_onboarded INTEGER DEFAULT 0,

                -- Per-Mode Elo Ratings
                elo_1v1 INTEGER,
                elo_2v2 INTEGER,
                elo_3v3 INTEGER,

                -- Provisional Game Counters
                provisional_games_1v1 INTEGER DEFAULT 0,
                provisional_games_2v2 INTEGER DEFAULT 0,
                provisional_games_3v3 INTEGER DEFAULT 0,

                -- Legacy Stats (from old players table)
                tournaments_played INTEGER DEFAULT 0,
                first_place INTEGER DEFAULT 0,
                second_place INTEGER DEFAULT 0,
                third_place INTEGER DEFAULT 0,
                tournament_matches_won INTEGER DEFAULT 0,
                tournament_matches_lost INTEGER DEFAULT 0,
                casual_matches_won INTEGER DEFAULT 0,
                casual_matches_lost INTEGER DEFAULT 0,

                -- Additional Stats (from player_ranks)
                total_wins INTEGER DEFAULT 0,
                total_losses INTEGER DEFAULT 0,
                current_win_streak INTEGER DEFAULT 0,
                best_win_streak INTEGER DEFAULT 0,

                -- Tournament Stats
                tournaments_won INTEGER DEFAULT 0,
                last_tournament_at INTEGER DEFAULT 0,

                -- Smurf Detection
                smurf_flagged INTEGER DEFAULT 0,
                smurf_flagged_at INTEGER DEFAULT 0,

                -- Queue Management
                queue_leaves INTEGER DEFAULT 0,
                queue_banned_until INTEGER,

                -- Rank Lock
                rank_locked INTEGER DEFAULT 0,

                -- Timestamps
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
        """
        )
        log.info("  ✅ Created players_new table")

        # Step 4: Merge data from both tables
        log.info("Step 4: Merging data from players + player_ranks...")
        await db.execute(
            """
            INSERT INTO players_new (
                discord_id, claimed_rank, mode_main, region, has_onboarded,
                elo_1v1, elo_2v2, elo_3v3,
                provisional_games_1v1, provisional_games_2v2, provisional_games_3v3,
                tournaments_played, first_place, second_place, third_place,
                tournament_matches_won, tournament_matches_lost,
                casual_matches_won, casual_matches_lost,
                total_wins, total_losses, current_win_streak, best_win_streak,
                tournaments_won, last_tournament_at,
                smurf_flagged, smurf_flagged_at, queue_leaves, queue_banned_until,
                rank_locked, created_at, last_seen_at
            )
            SELECT
                COALESCE(p.user_id, pr.user_id) as discord_id,
                pr.rank as claimed_rank,
                NULL as mode_main,
                COALESCE(pr.region, p.region) as region,
                COALESCE(pr.has_onboarded, 0) as has_onboarded,
                COALESCE(pr.elo_1v1, 1000) as elo_1v1,
                COALESCE(pr.elo_2v2, 1000) as elo_2v2,
                COALESCE(pr.elo_3v3, 1000) as elo_3v3,
                COALESCE(pr.provisional_games_1v1, 0) as provisional_games_1v1,
                COALESCE(pr.provisional_games_2v2, 0) as provisional_games_2v2,
                COALESCE(pr.provisional_games_3v3, 0) as provisional_games_3v3,
                COALESCE(p.tournaments_played, 0) as tournaments_played,
                COALESCE(p.first_place, 0) as first_place,
                COALESCE(p.second_place, 0) as second_place,
                COALESCE(p.third_place, 0) as third_place,
                COALESCE(p.tournament_matches_won, 0) as tournament_matches_won,
                COALESCE(p.tournament_matches_lost, 0) as tournament_matches_lost,
                COALESCE(p.casual_matches_won, 0) as casual_matches_won,
                COALESCE(p.casual_matches_lost, 0) as casual_matches_lost,
                COALESCE(pr.total_wins, 0) as total_wins,
                COALESCE(pr.total_losses, 0) as total_losses,
                COALESCE(pr.current_win_streak, 0) as current_win_streak,
                COALESCE(pr.best_win_streak, 0) as best_win_streak,
                COALESCE(pr.tournaments_won, 0) as tournaments_won,
                COALESCE(pr.last_tournament_at, 0) as last_tournament_at,
                COALESCE(pr.smurf_flagged, 0) as smurf_flagged,
                COALESCE(pr.smurf_flagged_at, 0) as smurf_flagged_at,
                COALESCE(pr.queue_leaves, 0) as queue_leaves,
                pr.queue_banned_until,
                COALESCE(pr.rank_locked, 0) as rank_locked,
                datetime('now') as created_at,
                datetime('now') as last_seen_at
            FROM player_ranks pr
            LEFT JOIN players p ON p.user_id = pr.user_id

            UNION

            SELECT
                p.user_id as discord_id,
                NULL as claimed_rank,
                NULL as mode_main,
                p.region,
                0 as has_onboarded,
                1000 as elo_1v1,
                1000 as elo_2v2,
                1000 as elo_3v3,
                0 as provisional_games_1v1,
                0 as provisional_games_2v2,
                0 as provisional_games_3v3,
                p.tournaments_played,
                p.first_place,
                p.second_place,
                p.third_place,
                p.tournament_matches_won,
                p.tournament_matches_lost,
                p.casual_matches_won,
                p.casual_matches_lost,
                0 as total_wins,
                0 as total_losses,
                0 as current_win_streak,
                0 as best_win_streak,
                0 as tournaments_won,
                0 as last_tournament_at,
                0 as smurf_flagged,
                0 as smurf_flagged_at,
                0 as queue_leaves,
                NULL as queue_banned_until,
                0 as rank_locked,
                datetime('now') as created_at,
                datetime('now') as last_seen_at
            FROM players p
            WHERE NOT EXISTS (
                SELECT 1 FROM player_ranks pr WHERE pr.user_id = p.user_id
            )
        """
        )

        async with db.execute("SELECT COUNT(*) FROM players_new") as cursor:
            count = (await cursor.fetchone())[0]
            log.info(f"  ✅ Migrated {count} player records")

        # Step 5: Rename tables
        log.info("Step 5: Renaming tables...")
        await db.execute("ALTER TABLE players RENAME TO players_backup")
        await db.execute("ALTER TABLE player_ranks RENAME TO player_ranks_backup")
        await db.execute("ALTER TABLE players_new RENAME TO players")
        log.info("  ✅ Old tables renamed to *_backup")
        log.info("  ✅ New table activated as 'players'")

        # Step 6: Add indexes
        log.info("Step 6: Adding performance indexes...")
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_players_discord_id ON players(discord_id)
        """
        )
        log.info("  ✅ Created index on discord_id")

        # Step 7: Mark migration as complete
        await db.execute(
            """
            INSERT INTO schema_migrations (version, applied_at)
            VALUES (?, ?)
        """,
            (MIGRATION_VERSION, datetime.now().isoformat()),
        )

        await db.commit()

        log.info("=" * 60)
        log.info(f"✅ Migration {MIGRATION_VERSION} completed successfully!")
        log.info("   Old tables preserved as players_backup and player_ranks_backup")
        log.info("=" * 60)

        return True

    except Exception as e:
        log.error(f"❌ Migration failed: {e}", exc_info=True)
        await db.rollback()
        log.error("   Database rolled back to previous state")
        return False


async def run_migrations(db: aiosqlite.Connection, db_path: str = "tournament_bot.db"):
    """Run all pending migrations."""
    try:
        await migrate(db, db_path)
    except Exception as e:
        log.error(f"Migration runner failed: {e}", exc_info=True)
