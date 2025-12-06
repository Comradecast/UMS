"""
core-bot/bot.py — UMS Bot Core Entry Point
-------------------------------------------
Hardened startup sequence with pre-flight checks,
lockfile handling, and clean shutdown.

UMS Core v1.0.0-core - 3 Hero Features Only:
1. Onboarding Panel
2. Admin Setup Panel
3. Tournament Request Flow (approval-required)

EXCLUDES: Live brackets, Elo/ratings, clans, teams, queues
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports when running from core-bot/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

import aiosqlite
import discord
from discord.ext import commands

from database import (
    DB_NAME,
    init_db_once,
    run_migrations,
    validate_db_connectivity,
    validate_schema,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "").strip()
OWNER_ID: Optional[int] = int(os.getenv("OWNER_ID", "0") or "0") or None

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-5s | %(name)s: %(message)s",
)
log = logging.getLogger("core-bot")

# Lockfile path
LOCKFILE = Path(__file__).parent / "bot.lock"

# -----------------------------------------------------------------------------
# Bot Setup
# -----------------------------------------------------------------------------

intents = discord.Intents.default()
# Core bot does everything via slash commands & components.
# Do NOT request privileged intents for this minimal external build.
intents.presences = False
intents.members = False
intents.message_content = False


class CoreBot(commands.Bot):
    """
    UMS Bot Core - Minimal tournament bot with 3 hero features.

    Features:
    - Onboarding Panel (player registration)
    - Admin Setup Panel (server configuration)
    - Tournament Request Flow (approval-required workflow)
    """

    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db: Optional[aiosqlite.Connection] = None
        self._startup_complete = False

    async def run_startup_checks(self) -> None:
        """
        Pre-flight checks before Discord login.
        Validates environment, database, and core requirements.
        Fails fast with clear errors if anything is missing.
        """
        print("\n" + "=" * 60)
        print(">> UMS Bot Core — Pre-flight Checks (v1.0.0-core)")
        print("=" * 60)

        # 1. Validate DISCORD_TOKEN
        if not DISCORD_TOKEN:
            raise RuntimeError(
                "❌ DISCORD_TOKEN not set in environment.\n"
                "   Set it in your .env file or environment variables."
            )
        print("[✓] DISCORD_TOKEN present ............. OK")

        # 2. Validate database connectivity
        try:
            await validate_db_connectivity()
            print(f"[✓] Database connectivity ............. OK ({DB_NAME})")
        except Exception as e:
            raise RuntimeError(
                f"❌ Database connection failed: {e}\n"
                f"   Check that {DB_NAME} is accessible and not locked."
            )

        # 3. Initialize schema / create tables
        try:
            await init_db_once()
            print("[✓] Schema initialization ............. OK")
        except Exception as e:
            raise RuntimeError(f"❌ Schema initialization failed: {e}")

        # 4. Validate required tables exist
        try:
            schema_status = await validate_schema()
            missing = [t for t, exists in schema_status.items() if not exists]
            if missing:
                raise RuntimeError(f"Missing tables: {', '.join(missing)}")
            print("[✓] Core tables validated ............. OK")
        except Exception as e:
            raise RuntimeError(f"❌ Schema validation failed: {e}")

        print("-" * 60)
        print("[+] Pre-flight checks complete")
        print("-" * 60 + "\n")

    async def setup_hook(self):
        """5-phase startup sequence."""
        print("\n" + "=" * 60)
        print(">> Core Bot Startup")
        print("=" * 60)

        # Phase 1: Database
        phase1_start = time.perf_counter()
        self.db = await aiosqlite.connect(DB_NAME)
        self.db.row_factory = aiosqlite.Row
        try:
            await run_migrations(self.db, DB_NAME)
        except Exception as e:
            log.error(f"Migration error: {e}", exc_info=True)
        phase1_elapsed = time.perf_counter() - phase1_start
        print(f"[1/5] Database & migrations ........... OK ({phase1_elapsed:.2f}s)")

        # Phase 2: Core services
        phase2_start = time.perf_counter()
        await self._init_services()
        phase2_elapsed = time.perf_counter() - phase2_start
        print(f"[2/5] Core services ................... OK ({phase2_elapsed:.2f}s)")

        # Phase 3: Load cogs
        phase3_start = time.perf_counter()
        await self._load_cogs()
        phase3_elapsed = time.perf_counter() - phase3_start
        print(f"[3/5] Cogs loaded ..................... OK ({phase3_elapsed:.2f}s)")

        # Phase 4: Cog initialization
        phase4_start = time.perf_counter()
        for cog in self.cogs.values():
            if hasattr(cog, "async_init"):
                try:
                    await cog.async_init()
                except Exception as e:
                    log.error(f"Error in {cog.__class__.__name__}.async_init(): {e}")
        phase4_elapsed = time.perf_counter() - phase4_start
        print(f"[4/5] Cog initialization .............. OK ({phase4_elapsed:.2f}s)")

        # Phase 5: Sync commands
        phase5_start = time.perf_counter()
        synced = await self.tree.sync()
        log.info(f"Synced {len(synced)} global commands")
        phase5_elapsed = time.perf_counter() - phase5_start
        print(f"[5/5] Command sync .................... OK ({phase5_elapsed:.2f}s)")

        print("-" * 60)
        total = (
            phase1_elapsed
            + phase2_elapsed
            + phase3_elapsed
            + phase4_elapsed
            + phase5_elapsed
        )
        print(f"[+] Startup complete in {total:.2f}s")
        print("-" * 60)

        self._startup_complete = True

    async def _init_services(self):
        """Initialize core services for UMS Core."""
        from services.player_service import PlayerService
        from services.guild_config_service import GuildConfigService
        from services.tournament_service import TournamentService

        self.player_service = PlayerService(self.db)
        self.guild_config_service = GuildConfigService(self.db)
        self.tournament_service = TournamentService(self.db)

    async def _load_cogs(self):
        """
        Load UMS Core cogs only.

        UMS Core includes:
        - server_setup: Admin setup panel
        - onboarding_view: Player onboarding
        - tournaments: Tournament management
        """
        core_cogs = [
            "cogs.server_setup",  # Admin Setup Panel
            "cogs.onboarding_view",  # Onboarding Panel
            "cogs.tournaments",  # Tournament Management
        ]

        loaded = 0
        failed = []

        for cog_path in core_cogs:
            try:
                print(f"    Loading {cog_path}...", end=" ")
                await self.load_extension(cog_path)
                loaded += 1
                print("OK")
                log.info(f"Loaded cog: {cog_path}")
            except Exception as e:
                failed.append(cog_path.split(".")[-1])
                print(f"FAILED: {e}")
                log.error(f"Failed to load {cog_path}: {e}", exc_info=True)

        log.info(f"Loaded {loaded}/{len(core_cogs)} core cogs")
        if failed:
            log.warning(f"Failed cogs: {', '.join(failed)}")


bot = CoreBot()


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id if bot.user else 'n/a'})")
    print("\n" + "-" * 60)
    print("[+] UMS BOT CORE IS FULLY ONLINE")
    print("-" * 60 + "\n")

    # Set presence to point people at /ums-help
    try:
        await bot.change_presence(activity=discord.Game(name="/ums-help for info"))
        log.info("Bot presence set: Playing /ums-help for info")
    except Exception as e:
        log.warning(f"Failed to set presence: {e}")


# -----------------------------------------------------------------------------
# Shutdown
# -----------------------------------------------------------------------------


async def shutdown():
    """Graceful shutdown."""
    log.info("Shutdown: starting graceful shutdown")

    if getattr(bot, "db", None):
        try:
            await bot.db.close()
            log.info("Shutdown: database connection closed")
        except Exception:
            log.exception("Error closing database")

    try:
        await bot.close()
    except Exception:
        log.exception("Error closing bot")

    log.info("Shutdown: complete")


def cleanup_lockfile():
    """Remove lockfile if it exists."""
    if LOCKFILE.exists():
        try:
            LOCKFILE.unlink()
            log.debug("Lockfile removed")
        except Exception as e:
            log.warning(f"Could not remove lockfile: {e}")


# -----------------------------------------------------------------------------
# Main Entry
# -----------------------------------------------------------------------------


async def main():
    """Main entry point with lockfile handling and pre-flight checks."""

    # Check for stale lockfile
    if LOCKFILE.exists():
        try:
            pid = LOCKFILE.read_text().strip()
            log.warning(
                f"⚠️  Lockfile exists (PID: {pid}). "
                "Previous instance may not have shut down cleanly. Continuing anyway."
            )
        except Exception:
            log.warning("⚠️  Stale lockfile detected. Continuing anyway.")

    try:
        # Create lockfile
        LOCKFILE.write_text(str(os.getpid()))
        log.debug(f"Created lockfile: {LOCKFILE}")

        # Run pre-flight checks BEFORE Discord login
        await bot.run_startup_checks()

        # Start bot
        log.info("Starting UMS Bot Core...")
        await bot.start(DISCORD_TOKEN)

    except KeyboardInterrupt:
        log.info("Shutdown signal received (Ctrl+C)")
        await shutdown()
    except asyncio.CancelledError:
        log.info("Shutdown signal received (cancelled)")
        await shutdown()
    except Exception as e:
        log.exception(f"Fatal error: {e}")
        await shutdown()
        raise
    finally:
        # Always cleanup lockfile
        cleanup_lockfile()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C at the asyncio.run level
        cleanup_lockfile()
        print("\nBot stopped.")
