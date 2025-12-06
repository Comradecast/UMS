# cogs/player_profile.py
# ------------------------------------------------------------
# Player Profile & Rank System
# Foundation for skill-based matchmaking and tournaments
# ------------------------------------------------------------

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

import aiosqlite
import database  # use database.DB_NAME so monkeypatching works

from utils.server_config import ServerConfigManager

log = logging.getLogger(__name__)


# ------------------------------------------------------------
# Persistent Views and Modals
# ------------------------------------------------------------


class SetRankView(discord.ui.View):
    """Ephemeral view for selecting a starting rank + division."""

    def __init__(self, cog: "PlayerProfile", user_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.selected_rank: Optional[str] = None
        self.selected_division: Optional[int] = None

        # Initialize selectors
        self.add_item(RankSelect())
        self.add_item(DivisionSelect())
        self.add_item(ConfirmRankButton())


class RankSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Bronze", emoji="🥉"),
            discord.SelectOption(label="Silver", emoji="🥈"),
            discord.SelectOption(label="Gold", emoji="🥇"),
            discord.SelectOption(label="Platinum", emoji="💠"),
            discord.SelectOption(label="Diamond", emoji="💎"),
            discord.SelectOption(label="Champion", emoji="🏆"),
            discord.SelectOption(label="Grand Champion", emoji="👑"),
        ]
        super().__init__(
            placeholder="Select your Rank...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, inter: discord.Interaction) -> None:
        self.view.selected_rank = self.values[0]
        await inter.response.defer()


class DivisionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Division I", value="1"),
            discord.SelectOption(label="Division II", value="2"),
            discord.SelectOption(label="Division III", value="3"),
            discord.SelectOption(label="Division IV", value="4"),
            discord.SelectOption(label="Division V", value="5"),
        ]
        super().__init__(
            placeholder="Select your Division...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, inter: discord.Interaction) -> None:
        self.view.selected_division = int(self.values[0])
        await inter.response.defer()


class ConfirmRankButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Confirm Rank",
            row=2,
        )

    async def callback(self, inter: discord.Interaction) -> None:
        view: SetRankView = self.view

        if not view.selected_rank or not view.selected_division:
            return await inter.response.send_message(
                "❌ Please select both a Rank and a Division.",
                ephemeral=True,
            )

        await inter.response.defer(ephemeral=True)

        # [PHASE3] Check if rank is already locked using PlayerService
        player = await view.cog.bot.player_service.get_by_discord_id(inter.user.id)

        if player and player.rank_locked:
            return await inter.followup.send(
                "❌ **Rank is locked!**\n\n"
                "You've already set your rank. It's now automatically calculated from your Elo.\n"
                "If you need an adjustment, contact an admin.",
                ephemeral=True,
            )

        # Set starting rank (will lock it)
        success = await view.cog.bot.profile_service.set_rank(
            inter.user.id,
            view.selected_rank,
            view.selected_division,
        )

        if success:
            rank_display = view.cog.format_rank_display(
                view.selected_rank,
                view.selected_division,
                verified=False,
            )

            await inter.followup.send(
                f"✅ **Starting Rank Set!**\n\n"
                f"Your rank: **{rank_display}**\n\n"
                f"⚠️ **This is now locked.** Your rank will automatically update based on your Solo Queue Elo.\n"
                f"All queue types (1v1/2v2/3v3) start at the same Elo.",
                ephemeral=True,
            )

            # Update the persistent panel (if possible)
            await view.cog.update_rank_panel()
        else:
            await inter.followup.send(
                "❌ Failed to update rank. Please try again.",
                ephemeral=True,
            )


class RankPanelView(discord.ui.View):
    """
    Persistent view for the Rank Panel.

    Buttons:
    - Set Your Rank: opens SetRankView for starting rank selection
    - View Profile: redirects to /dashboard (single source of truth)
    """

    def __init__(self, cog: "PlayerProfile"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Set Your Rank",
        style=discord.ButtonStyle.primary,
        custom_id="rank_panel:set_rank",
        emoji="⚙️",
    )
    async def set_rank_button(
        self,
        inter: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Open ephemeral view to set starting rank + division."""
        view = SetRankView(self.cog, inter.user.id)
        await inter.response.send_message(
            "Select your Rank and Division:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="View Profile",
        style=discord.ButtonStyle.secondary,
        custom_id="rank_panel:view_profile",
        emoji="👤",
    )
    async def view_profile_button(
        self,
        inter: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """[PHASE3] Redirect users to the dashboard-based profile view."""
        await inter.response.send_message(
            "Player profiles have moved.\n\n"
            "Use `/dashboard` to view your current rank, Elo, match history, and stats.\n"
            "Solo Queue and tournaments now use that data as the source of truth.",
            ephemeral=True,
        )


# ------------------------------------------------------------
# Player Profile Cog
# ------------------------------------------------------------


class PlayerProfile(commands.Cog):
    """
    Manages player ranks, Elo, and profile-related helpers.

    Responsibilities (Phase 3):
    - Starting rank selection (panel + /set_rank)
    - Rank distribution reporting
    - Smurf detection & admin tooling
    - Onboarding helpers (region + starting rank/Elo)
    """

    # Rank tier values for calculations / ordering
    RANKS: Dict[str, int] = {
        "Bronze": 1,
        "Silver": 2,
        "Gold": 3,
        "Platinum": 4,
        "Diamond": 5,
        "Champion": 6,
        "Grand Champion": 7,
    }

    # Valid divisions within each rank
    DIVISIONS = [1, 2, 3, 4, 5]

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ServerConfigManager()
        self.rank_panel_messages: Dict[int, discord.Message] = {}  # guild_id -> message

    async def async_init(self) -> None:
        """Async initialization called after bot is ready."""
        # [PHASE3] DB schema is managed by migrations; only views need setup.
        await self._setup_persistent_panel()

    async def _setup_persistent_panel(self) -> None:
        """Register the persistent RankPanel view."""
        log.info("Starting persistent RankPanel setup...")
        try:
            # NOTE: Do NOT call wait_until_ready() here.
            # This is called from setup_hook() and would deadlock.
            view = RankPanelView(self)
            self.bot.add_view(view)
            log.info("Registered RankPanelView globally")
            log.info(
                "Persistent panel setup completed (deferred to runtime for posting)"
            )
        except Exception as e:
            log.error("Failed to setup persistent panels: %s", e, exc_info=True)

    async def _post_rank_panel(self, channel: discord.TextChannel) -> None:
        """Post the persistent Rank Panel to a channel."""
        embed = discord.Embed(
            title="🎮 Player Rank & Elo",
            description=(
                "Set your **starting** Rocket League Sideswipe rank for:\n"
                "✅ Skill-based matchmaking\n"
                "✅ Fair tournament seeding\n"
                "✅ Rank-restricted tournaments\n\n"
                "After this, your rank is **locked** and will auto-update "
                "based on your Solo Queue Elo."
            ),
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="📋 How It Works",
            value=(
                "1. Click **Set Your Rank**\n"
                "2. Choose your rank and division honestly\n"
                "3. Play Solo Queue – your Elo and rank will update automatically\n\n"
                "Detailed stats, Elo history, and match records live in `/dashboard`."
            ),
            inline=False,
        )

        embed.set_footer(text="Profiles & stats → /dashboard")

        view = RankPanelView(self)

        try:
            message = await channel.send(embed=embed, view=view)
            self.rank_panel_messages[channel.guild.id] = message
            log.info(
                "Posted new rank panel message in %s: %s",
                channel.guild.name,
                message.id,
            )
        except Exception as e:
            log.error("Failed to post rank panel: %s", e, exc_info=True)

    async def update_rank_panel(self) -> None:
        """
        Update the persistent panel embed.

        Currently a no-op. Kept as an extension point for:
        - rank distribution summary
        - total registered players
        - other global stats
        """
        return

    # --------------------------------------------------------
    # Service-layer wrappers (backwards compatibility)
    # --------------------------------------------------------

    async def set_rank(self, user_id: int, rank: str, division: int) -> bool:
        """Set a player's starting rank via ProfileService."""
        return await self.bot.profile_service.set_rank(user_id, rank, division)

    async def get_dashboard_stats(self, user_id: int) -> Dict[str, Any]:
        """Get formatted stats for user dashboard via ProfileService."""
        return await self.bot.profile_service.get_dashboard_stats(user_id)

    async def get_rank(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get a player's rank information via ProfileService."""
        return await self.bot.profile_service.get_rank(user_id)

    async def get_skill_rating(self, user_id: int) -> int:
        """Get a player's primary skill rating (currently 1v1 Elo)."""
        return await self.bot.profile_service.get_skill_rating(user_id)

    def format_rank_display(
        self,
        rank: str,
        division: int,
        verified: bool = False,
    ) -> str:
        """Format rank as a display string. Pure formatting logic."""
        roman = ["I", "II", "III", "IV", "V"]
        div_str = roman[division - 1] if 1 <= division <= 5 else str(division)
        verify_icon = "✅" if verified else "⚠️"
        return f"{rank} {div_str} {verify_icon}"

    # --------------------------------------------------------
    # Public Commands
    # --------------------------------------------------------

    @app_commands.command(
        name="profile",
        description="View player profile and rank",
    )
    @app_commands.describe(
        user="User to view profile for (leave blank for yourself)",
    )
    async def profile_cmd(
        self,
        inter: discord.Interaction,
        user: Optional[discord.Member] = None,
    ) -> None:
        """[LEGACY] Redirect users to the dashboard-based profile view."""
        await inter.response.send_message(
            "Player profiles and Rank info have moved.\n\n"
            "Use `/dashboard` to view your current rank, Elo, match history, and stats.\n"
            "Solo Queue and tournaments now use that data as the source of truth.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_rank",
        description="Set your Rocket League Sideswipe starting rank",
    )
    @app_commands.describe(
        rank="Your rank tier",
        division="Your division within the rank (I-V)",
    )
    @app_commands.choices(
        rank=[
            app_commands.Choice(name="Bronze", value="Bronze"),
            app_commands.Choice(name="Silver", value="Silver"),
            app_commands.Choice(name="Gold", value="Gold"),
            app_commands.Choice(name="Platinum", value="Platinum"),
            app_commands.Choice(name="Diamond", value="Diamond"),
            app_commands.Choice(name="Champion", value="Champion"),
            app_commands.Choice(name="Grand Champion", value="Grand Champion"),
        ]
    )
    @app_commands.choices(
        division=[
            app_commands.Choice(name="I", value=1),
            app_commands.Choice(name="II", value=2),
            app_commands.Choice(name="III", value=3),
            app_commands.Choice(name="IV", value=4),
            app_commands.Choice(name="V", value=5),
        ]
    )
    async def set_rank_cmd(
        self,
        inter: discord.Interaction,
        rank: str,
        division: app_commands.Choice[int],
    ) -> None:
        """
        Set your starting rank for skill-based matchmaking.

        [PHASE3] Primary UX is:
        - onboarding -> Rank Panel -> Elo auto-updates

        This command acts as a fallback / alternative path.
        """
        await inter.response.defer(ephemeral=True)

        # division may be a Choice[int] (normal slash usage) or an int (tests calling directly)
        if hasattr(division, "value"):
            division_value = int(division.value)
        else:
            division_value = int(division)

        # New v3 path: use ProfileService as the source of truth
        success = await self.bot.profile_service.set_rank(
            inter.user.id,
            rank,
            division_value,
        )

        if not success:
            return await inter.followup.send(
                "❌ Failed to update rank. Please try again.",
                ephemeral=True,
            )

        # Response to user (no legacy sync needed - players table is canonical)
        rank_display = self.format_rank_display(
            rank,
            division_value,
            verified=False,
        )
        elo = await self.bot.profile_service.get_skill_rating(inter.user.id)

        await inter.followup.send(
            f"✅ **Rank Updated!**\n\n"
            f"Your starting rank: **{rank_display}**\n"
            f"Solo Queue Elo: **{elo}**\n\n"
            f"⚠️ This starting rank is self-reported.\n"
            f"From now on your rank is derived automatically from Elo.",
            ephemeral=True,
        )

    @app_commands.command(
        name="rank_stats",
        description="Show server-wide rank distribution",
    )
    async def rank_stats(self, inter: discord.Interaction) -> None:
        """
        Show server-wide rank distribution.

        Reads from canonical players table.
        """
        rows = []
        try:
            async with aiosqlite.connect(database.DB_NAME) as db:
                async with db.execute(
                    """
                    SELECT claimed_rank, COUNT(*) AS count
                    FROM players
                    WHERE claimed_rank IS NOT NULL
                    GROUP BY claimed_rank
                    ORDER BY count DESC
                    """
                ) as cursor:
                    rows = await cursor.fetchall()
        except Exception:
            log.warning(
                "Failed to load rank distribution from players",
                exc_info=True,
            )

        if not rows:
            await inter.response.send_message(
                "📊 Rank distribution\nNo rank data available yet.",
                ephemeral=True,
            )
            return

        total = sum(count for _, count in rows)
        lines = []
        for rank_name, count in rows:
            pct = (count / total) * 100 if total > 0 else 0.0
            lines.append(f"{rank_name}: {count} players ({pct:.1f}%)")

        text = "📊 Rank distribution:\n" + "\n".join(lines)

        embed = discord.Embed(
            title="📊 Rank Distribution",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        await inter.response.send_message(
            content=text,
            embed=embed,
            ephemeral=True,
        )

    # ============================================================
    # Performance Tracking & Smurf Detection
    # ============================================================

    async def update_player_stats_after_match(
        self,
        winner_id: int,
        loser_id: int,
        tournament_key: Optional[str] = None,
    ) -> None:
        """
        Update player statistics after a match completes.

        Tracks wins, losses, and win streaks for smurf detection.
        """
        try:
            winner = await self.bot.player_service.get_or_create(winner_id)
            loser = await self.bot.player_service.get_or_create(loser_id)

            await self.bot.player_service.record_match_result(
                winner.id,
                did_win=True,
            )
            await self.bot.player_service.record_match_result(
                loser.id,
                did_win=False,
            )

            log.info(
                "Updated match stats: Winner %s, Loser %s",
                winner_id,
                loser_id,
            )

            await self.check_for_smurfs(winner_id)

        except Exception as e:
            log.error("Failed to update player stats after match: %s", e, exc_info=True)

    async def update_player_stats_after_tournament(
        self,
        tournament_key: str,
        placements: list[int],
    ) -> None:
        """Update player statistics after a tournament concludes."""
        if not placements:
            return

        try:
            for i, discord_id in enumerate(placements):
                placement = i + 1
                player = await self.bot.player_service.get_or_create(discord_id)
                await self.bot.player_service.record_tournament_result(
                    player.id,
                    placement,
                )

            log.info(
                "Updated tournament stats for %s players. Champion: %s",
                len(placements),
                placements[0],
            )

            await self.check_for_smurfs(placements[0])

        except Exception as e:
            log.error(
                "Failed to update player stats after tournament: %s",
                e,
                exc_info=True,
            )

    async def check_for_smurfs(self, user_id: int) -> None:
        """
        Check if a player meets smurf detection criteria and flag/notify if so.
        """
        try:
            player = await self.bot.player_service.get_by_discord_id(user_id)
            if not player:
                return

            rank_str = player.claimed_rank or "Unranked"
            rank_name = rank_str.split()[0]  # e.g. "Gold 3" -> "Gold"

            total_matches = player.total_wins + player.total_losses
            total_wins = player.total_wins
            current_streak = player.current_win_streak
            best_streak = player.best_win_streak
            tourns_played = player.tournaments_played
            tourns_won = player.tournaments_won
            already_flagged = bool(player.smurf_flagged)

            rank_tier = self.RANKS.get(rank_name, 3)
            if rank_tier > 2:
                return  # Not a low rank (Bronze/Silver), skip

            if total_matches < 30:
                return  # Not enough data

            win_rate = (total_wins / total_matches) * 100 if total_matches > 0 else 0
            if win_rate < 70:
                return  # Win rate not suspicious

            recent_tourns_won = tourns_won  # Simplified, can be refined later
            tournament_dominance = tourns_played >= 5 and recent_tourns_won >= 3
            long_streak = current_streak >= 10 or best_streak >= 10

            if not (tournament_dominance or long_streak):
                return

            if not already_flagged:
                await self.bot.player_service.set_smurf_flag(player.id, True)

                await self._notify_smurf_detected(
                    user_id,
                    {
                        "rank": rank_name,
                        "win_rate": win_rate,
                        "total_matches": total_matches,
                        "tournaments_won": tourns_won,
                        "tournaments_played": tourns_played,
                        "current_streak": current_streak,
                        "best_streak": best_streak,
                    },
                )

                log.warning(
                    "⚠️ SMURF DETECTED: User %s flagged - %s with %.1f%% win rate",
                    user_id,
                    rank_name,
                    win_rate,
                )

        except Exception as e:
            log.error("Failed to check for smurfs: %s", e, exc_info=True)

    async def _notify_smurf_detected(self, user_id: int, stats: Dict[str, Any]) -> None:
        """Send notification to admin channel about potential smurf."""
        admin_channel_id = os.getenv("ADMIN_NOTIFICATION_CHANNEL_ID")
        if not admin_channel_id or admin_channel_id == "0":
            log.warning("No admin notification channel configured for smurf alerts")
            return

        try:
            channel = self.bot.get_channel(int(admin_channel_id))
            if not channel:
                return

            current_tier = self.RANKS.get(stats["rank"], 1)
            suggested_tier = min(current_tier + 2, max(self.RANKS.values()))
            suggested_rank = next(
                (k for k, v in self.RANKS.items() if v == suggested_tier),
                stats["rank"],
            )

            embed = discord.Embed(
                title="🚨 Potential Smurf Detected",
                description=f"Player <@{user_id}> shows suspicious performance patterns",
                color=discord.Color.red(),
            )

            embed.add_field(
                name="Current Rank",
                value=f"{stats['rank']} (Tier {self.RANKS.get(stats['rank'], 1)})",
                inline=True,
            )

            embed.add_field(
                name="Win Rate",
                value=f"{stats['win_rate']:.1f}%",
                inline=True,
            )

            embed.add_field(
                name="Matches Played",
                value=str(stats["total_matches"]),
                inline=True,
            )

            embed.add_field(
                name="Tournaments",
                value=f"{stats['tournaments_won']} wins / {stats['tournaments_played']} played",
                inline=True,
            )

            embed.add_field(
                name="Win Streak",
                value=f"Current: {stats['current_streak']} | Best: {stats['best_streak']}",
                inline=True,
            )

            embed.add_field(
                name="💡 Suggested Action",
                value=f"Consider bumping to **{suggested_rank}**",
                inline=False,
            )

            embed.set_footer(
                text="This is an automated alert. Please review before taking action.",
            )

            await channel.send(embed=embed)
            log.info("Sent smurf alert for user %s to admin channel", user_id)

        except Exception as e:
            log.error("Failed to send smurf notification: %s", e, exc_info=True)

    async def is_smurf_flagged(self, user_id: int) -> bool:
        """Check if a user is currently flagged as a smurf."""
        return await self.bot.profile_service.is_smurf_flagged(user_id)

    async def sync_player_stats(self, user_id: int) -> bool:
        """Recalculate and update stats for a single user from match history."""
        try:
            player = await self.bot.player_service.get_by_discord_id(user_id)
            if not player:
                return False
            await self.bot.player_service.recompute_stats_from_history(player.id)
            return True
        except Exception as e:
            log.error("Failed to sync stats for user %s: %s", user_id, e, exc_info=True)
            return False

    # ============================================================
    # Admin Commands for Manual Smurf Management
    # ============================================================

    profile_admin = app_commands.Group(
        name="profile_admin",
        description="Admin commands for player profile management",
    )

    @profile_admin.command(
        name="view",
        description="View detailed player stats (Admin only)",
    )
    @app_commands.describe(user="Player to view stats for")
    async def admin_view_profile(
        self,
        inter: discord.Interaction,
        user: discord.Member,
    ) -> None:
        """View detailed player profile with performance stats (admin-only)."""
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(
                "❌ This command is admin-only.",
                ephemeral=True,
            )

        await inter.response.defer(ephemeral=True)

        try:
            player = await self.bot.player_service.get_by_discord_id(user.id)
            if not player:
                return await inter.followup.send(
                    f"❌ {user.mention} has not set their rank yet.",
                    ephemeral=True,
                )

            rank_str = player.claimed_rank or "Unranked"
            total_m = player.total_wins + player.total_losses
            total_w = player.total_wins
            total_l = player.total_losses
            curr_streak = player.current_win_streak
            best_streak = player.best_win_streak
            tourns_played = player.tournaments_played
            tourns_won = player.tournaments_won
            smurf_flag = bool(player.smurf_flagged)
            smurf_time = player.smurf_flagged_at

            win_rate = (total_w / total_m * 100) if total_m > 0 else 0.0

            embed = discord.Embed(
                title=f"📊 Player Profile: {user.display_name}",
                color=discord.Color.red() if smurf_flag else discord.Color.blue(),
            )

            flag_emoji = "🚨" if smurf_flag else ""
            embed.add_field(
                name="Rank",
                value=f"{rank_str} {flag_emoji}",
                inline=True,
            )

            embed.add_field(
                name="Matches",
                value=f"{total_w}W - {total_l}L ({total_m} total)",
                inline=True,
            )

            embed.add_field(
                name="Win Rate",
                value=f"{win_rate:.1f}%",
                inline=True,
            )

            embed.add_field(
                name="Tournaments",
                value=f"{tourns_won} wins / {tourns_played} played",
                inline=True,
            )

            embed.add_field(
                name="Win Streaks",
                value=f"Current: {curr_streak} | Best: {best_streak}",
                inline=True,
            )

            if smurf_flag:
                embed.add_field(
                    name="⚠️ Smurf Flag",
                    value=f"Flagged <t:{smurf_time}:R>",
                    inline=False,
                )

            await inter.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            log.error("Failed to view admin profile: %s", e, exc_info=True)
            await inter.followup.send(f"❌ Error: {e}", ephemeral=True)

    @profile_admin.command(
        name="flag",
        description="Manually flag a player as a potential smurf (Admin only)",
    )
    @app_commands.describe(user="Player to flag", reason="Reason for flagging")
    async def admin_flag_smurf(
        self,
        inter: discord.Interaction,
        user: discord.Member,
        reason: str = "Manual flag",
    ) -> None:
        """Manually flag a player as a smurf (admin-only)."""
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(
                "❌ This command is admin-only.",
                ephemeral=True,
            )

        await inter.response.defer(ephemeral=True)

        try:
            player = await self.bot.player_service.get_or_create(user.id)
            await self.bot.player_service.set_smurf_flag(player.id, True)

            await inter.followup.send(
                f"✅ Flagged {user.mention} as potential smurf.\nReason: {reason}",
                ephemeral=True,
            )
            log.info(
                "Admin %s manually flagged %s as smurf: %s",
                inter.user.id,
                user.id,
                reason,
            )

        except Exception as e:
            log.error("Failed to flag smurf: %s", e, exc_info=True)
            await inter.followup.send(f"❌ Error: {e}", ephemeral=True)

    @profile_admin.command(
        name="clear_flag",
        description="Remove smurf flag from a player (Admin only)",
    )
    @app_commands.describe(user="Player to clear flag from")
    async def admin_clear_flag(
        self,
        inter: discord.Interaction,
        user: discord.Member,
    ) -> None:
        """Clear smurf flag from a player (admin-only)."""
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(
                "❌ This command is admin-only.",
                ephemeral=True,
            )

        await inter.response.defer(ephemeral=True)

        try:
            player = await self.bot.player_service.get_by_discord_id(user.id)
            if player:
                await self.bot.player_service.set_smurf_flag(player.id, False)

            await inter.followup.send(
                f"✅ Cleared smurf flag from {user.mention}",
                ephemeral=True,
            )
            log.info(
                "Admin %s cleared smurf flag from %s",
                inter.user.id,
                user.id,
            )

        except Exception as e:
            log.error("Failed to clear smurf flag: %s", e, exc_info=True)
            await inter.followup.send(f"❌ Error: {e}", ephemeral=True)

    @profile_admin.command(
        name="sync_stats",
        description="Recalculate player stats from match history (Admin only)",
    )
    async def admin_sync_stats(self, inter: discord.Interaction) -> None:
        """Recalculate wins/losses/matches from global_matches table."""
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message(
                "❌ This command is admin-only.",
                ephemeral=True,
            )

        await inter.response.defer(ephemeral=True)

        try:
            player_ids = await self.bot.player_service.get_all_player_ids()
            updated_count = 0

            for pid in player_ids:
                await self.bot.player_service.recompute_stats_from_history(pid)
                updated_count += 1

            await inter.followup.send(
                f"✅ Successfully synced stats for {updated_count} players based on match history.",
                ephemeral=True,
            )
            log.info(
                "Admin %s synced stats for %s players",
                inter.user.id,
                updated_count,
            )

        except Exception as e:
            log.error("Failed to sync stats: %s", e, exc_info=True)
            await inter.followup.send(f"❌ Error: {e}", ephemeral=True)

    # --------------------------------------------------------
    # Onboarding Helpers
    # --------------------------------------------------------

    async def check_onboarding_status(self, user_id: int) -> bool:
        """Check if user has completed onboarding."""
        try:
            player = await self.bot.player_service.get_by_discord_id(user_id)
            if not player:
                return False
            return bool(player.has_onboarded)
        except Exception as e:
            log.error(
                "Failed to check onboarding status for %s: %s",
                user_id,
                e,
                exc_info=True,
            )
            return False

    async def complete_onboarding(
        self,
        user_id: int,
        region: str,
        rank: str,
    ) -> bool:
        """Save onboarding data and mark as complete."""
        try:
            from constants import RANK_TO_ELO

            starting_elo = RANK_TO_ELO.get(rank, 1000)

            await self.bot.player_service.complete_onboarding(
                user_id,
                region,
                rank,
                starting_elo,
            )

            log.info(
                "Completed onboarding for user %s: %s, %s (Elo: %s)",
                user_id,
                region,
                rank,
                starting_elo,
            )
            return True
        except Exception as e:
            log.error(
                "Failed to complete onboarding for %s: %s", user_id, e, exc_info=True
            )
            return False


async def setup(bot: commands.Bot) -> None:
    """Load the PlayerProfile cog."""
    await bot.add_cog(PlayerProfile(bot))
