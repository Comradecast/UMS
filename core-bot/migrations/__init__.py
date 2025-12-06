"""
UMS Bot Core Migrations Package
-------------------------------
Contains ONLY migrations applicable to UMS Core schema.

UMS Core does NOT include: teams, matches (unified), or advanced tournament features.
Only run migrations that apply to core tables: players, guild_config, tournament_requests.
"""

import importlib
import logging
import aiosqlite

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# UMS CORE MIGRATIONS ONLY
# DO NOT add migrations that reference: teams, matches_unified, match_participants
# -----------------------------------------------------------------------------

# Import ONLY migrations that apply to UMS Core schema
_consolidate = importlib.import_module(".001_consolidate_players", package="migrations")
_add_v3_columns = importlib.import_module(
    ".002_add_players_v3_columns", package="migrations"
)
_add_channel_created = importlib.import_module(
    ".009_add_channel_created_cols", package="migrations"
)
_recreate_tournaments = importlib.import_module(
    ".010_recreate_tournaments_table", package="migrations"
)
_add_restrictions = importlib.import_module(
    ".011_add_tournament_restrictions", package="migrations"
)
_add_archive_fields = importlib.import_module(
    ".012_add_tournament_archive_fields", package="migrations"
)
_add_dashboard = importlib.import_module(
    ".013_add_tournament_dashboard", package="migrations"
)
_add_pending_result = importlib.import_module(
    ".014_add_match_pending_result", package="migrations"
)
_add_tournament_code = importlib.import_module(
    ".015_add_tournament_code", package="migrations"
)

# List of UMS Core migrations in order
# These ONLY touch tables that exist in UMS Core
MIGRATIONS = [
    _consolidate,  # players table consolidation
    _add_v3_columns,  # players v3 columns
    _add_channel_created,  # guild_config channel_created tracking
    _recreate_tournaments,  # tournaments table with Core schema
    _add_restrictions,  # allowed_regions/ranks for tournaments
    _add_archive_fields,  # winner/runner-up/completed_at for archiving
    _add_dashboard,  # dashboard_channel_id/message_id
    _add_pending_result,  # pending_winner_entry_id/reported_by for confirmations
    _add_tournament_code,  # tournament_code for human-friendly IDs
    # NOTE: Migrations 003-008 are for full tournament-bot and are intentionally excluded:
    # - 003_create_matches_unified: matches table (not in Core)
    # - 004_create_match_participants: match_participants table (not in Core)
    # - 005_add_match_status: matches table (not in Core)
    # - 006_add_ums_match_id_to_solo_matches: solo_matches table (not in Core)
    # - 007_add_team_tag_column: teams table (not in Core)
    # - 008_add_standings_message_id: tournaments advanced fields (not in Core)
]


async def run_migrations(
    db: aiosqlite.Connection, db_path: str = "tournament_bot_core.db"
):
    """
    Run UMS Core migrations only.

    This runner uses the hard-coded MIGRATIONS list above.
    It does NOT scan for migration files dynamically.
    """
    log.debug("[CORE-MIGRATIONS] Starting UMS Core migration runner...")
    migrations_run = 0

    for migration in MIGRATIONS:
        module_name = getattr(migration, "__name__", "unknown")
        try:
            if hasattr(migration, "run"):
                await migration.run(db)
                migrations_run += 1
                log.debug(f"[CORE-MIGRATIONS] Ran {module_name}")
            elif hasattr(migration, "migrate"):
                # For older migration style (001_consolidate_players)
                await migration.migrate(db, db_path)
                migrations_run += 1
                log.debug(f"[CORE-MIGRATIONS] Ran {module_name}")
        except Exception as e:
            log.error(
                f"[CORE-MIGRATIONS] Migration {module_name} failed: {e}", exc_info=True
            )
            raise

    log.info(f"[CORE-MIGRATIONS] Complete ({migrations_run} migrations checked)")


__all__ = ["run_migrations", "MIGRATIONS"]
