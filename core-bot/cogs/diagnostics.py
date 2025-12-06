"""
Diagnostics Cog - Health check command for bot troubleshooting
"""

import logging

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from database import DB_NAME
from utils.server_config import ServerConfigManager

log = logging.getLogger(__name__)


class DiagnosticsCog(commands.Cog):
    """Health check and diagnostics for the bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ServerConfigManager()

    @app_commands.command(name="diag")
    @app_commands.default_permissions(administrator=True)
    async def diagnostics(self, interaction: discord.Interaction):
        """Run bot health diagnostics (admin only)."""
        # Try to defer, but handle case where interaction was already acknowledged
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.HTTPException as e:
            if e.code != 40060:  # Not the "already acknowledged" error
                raise
            # If already acknowledged, we'll just send a new message instead of followup

        embed = discord.Embed(
            title="🔍 Bot Health Diagnostics", color=discord.Color.blue()
        )

        # Overall status will be determined by checks
        errors = []
        warnings = []

        # 1. Database Check
        db_status = await self._check_database()
        embed.add_field(name="💾 Database", value=db_status["message"], inline=False)
        if not db_status["healthy"]:
            errors.append("Database")

        # 2. Cogs Check
        cog_status = self._check_cogs()
        embed.add_field(name="🔌 Cogs", value=cog_status["message"], inline=False)
        if cog_status["warnings"]:
            warnings.append("Cogs")

        # 3. Scheduler Check
        scheduler_status = self._check_scheduler()
        embed.add_field(
            name="📅 Scheduler", value=scheduler_status["message"], inline=False
        )
        if not scheduler_status["healthy"]:
            warnings.append("Scheduler")

        # 4. Persistent Views Check
        views_status = self._check_persistent_views()
        embed.add_field(
            name="🎛️ Persistent Views", value=views_status["message"], inline=False
        )

        # 5. Channel Configuration Check (guild-specific)
        if interaction.guild:
            channel_status = await self._check_channels(
                interaction.guild.id, interaction.guild
            )
            embed.add_field(
                name="📺 Channel Config", value=channel_status["message"], inline=False
            )
            if channel_status["warnings"]:
                warnings.append("Channels")

        # 6. Orphaned Records Check
        orphans_status = await self._check_orphaned_records()
        embed.add_field(
            name="🗑️ Orphaned Records", value=orphans_status["message"], inline=False
        )
        if orphans_status["warnings"]:
            warnings.append("Orphaned Data")

        # Overall Status
        if errors:
            embed.color = discord.Color.red()
            embed.description = f"❌ **Critical Issues Found**: {', '.join(errors)}"
        elif warnings:
            embed.color = discord.Color.gold()
            embed.description = f"⚠️ **Warnings**: {', '.join(warnings)}"
        else:
            embed.color = discord.Color.green()
            embed.description = "✅ **All Systems Operational**"

        # Send response (followup if deferred, otherwise send new message)
        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except:
            # If followup fails, try sending a new response
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _check_database(self) -> dict:
        """Check database connectivity and tables."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                # Test basic connectivity
                await db.execute("SELECT 1")

                # Get table list
                async with db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ) as cursor:
                    tables = await cursor.fetchall()

                table_count = len(tables)
                critical_tables = [
                    "tournaments",
                    "players",
                    "server_configs",
                    "admin_dashboard_panels",
                ]
                missing = []

                table_names = [t[0] for t in tables]
                for table in critical_tables:
                    if table not in table_names:
                        missing.append(table)

                if missing:
                    return {
                        "healthy": False,
                        "message": f"❌ Missing tables: {', '.join(missing)}",
                    }

                return {
                    "healthy": True,
                    "message": f"✅ Connected ({table_count} tables)",
                }
        except Exception as e:
            return {"healthy": False, "message": f"❌ Connection failed: {str(e)[:50]}"}

    def _check_cogs(self) -> dict:
        """Check loaded cogs status."""
        loaded_cogs = list(self.bot.cogs.keys())
        cog_count = len(loaded_cogs)

        # Expected critical cogs
        critical_cogs = [
            "RegistrationCog",
            "AdminDashboardCog",
            "UserDashboardCog",
            "TournamentScheduler",
            "PlayerProfile",
        ]

        missing = [c for c in critical_cogs if c not in loaded_cogs]

        if missing:
            return {
                "healthy": True,
                "warnings": True,
                "message": f"⚠️ {cog_count} loaded, missing: {', '.join(missing)}",
            }

        return {
            "healthy": True,
            "warnings": False,
            "message": f"✅ {cog_count} cogs loaded",
        }

    def _check_scheduler(self) -> dict:
        """Check APScheduler status."""
        scheduler_cog = self.bot.get_cog("TournamentScheduler")

        if not scheduler_cog:
            return {"healthy": False, "message": "❌ Scheduler cog not loaded"}

        if not hasattr(scheduler_cog, "scheduler"):
            return {"healthy": False, "message": "❌ Scheduler not initialized"}

        scheduler = scheduler_cog.scheduler

        if not scheduler.running:
            return {"healthy": False, "message": "❌ Scheduler not running"}

        jobs = scheduler.get_jobs()
        return {"healthy": True, "message": f"✅ Running ({len(jobs)} jobs)"}

    def _check_persistent_views(self) -> dict:
        """Check if persistent views are registered."""
        # Check if bot has persistent views
        view_count = len(self.bot.persistent_views)

        return {
            "healthy": True,
            "message": f"✅ {view_count} persistent views registered",
        }

    async def _check_channels(self, guild_id: int, guild: discord.Guild) -> dict:
        """Check channel configuration for this guild."""
        try:
            config = await self.config.get_config(guild_id)

            if not config:
                return {
                    "healthy": False,
                    "warnings": True,
                    "message": "⚠️ No configuration found (run /setup)",
                }

            # Check critical channels exist
            issues = []
            checks = [
                ("Registration", config.get("registration_channel")),
                ("Results", config.get("results_channel")),
                ("Admin", config.get("admin_review_channel")),
            ]

            for name, channel_id in checks:
                if channel_id:
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        issues.append(f"{name} channel missing")

            if issues:
                return {
                    "healthy": False,
                    "warnings": True,
                    "message": f"⚠️ Issues: {', '.join(issues)}",
                }

            return {
                "healthy": True,
                "warnings": False,
                "message": "✅ All critical channels configured",
            }
        except Exception as e:
            return {
                "healthy": False,
                "warnings": True,
                "message": f"⚠️ Check failed: {str(e)[:30]}",
            }

    async def _check_orphaned_records(self) -> dict:
        """Check for orphaned records in the database."""
        try:
            issues = []

            async with aiosqlite.connect(DB_NAME) as db:
                # Check for tournament participants without tournaments
                async with db.execute(
                    """
                    SELECT COUNT(*) FROM tournament_participants tp
                    WHERE NOT EXISTS (
                        SELECT 1 FROM tournaments t WHERE t.key = tp.tournament_key
                    )
                """
                ) as cursor:
                    orphaned_participants = (await cursor.fetchone())[0]
                    if orphaned_participants > 0:
                        issues.append(f"{orphaned_participants} orphaned participants")

                # Check for matches without tournaments
                async with db.execute(
                    """
                    SELECT COUNT(*) FROM matches m
                    WHERE NOT EXISTS (
                        SELECT 1 FROM tournaments t WHERE t.key = m.tournament_key
                    )
                """
                ) as cursor:
                    orphaned_matches = (await cursor.fetchone())[0]
                    if orphaned_matches > 0:
                        issues.append(f"{orphaned_matches} orphaned matches")

                # Check for admin panels without valid guild
                async with db.execute(
                    """
                    SELECT COUNT(*) FROM admin_dashboard_panels
                    WHERE guild_id NOT IN (
                        SELECT DISTINCT guild_id FROM tournaments
                    )
                """
                ) as cursor:
                    orphaned_panels = (await cursor.fetchone())[0]
                    if orphaned_panels > 0:
                        issues.append(f"{orphaned_panels} orphaned panels")

            if issues:
                return {
                    "healthy": True,
                    "warnings": True,
                    "message": f"⚠️ Found: {', '.join(issues)}",
                }

            return {
                "healthy": True,
                "warnings": False,
                "message": "✅ No orphaned records found",
            }

        except Exception as e:
            return {
                "healthy": True,
                "warnings": False,
                "message": f"⚠️ Check skipped: {str(e)[:40]}",
            }


async def setup(bot: commands.Bot):
    """Load the Diagnostics cog."""
    await bot.add_cog(DiagnosticsCog(bot))
    log.info("DiagnosticsCog loaded successfully")
