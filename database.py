"""
core-bot/database.py — UMS Bot Core Database Module
-----------------------------------------------------
Provides DB initialization with v3 schema for UMS Core only.

UMS Core Tables:
- meta: Schema version tracking
- players: Player identity and basic info (minimal fields for core)
- guild_config: Server configuration (v3 source of truth)
- tournament_requests: Request tracking with approval workflow
- tournaments: Minimal tournament records

Legacy/Compatibility:
- server_configs: Read-only fallback, migrates to guild_config on first use
"""

from __future__ import annotations

import importlib.util
import logging
import os
import time
from pathlib import Path
from typing import Optional

import aiosqlite

log = logging.getLogger(__name__)

# Core bot uses its own database file
DB_NAME = os.getenv("CORE_BOT_DB", "tournament_bot_core.db")

SCHEMA_VERSION = 4  # UMS Core v1.0.0-core

# Idempotency flag
_db_initialized = False


async def init_db_once(db_path: Optional[str] = None) -> float:
    """
    Idempotent database initialization. Safe to call multiple times.

    Returns the time taken in seconds (0 if already initialized).
    """
    global _db_initialized
    if _db_initialized:
        log.debug("Database already initialized, skipping")
        return 0.0

    start = time.perf_counter()
    await init_db(db_path)
    _db_initialized = True
    elapsed = time.perf_counter() - start
    return elapsed


def reset_db_init_flag():
    """Reset the initialization flag (for testing only)."""
    global _db_initialized
    _db_initialized = False


async def init_db(db_path: Optional[str] = None) -> None:
    """Initialize the database with the UMS Core v3 schema."""
    target_db = db_path or DB_NAME

    async with aiosqlite.connect(target_db) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # ------------------------------------------------------------------
        # META - Schema version tracking
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            INSERT OR REPLACE INTO meta (key, value)
            VALUES ('schema_version', ?)
            """,
            (str(SCHEMA_VERSION),),
        )

        # ------------------------------------------------------------------
        # PLAYERS - Minimal player identity for UMS Core
        # Only fields needed for onboarding and basic identification
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                user_id                    INTEGER PRIMARY KEY,
                discord_id                 INTEGER UNIQUE,
                display_name               TEXT,
                region                     TEXT,
                primary_mode               TEXT,
                claimed_rank               TEXT,
                has_onboarded              INTEGER DEFAULT 0,
                created_at                 INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at                 INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """
        )

        # ------------------------------------------------------------------
        # GUILD_CONFIG - v3 Server Configuration (source of truth)
        # Clean, minimal config for UMS Core
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id                INTEGER PRIMARY KEY,
                admin_channel           INTEGER,
                announce_channel        INTEGER,
                request_channel         INTEGER,
                onboarding_channel      INTEGER,
                ums_admin_role          INTEGER,
                setup_completed         INTEGER DEFAULT 0,
                onboarding_channel_created  INTEGER DEFAULT 0,
                admin_channel_created       INTEGER DEFAULT 0,
                announce_channel_created    INTEGER DEFAULT 0,
                created_at              INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at              INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """
        )

        # ------------------------------------------------------------------
        # TOURNAMENT_REQUESTS - Request tracking with approval workflow
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tournament_requests (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id                INTEGER NOT NULL,
                requester_id            INTEGER NOT NULL,
                name                    TEXT NOT NULL,
                region                  TEXT,
                format                  TEXT,
                size                    TEXT,
                match_length            TEXT,
                start_time              TEXT,
                scheduled_start         INTEGER,
                rank_restriction        TEXT,
                region_restriction      TEXT,
                status                  TEXT DEFAULT 'pending',
                admin_message_id        INTEGER,
                resolved_by             INTEGER,
                resolved_at             INTEGER,
                decline_reason          TEXT,
                tournament_key          TEXT,
                created_at              INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_requests_guild_status ON tournament_requests(guild_id, status)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_requests_requester ON tournament_requests(requester_id)"
        )

        # ------------------------------------------------------------------
        # TOURNAMENTS - Single Elimination tournament records
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tournaments (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id                INTEGER NOT NULL,
                name                    TEXT NOT NULL,
                tournament_code         TEXT UNIQUE,
                format                  TEXT NOT NULL,
                size                    INTEGER NOT NULL,
                status                  TEXT NOT NULL DEFAULT 'draft',
                reg_message_id          INTEGER,
                reg_channel_id          INTEGER,
                allowed_regions         TEXT,
                allowed_ranks           TEXT,
                winner_player_id        INTEGER,
                runner_up_player_id     INTEGER,
                completed_at            INTEGER,
                dashboard_channel_id    INTEGER,
                dashboard_message_id    INTEGER,
                created_at              INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_tournaments_guild_status ON tournaments(guild_id, status)"
        )

        # ------------------------------------------------------------------
        # TOURNAMENT_ENTRIES - Player/team registrations
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tournament_entries (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id           INTEGER NOT NULL,
                player1_id              INTEGER NOT NULL,
                player2_id              INTEGER,
                team_name               TEXT,
                seed                    INTEGER,
                created_at              INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
            )
            """
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_entries_tournament ON tournament_entries(tournament_id)"
        )

        # ------------------------------------------------------------------
        # MATCHES - SE bracket matches
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id           INTEGER NOT NULL,
                round                   INTEGER NOT NULL,
                match_index             INTEGER NOT NULL,
                entry1_id               INTEGER,
                entry2_id               INTEGER,
                winner_entry_id         INTEGER,
                score_text              TEXT,
                status                  TEXT NOT NULL DEFAULT 'pending',
                pending_winner_entry_id INTEGER,
                pending_reported_by     INTEGER,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
            )
            """
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament_id, round)"
        )

        # ------------------------------------------------------------------
        # LEGACY: server_configs (read-only fallback, do not write)
        # Keep for backwards compatibility with existing installs
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS server_configs (
                guild_id                    INTEGER PRIMARY KEY,
                tournament_requests_channel INTEGER,
                admin_review_channel        INTEGER,
                registration_channel        INTEGER,
                results_channel             INTEGER,
                casual_match_channel        INTEGER,
                rank_channel                INTEGER,
                clan_channel                INTEGER,
                audit_channel               INTEGER,
                admin_role                  INTEGER,
                organizer_role              INTEGER,
                enabled                     INTEGER DEFAULT 1,
                setup_completed             INTEGER DEFAULT 0,
                setup_date                  INTEGER,
                enable_leaderboard          INTEGER DEFAULT 1,
                enable_player_profiles      INTEGER DEFAULT 1,
                enable_casual_matches       INTEGER DEFAULT 1,
                created_at                  INTEGER,
                updated_at                  INTEGER
            )
            """
        )

        # ------------------------------------------------------------------
        # ORGANIZER RATE LIMITING
        # ------------------------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS organizer_cooldowns (
                user_id         INTEGER PRIMARY KEY,
                cooldown_until  INTEGER NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS organizer_bans (
                user_id         INTEGER PRIMARY KEY,
                reason          TEXT,
                banned_at       INTEGER,
                banned_by       TEXT
            )
            """
        )

        await db.commit()
        log.info("[CORE-DB] Schema initialized at %s (v%s)", target_db, SCHEMA_VERSION)


async def run_migrations(db: aiosqlite.Connection, db_path: str) -> None:
    """
    Run UMS Core migrations only.

    Uses the hardcoded MIGRATIONS list from migrations/__init__.py.
    Does NOT scan for migration files dynamically to avoid running
    migrations that reference tables not in UMS Core.
    """
    log.debug("[CORE-DB] Starting UMS Core migration runner...")

    try:
        # Import the curated migrations list from migrations package
        from migrations import run_migrations as run_core_migrations

        await run_core_migrations(db, db_path)
    except ImportError as e:
        log.warning(f"[CORE-DB] Could not import migrations package: {e}")
    except Exception as e:
        log.error(f"[CORE-DB] Migration error: {e}", exc_info=True)
        raise


async def migrate_legacy_config(db: aiosqlite.Connection, guild_id: int) -> bool:
    """
    Migrate legacy server_configs to guild_config on first use.
    Returns True if migration occurred, False otherwise.
    """
    db.row_factory = aiosqlite.Row

    # Check if guild_config already exists
    async with db.execute(
        "SELECT 1 FROM guild_config WHERE guild_id = ?", (guild_id,)
    ) as cursor:
        if await cursor.fetchone():
            return False  # Already migrated

    # Check for legacy config
    async with db.execute(
        "SELECT * FROM server_configs WHERE guild_id = ?", (guild_id,)
    ) as cursor:
        legacy = await cursor.fetchone()

    if not legacy:
        return False  # No legacy config to migrate

    # Migrate minimal fields to guild_config
    now = int(time.time())
    await db.execute(
        """
        INSERT INTO guild_config (
            guild_id, admin_channel, announce_channel, request_channel,
            ums_admin_role, setup_completed, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            legacy["admin_review_channel"],
            legacy["registration_channel"],  # Use as announce channel
            legacy["tournament_requests_channel"],
            legacy["admin_role"],
            legacy["setup_completed"],
            legacy["created_at"] or now,
            now,
        ),
    )
    await db.commit()

    log.info(
        "[CORE-DB] Migrated legacy server_configs -> guild_config for guild %s",
        guild_id,
    )
    return True


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DB_NAME)
    db.row_factory = aiosqlite.Row
    return db


def get_db_path() -> str:
    """Return the active DB path."""
    return DB_NAME


async def validate_db_connectivity(db_path: Optional[str] = None) -> bool:
    """
    Validate database connectivity.
    Returns True if connection succeeds, raises exception otherwise.
    """
    target_db = db_path or DB_NAME
    try:
        async with aiosqlite.connect(target_db) as db:
            await db.execute("SELECT 1")
        return True
    except Exception as e:
        log.error(f"[CORE-DB] Database connectivity check failed: {e}")
        raise


async def get_core_tables() -> list[str]:
    """Return list of core tables that should exist."""
    return [
        "meta",
        "players",
        "guild_config",
        "tournament_requests",
        "tournaments",
        "organizer_cooldowns",
        "organizer_bans",
    ]


async def validate_schema(db_path: Optional[str] = None) -> dict:
    """
    Validate all core tables exist.
    Returns dict with table names and their existence status.
    """
    target_db = db_path or DB_NAME
    core_tables = await get_core_tables()
    result = {}

    async with aiosqlite.connect(target_db) as db:
        for table in core_tables:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ) as cursor:
                row = await cursor.fetchone()
                result[table] = row is not None

    return result
