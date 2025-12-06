"""
Migration 015: Add tournament_code field
-----------------------------------------
Adds tournament_code column for human-friendly tournament IDs (e.g., JTP6F9KE).
"""

import logging
import random
import aiosqlite

log = logging.getLogger(__name__)

# Code alphabet: no confusing chars (0/O, 1/I)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def generate_code() -> str:
    """Generate a random 8-character tournament code."""
    return "".join(random.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


async def run(db: aiosqlite.Connection) -> None:
    """Add tournament_code column and backfill existing tournaments."""
    try:
        # Check existing columns
        cursor = await db.execute("PRAGMA table_info(tournaments)")
        columns = [row[1] for row in await cursor.fetchall()]

        # Add column if missing
        if "tournament_code" not in columns:
            await db.execute("ALTER TABLE tournaments ADD COLUMN tournament_code TEXT")
            log.info("[MIGRATION-015] Added tournament_code column")

            # Create unique index
            await db.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_tournaments_tournament_code
                ON tournaments(tournament_code)
                """
            )
            log.info("[MIGRATION-015] Created unique index on tournament_code")

        # Backfill existing tournaments with codes
        cursor = await db.execute(
            "SELECT id FROM tournaments WHERE tournament_code IS NULL"
        )
        null_rows = await cursor.fetchall()

        if null_rows:
            log.info(
                f"[MIGRATION-015] Backfilling {len(null_rows)} tournaments with codes"
            )

            # Get existing codes to avoid collisions
            cursor = await db.execute(
                "SELECT tournament_code FROM tournaments WHERE tournament_code IS NOT NULL"
            )
            existing_codes = {row[0] for row in await cursor.fetchall()}

            for row in null_rows:
                tournament_id = row[0]

                # Generate unique code
                while True:
                    code = generate_code()
                    if code not in existing_codes:
                        existing_codes.add(code)
                        break

                await db.execute(
                    "UPDATE tournaments SET tournament_code = ? WHERE id = ?",
                    (code, tournament_id),
                )
                log.info(
                    f"[MIGRATION-015] Assigned code {code} to tournament {tournament_id}"
                )

        await db.commit()
        log.info("[MIGRATION-015] Tournament code migration complete")

    except Exception as e:
        log.error(f"[MIGRATION-015] Failed: {e}")
        raise
