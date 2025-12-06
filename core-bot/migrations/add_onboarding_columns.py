"""
Database migration script to add onboarding columns to player_ranks table.

This script:
1. Adds has_onboarded column (default 0)
2. Adds region column (default NULL)
3. Marks all existing users as onboarded (to avoid blocking them)

Run this ONCE before deploying the new onboarding feature.
"""

import asyncio
import logging

import aiosqlite

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DB_NAME = "tournament_bot.db"


async def migrate():
    """Run the migration."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            log.info("Starting migration...")

            # Check if columns already exist
            cursor = await db.execute("PRAGMA table_info(player_ranks)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            needs_migration = False

            # Add has_onboarded column if it doesn't exist
            if "has_onboarded" not in column_names:
                log.info("Adding has_onboarded column...")
                await db.execute(
                    "ALTER TABLE player_ranks ADD COLUMN has_onboarded INTEGER DEFAULT 0"
                )
                needs_migration = True
            else:
                log.info("has_onboarded column already exists")

            # Add region column if it doesn't exist
            if "region" not in column_names:
                log.info("Adding region column...")
                await db.execute(
                    "ALTER TABLE player_ranks ADD COLUMN region TEXT DEFAULT NULL"
                )
                needs_migration = True
            else:
                log.info("region column already exists")

            if needs_migration:
                # Mark all existing users as onboarded
                log.info("Marking existing users as onboarded...")
                result = await db.execute("UPDATE player_ranks SET has_onboarded = 1")
                await db.commit()

                # Count how many users were updated
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM player_ranks WHERE has_onboarded = 1"
                )
                count = (await cursor.fetchone())[0]

                log.info(
                    f"✅ Migration complete! Marked {count} existing users as onboarded."
                )
            else:
                log.info("✅ No migration needed - columns already exist.")

    except Exception as e:
        log.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(migrate())
