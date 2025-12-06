# cogs/leaderboard.py
# ------------------------------------------------------------
# Leaderboard & Player Stats
# Phase 3: read stats via PlayerService / unified players table
# + legacy /leaderboard command for tests using player_ranks
# ------------------------------------------------------------

from __future__ import annotations

import logging
from typing import Any, Dict

import discord
from discord import app_commands
from discord.ext import commands

import aiosqlite
import database  # use database.DB_NAME so monkeypatching works in tests

from utils.server_config import ServerConfigManager

log = logging.getLogger(__name__)


class LeaderboardCog(commands.Cog):
    """Tracks and displays player statistics across all tournaments.

    Phase 3 Notes:
    - Stats are read from the unified `players` table via PlayerService.
    - This cog currently exposes `get_player_stats` for other cogs
      (e.g. PlayerProfile) to render tournament stats.
    - /leaderboard and /stats now read from canonical players table.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ServerConfigManager()
        log.info("LeaderboardCog initialized (service-backed)")

    # --------------------------------------------------------
    # Legacy / Test-Facing Command
    # --------------------------------------------------------

    @app_commands.command(
        name="leaderboard",
        description="Show the top players leaderboard",
    )
    async def leaderboard(self, inter: discord.Interaction) -> None:
        """
        Show top players ranked by total wins.

        Reads from canonical players table.
        """
        rows = []
        try:
            async with aiosqlite.connect(database.DB_NAME) as db:
                async with db.execute(
                    """
                    SELECT discord_id, claimed_rank, elo_1v1,
                           (COALESCE(tournament_matches_won, 0) + COALESCE(casual_matches_won, 0)) AS total_wins,
                           (COALESCE(tournament_matches_lost, 0) + COALESCE(casual_matches_lost, 0)) AS total_losses
                    FROM players
                    WHERE claimed_rank IS NOT NULL OR elo_1v1 IS NOT NULL
                    ORDER BY total_wins DESC, total_losses ASC, discord_id ASC
                    LIMIT 10
                    """
                ) as cursor:
                    rows = await cursor.fetchall()
        except Exception:
            log.warning("Failed to load leaderboard from players", exc_info=True)

        if not rows:
            await inter.response.send_message(
                "🏆 Leaderboard\nNo ranked players found yet.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🏆 Leaderboard",
            description="Top players by wins",
            color=discord.Color.gold(),
        )

        lines = []
        for idx, (discord_id, claimed_rank, elo, total_wins, total_losses) in enumerate(
            rows, start=1
        ):
            rank_display = claimed_rank or f"Elo {elo or 1000}"
            lines.append(
                f"**#{idx}** <@{discord_id}> — {rank_display} "
                f"({total_wins}W / {total_losses}L)"
            )

        embed.description = "\n".join(lines)

        await inter.response.send_message(
            content="🏆 Leaderboard",
            embed=embed,
            ephemeral=True,
        )

    @app_commands.command(
        name="stats",
        description="Show your personal player statistics",
    )
    async def stats(self, inter: discord.Interaction) -> None:
        """
        Show personal player stats.

        Reads from canonical players table.
        """
        row = None
        try:
            async with aiosqlite.connect(database.DB_NAME) as db:
                async with db.execute(
                    """
                    SELECT claimed_rank, elo_1v1,
                           (COALESCE(tournament_matches_won, 0) + COALESCE(casual_matches_won, 0)) AS total_wins,
                           (COALESCE(tournament_matches_lost, 0) + COALESCE(casual_matches_lost, 0)) AS total_losses
                    FROM players
                    WHERE discord_id = ?
                    """,
                    (inter.user.id,),
                ) as cursor:
                    row = await cursor.fetchone()
        except Exception:
            log.warning("Failed to load stats from players", exc_info=True)

        if not row:
            await inter.response.send_message(
                "📊 No stats found for you yet. Play some matches first!",
                ephemeral=True,
            )
            return

        claimed_rank, elo, total_wins, total_losses = row
        rank_display = claimed_rank or f"Elo {elo or 1000}"
        total_matches = (total_wins or 0) + (total_losses or 0)
        win_rate = (total_wins / total_matches) * 100 if total_matches > 0 else 0.0

        embed = discord.Embed(
            title=f"📊 Player Stats: {inter.user.display_name}",
            color=discord.Color.blue(),
        )

        embed.description = (
            f"Rank: {rank_display}\n"
            f"Wins: {total_wins}\n"
            f"Losses: {total_losses}\n"
            f"Win Rate: {win_rate:.1f}%"
        )

        embed.add_field(
            name="Rank",
            value=rank_display,
            inline=True,
        )
        embed.add_field(
            name="Record",
            value=f"{total_wins}W - {total_losses}L ({total_matches} matches)",
            inline=True,
        )
        embed.add_field(
            name="Win Rate",
            value=f"{win_rate:.1f}%",
            inline=True,
        )

        await inter.response.send_message(
            content=(
                "📊 Your current stats:\n"
                f"Rank: {rank_display} | "
                f"Wins: {total_wins} | Losses: {total_losses} | "
                f"Win Rate: {win_rate:.1f}%"
            ),
            embed=embed,
            ephemeral=True,
        )

    # --------------------------------------------------------
    # Service-backed stats for other cogs
    # --------------------------------------------------------

    async def get_player_stats(self, user_id: int) -> Dict[str, Any]:
        """[PHASE3] Get stats for a specific player via PlayerService.

        Returns a dict with keys used by PlayerProfile:
        - tournaments_played
        - first_place
        - second_place
        - tournament_wins
        - tournament_losses
        - casual_wins
        - casual_losses

        Missing fields default to 0 so this is safe even if the Player
        model doesn't have every attribute yet.
        """
        try:
            player = await self.bot.player_service.get_by_discord_id(user_id)
        except Exception as e:
            log.error(
                "Failed to load player stats for %s: %s", user_id, e, exc_info=True
            )
            return {}

        if not player:
            return {}

        # Map from Player model attributes to the fields the profile view expects.
        # getattr(..., 0) keeps this safe if any fields aren't present yet.
        return {
            "tournaments_played": getattr(player, "tournaments_played", 0),
            "first_place": getattr(player, "tournaments_won", 0),
            "second_place": getattr(player, "tournaments_second", 0),
            "tournament_wins": getattr(player, "tournament_match_wins", 0),
            "tournament_losses": getattr(player, "tournament_match_losses", 0),
            "casual_wins": getattr(player, "casual_wins", 0),
            "casual_losses": getattr(player, "casual_losses", 0),
        }

    # --------------------------------------------------------
    # Shim methods for legacy compatibility
    # --------------------------------------------------------

    async def record_match_result(
        self, winner_id: int, loser_id: int, tournament_key: str = None
    ) -> None:
        """
        [SHIM] Record a match result for tournament matches.

        This is a compatibility shim that delegates to rating_service.
        Called by BracketCog._resolve_match() after match completion.
        """
        # Skip dummy players (negative IDs)
        if winner_id <= 0 or loser_id <= 0:
            log.debug(
                f"[LEADERBOARD-SHIM] Skipping match with dummy player: "
                f"winner={winner_id}, loser={loser_id}"
            )
            return

        log.debug(
            f"[LEADERBOARD-SHIM] record_match_result called: "
            f"winner={winner_id}, loser={loser_id}, tournament={tournament_key}"
        )

        # Delegate to rating_service if available
        if hasattr(self.bot, "rating_service") and self.bot.rating_service:
            try:
                await self.bot.rating_service.apply_match_result(
                    winner_id, loser_id, mode="1v1"
                )
                log.info(
                    f"[LEADERBOARD-SHIM] Elo updated via rating_service: "
                    f"{winner_id} def. {loser_id}"
                )
            except Exception as e:
                log.error(f"[LEADERBOARD-SHIM] Failed to apply Elo: {e}")
        else:
            log.debug(
                "[LEADERBOARD-SHIM] rating_service not available, skipping Elo update"
            )

    async def record_tournament_placement(
        self,
        user_id: int,
        placement: int,
        tournament_key: str = None,
        tournament_name: str = None,
    ) -> None:
        """
        [SHIM] Record a tournament placement (1st, 2nd, etc.).

        This is a compatibility shim for legacy code that calls this method.
        Currently logs-only; full implementation deferred to Phase 4.
        """
        if user_id <= 0:
            log.debug(
                f"[LEADERBOARD-SHIM] Skipping placement for dummy player: {user_id}"
            )
            return

        log.info(
            f"[LEADERBOARD-SHIM] Tournament placement: user={user_id}, "
            f"place={placement}, tournament={tournament_name or tournament_key}"
        )

        # TODO: In Phase 4, update player stats in unified players table
        # via PlayerService.record_tournament_placement()


async def setup(bot: commands.Bot):
    """Load the LeaderboardCog."""
    await bot.add_cog(LeaderboardCog(bot))
