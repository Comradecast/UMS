"""
cogs/tournaments.py — Tournament Management for UMS Bot Core
=============================================================
Admin-only commands for managing Single Elimination tournaments.

Commands:
- /tournament_create - Create a new tournament
- /tournament_open_registration - Open registration
- /tournament_close_registration - Close registration
- /tournament_start - Generate bracket and start (coming soon)
- /tournament_report_result - Record match result (coming soon)
- /tournament_cancel - Cancel tournament
"""

from __future__ import annotations

import logging
from typing import Optional, List

import discord
from discord import app_commands, ui
from discord.ext import commands

# Import UI components from ui/ package
from ui.match_views import MatchCardView, CompletedMatchView
from ui.tournament_views import (
    DashboardView,
    AdminControlPanel,
)
from ui.tournament_embeds import build_dashboard_embed
from ui.registration_views import (
    Registration1v1View,
    Registration2v2View,
)

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# DEV-ONLY CONFIGURATION
# -----------------------------------------------------------------------------

# Add your Discord user ID here to enable dev-only commands
# Example: DEV_USER_IDS = {123456789012345678, 987654321098765432}
DEV_USER_IDS: set[int] = {
    1383507533901201449,
}


def is_dev_user(user: discord.abc.User) -> bool:
    """Check if user is a developer with access to dev-only commands."""
    return user.id in DEV_USER_IDS


# -----------------------------------------------------------------------------
# MATCH CARD POSTING HELPERS
# -----------------------------------------------------------------------------


async def post_match_cards(
    bot: commands.Bot,
    guild: discord.Guild,
    tournament_id: int,
    matches: List,
) -> int:
    """
    Post match cards for a list of matches.

    Returns number of cards posted.
    """
    # Get announce channel from guild config
    config = await bot.guild_config_service.get(guild.id)
    if not config or not config.announce_channel:
        log.warning(f"[MATCH-CARD] No announce channel configured for guild {guild.id}")
        return 0

    channel = guild.get_channel(config.announce_channel)
    if not channel:
        log.warning(
            f"[MATCH-CARD] Announce channel {config.announce_channel} not found"
        )
        return 0

    # Get tournament for format info
    tournament = await bot.tournament_service.get_by_id(tournament_id)
    if not tournament:
        return 0

    posted = 0
    for match in matches:
        # Skip BYEs and completed matches
        if match.entry2_id is None or match.status != "pending":
            continue

        # Get display names
        entry1_name = await bot.tournament_service.get_entry_display_name(
            match.entry1_id, tournament.format
        )
        entry2_name = await bot.tournament_service.get_entry_display_name(
            match.entry2_id, tournament.format
        )

        # Create embed
        embed = discord.Embed(
            title=f"⚔️ Match #{match.id} — Round {match.round}",
            description=f"**{entry1_name}** vs **{entry2_name}**",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Tournament", value=tournament.name, inline=True)
        embed.add_field(name="Format", value=tournament.format, inline=True)
        embed.set_footer(text="Click a button below to report the winner!")

        # Create view
        view = MatchCardView(
            bot=bot,
            match_id=match.id,
            entry1_id=match.entry1_id,
            entry2_id=match.entry2_id,
            entry1_name=entry1_name,
            entry2_name=entry2_name,
        )

        try:
            await channel.send(embed=embed, view=view)
            posted += 1
            log.info(f"[MATCH-CARD] Posted match card {match.id} to #{channel.name}")
        except Exception as e:
            log.error(f"[MATCH-CARD] Failed to post match {match.id}: {e}")

    return posted


async def maybe_post_next_round_cards(
    bot: commands.Bot,
    guild: discord.Guild,
    tournament_id: int,
) -> None:
    """
    Check if a new round was generated and post match cards for it.

    Called after a match result is reported.
    """
    # Get latest matches
    matches = await bot.tournament_service.list_matches(tournament_id)
    if not matches:
        return

    # Find latest round
    latest_round = max(m.round for m in matches)
    round_matches = [m for m in matches if m.round == latest_round]

    # Check if this round has any pending matches that need cards
    pending = [
        m for m in round_matches if m.status == "pending" and m.entry2_id is not None
    ]
    if pending:
        # Post cards for pending matches in this round
        await post_match_cards(bot, guild, tournament_id, pending)


# -----------------------------------------------------------------------------
# TOURNAMENT DASHBOARD HELPERS
# -----------------------------------------------------------------------------


async def post_tournament_dashboard(
    bot: commands.Bot,
    guild: discord.Guild,
    tournament,
) -> bool:
    """Post the tournament dashboard to announce channel."""
    # Get announce channel
    config = await bot.guild_config_service.get(guild.id)
    if not config or not config.announce_channel:
        log.warning(f"[DASHBOARD] No announce channel configured for guild {guild.id}")
        return False

    channel = guild.get_channel(config.announce_channel)
    if not channel:
        log.warning(f"[DASHBOARD] Announce channel {config.announce_channel} not found")
        return False

    # Build embed
    embed = await build_dashboard_embed(bot, tournament)

    # Create view
    view = DashboardView(bot, tournament.id)

    try:
        message = await channel.send(embed=embed, view=view)

        # Store dashboard reference
        await bot.tournament_service.set_dashboard_message(
            tournament.id,
            channel.id,
            message.id,
        )

        log.info(f"[DASHBOARD] Posted dashboard for tournament {tournament.id}")
        return True

    except Exception as e:
        log.error(f"[DASHBOARD] Failed to post dashboard: {e}")
        return False


async def update_tournament_dashboard(
    bot: commands.Bot,
    guild: discord.Guild,
    tournament_id: int,
) -> bool:
    """Update the tournament dashboard message."""
    tournament = await bot.tournament_service.get_by_id(tournament_id)
    if not tournament:
        return False

    if not tournament.dashboard_channel_id or not tournament.dashboard_message_id:
        log.debug(
            f"[DASHBOARD] No dashboard message to update for tournament {tournament_id}"
        )
        return False

    channel = guild.get_channel(tournament.dashboard_channel_id)
    if not channel:
        log.warning(
            f"[DASHBOARD] Dashboard channel {tournament.dashboard_channel_id} not found"
        )
        return False

    try:
        message = await channel.fetch_message(tournament.dashboard_message_id)
    except discord.NotFound:
        log.warning(
            f"[DASHBOARD] Dashboard message {tournament.dashboard_message_id} not found"
        )
        return False
    except Exception as e:
        log.warning(f"[DASHBOARD] Failed to fetch dashboard message: {e}")
        return False

    # Build updated embed
    embed = await build_dashboard_embed(bot, tournament)

    # Determine view
    if tournament.status in ("completed", "archived"):
        view = None  # Disable buttons
    else:
        view = DashboardView(bot, tournament.id)

    try:
        await message.edit(embed=embed, view=view)
        log.info(
            f"[DASHBOARD] Updated dashboard for tournament {tournament_id} in guild {guild.id}"
        )
        return True
    except Exception as e:
        log.error(f"[DASHBOARD] Failed to update dashboard: {e}")
        return False


# -----------------------------------------------------------------------------
# ADMIN PANEL HELPER
# -----------------------------------------------------------------------------


async def post_admin_panel(bot: commands.Bot, channel: discord.TextChannel) -> bool:
    """Post the admin control panel to a channel."""
    try:
        embed = discord.Embed(
            title="🎮 UMS Tournament Control Panel",
            description=(
                "Manage tournaments with one click!\n\n"
                "**Workflow:**\n"
                "1️⃣ Create Tournament\n"
                "2️⃣ Open Registration\n"
                "3️⃣ Close Registration\n"
                "4️⃣ Start Tournament\n"
                "5️⃣ Report Results (coming soon)"
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="UMS Bot Core • Only admins can use these buttons")

        view = AdminControlPanel(bot)
        await channel.send(embed=embed, view=view)

        log.info(f"[TOURNAMENT] Posted admin panel to #{channel.name}")
        return True

    except Exception as e:
        log.error(f"[TOURNAMENT] Failed to post admin panel: {e}")
        return False


# -----------------------------------------------------------------------------
# TOURNAMENTS COG
# -----------------------------------------------------------------------------


class TournamentsCog(commands.Cog):
    """Admin commands for managing Single Elimination tournaments."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Register persistent views when cog loads."""
        # Register admin control panel
        self.bot.add_view(AdminControlPanel(self.bot))

        # Note: Registration views are tournament-specific so they can't be
        # fully restored here. The buttons will show "This interaction failed"
        # for old panels after restart - that's acceptable for Core.

        log.info("[TOURNAMENT] Registered persistent views")

    @property
    def tournament_service(self):
        """Get tournament service from bot."""
        return self.bot.tournament_service

    @property
    def config_service(self):
        """Get guild config service from bot."""
        return self.bot.guild_config_service

    # -------------------------------------------------------------------------
    # /tournament_create
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="tournament_create",
        description="Create a new tournament (Admin only)",
    )
    @app_commands.describe(
        name="Tournament name",
        format="Tournament format",
        size="Maximum number of entries",
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name="1v1 (Solo)", value="1v1"),
            app_commands.Choice(name="2v2 (Teams)", value="2v2"),
        ],
        size=[
            app_commands.Choice(name="8 players/teams", value=8),
            app_commands.Choice(name="16 players/teams", value=16),
            app_commands.Choice(name="32 players/teams", value=32),
            app_commands.Choice(name="64 players/teams", value=64),
        ],
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def tournament_create(
        self,
        interaction: discord.Interaction,
        name: str,
        format: app_commands.Choice[str],
        size: app_commands.Choice[int],
    ):
        """Create a new tournament."""
        await interaction.response.defer(ephemeral=True)

        tournament, error = await self.tournament_service.create_tournament(
            guild_id=interaction.guild.id,
            name=name,
            format=format.value,
            size=size.value,
        )

        if error:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Tournament Created",
            description=f"**{tournament.name}**",
            color=discord.Color.green(),
        )
        embed.add_field(name="Format", value=tournament.format, inline=True)
        embed.add_field(name="Size", value=str(tournament.size), inline=True)
        embed.add_field(name="Status", value=tournament.status, inline=True)
        embed.add_field(
            name="Next Steps",
            value=(
                "1. Use `/tournament_open_registration` to open signups\n"
                "2. Players register via the registration panel\n"
                "3. Use `/tournament_close_registration` when ready\n"
                "4. Use `/tournament_start` to generate the bracket"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Tournament ID: {tournament.id}")

        await interaction.followup.send(embed=embed, ephemeral=True)

        log.info(
            f"[TOURNAMENT] Created '{name}' ({format.value}, size={size.value}) "
            f"in guild {interaction.guild.id}"
        )

    # -------------------------------------------------------------------------
    # /tournament_open_registration
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="tournament_open_registration",
        description="Open registration for the current tournament (Admin only)",
    )
    @app_commands.describe(
        channel="Channel to post registration panel (defaults to announcement channel)",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def tournament_open_registration(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Open registration for the current tournament."""
        await interaction.response.defer(ephemeral=True)

        # Get active tournament
        tournament = await self.tournament_service.get_active_for_guild(
            interaction.guild.id
        )

        if not tournament:
            await interaction.followup.send(
                "❌ No active tournament found. Use `/tournament_create` first.",
                ephemeral=True,
            )
            return

        # Check status allows opening registration
        if tournament.status not in ("draft", "reg_open"):
            await interaction.followup.send(
                f"❌ Cannot open registration. Tournament status is **{tournament.status}**.\n"
                f"Registration can only be opened from 'draft' status.",
                ephemeral=True,
            )
            return

        # Determine target channel
        if channel:
            target = channel
        else:
            # Try to get announcement channel from config
            config = await self.config_service.get(interaction.guild.id)
            if config and config.announce_channel:
                target = interaction.guild.get_channel(config.announce_channel)
                if not target:
                    target = interaction.channel
            else:
                target = interaction.channel

        # Update status
        await self.tournament_service.set_status(tournament.id, "reg_open")

        # Build registration embed
        format_text = "Solo (1v1)" if tournament.format == "1v1" else "Teams (2v2)"
        reg_embed = discord.Embed(
            title=f"🏆 {tournament.name}",
            description=(
                f"**Registration is now OPEN!**\n\n"
                f"Click the button below to register."
            ),
            color=discord.Color.blue(),
        )
        reg_embed.add_field(name="Format", value=format_text, inline=True)
        reg_embed.add_field(name="Max Entries", value=str(tournament.size), inline=True)
        reg_embed.add_field(name="Registered", value="0", inline=True)
        reg_embed.set_footer(text="UMS Bot Core • Single Elimination Tournament")

        # Create appropriate view based on format
        if tournament.format == "1v1":
            view = Registration1v1View(self, tournament.id)
        else:
            view = Registration2v2View(self, tournament.id)

        reg_message = await target.send(embed=reg_embed, view=view)

        # Store message reference
        await self.tournament_service.set_registration_message(
            tournament.id,
            reg_message.id,
            target.id,
        )

        await interaction.followup.send(
            f"✅ Registration opened for **{tournament.name}**!\n"
            f"Registration panel posted in {target.mention}",
            ephemeral=True,
        )

        log.info(
            f"[TOURNAMENT] Opened registration for tournament {tournament.id} "
            f"in channel {target.id}"
        )

    # -------------------------------------------------------------------------
    # /tournament_close_registration
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="tournament_close_registration",
        description="Close registration for the current tournament (Admin only)",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def tournament_close_registration(
        self,
        interaction: discord.Interaction,
    ):
        """Close registration for the current tournament."""
        await interaction.response.defer(ephemeral=True)

        # Get active tournament
        tournament = await self.tournament_service.get_active_for_guild(
            interaction.guild.id
        )

        if not tournament:
            await interaction.followup.send(
                "❌ No active tournament found.",
                ephemeral=True,
            )
            return

        # Check status
        if tournament.status != "reg_open":
            await interaction.followup.send(
                f"❌ Cannot close registration. Tournament status is **{tournament.status}**.\n"
                f"Registration can only be closed from 'reg_open' status.",
                ephemeral=True,
            )
            return

        # Get entry count
        entry_count = await self.tournament_service.count_entries(tournament.id)

        # Update status
        await self.tournament_service.set_status(tournament.id, "reg_closed")

        # Try to update the registration message to disable buttons
        if tournament.reg_channel_id and tournament.reg_message_id:
            try:
                channel = interaction.guild.get_channel(tournament.reg_channel_id)
                if channel:
                    message = await channel.fetch_message(tournament.reg_message_id)

                    # Update embed
                    embed = message.embeds[0] if message.embeds else None
                    if embed:
                        embed.description = "**Registration is CLOSED.**"
                        embed.color = discord.Color.orange()

                        # Update registered count
                        for i, field in enumerate(embed.fields):
                            if field.name == "Registered":
                                embed.set_field_at(
                                    i,
                                    name="Registered",
                                    value=str(entry_count),
                                    inline=True,
                                )

                    # Create disabled view
                    disabled_view = ui.View()
                    disabled_button = ui.Button(
                        label="Registration Closed",
                        style=discord.ButtonStyle.secondary,
                        disabled=True,
                    )
                    disabled_view.add_item(disabled_button)

                    await message.edit(embed=embed, view=disabled_view)
            except Exception as e:
                log.warning(f"[TOURNAMENT] Could not update registration message: {e}")

        await interaction.followup.send(
            f"✅ Registration closed for **{tournament.name}**!\n\n"
            f"**Entries:** {entry_count}/{tournament.size}\n\n"
            f"Use `/tournament_start` when ready to generate the bracket.",
            ephemeral=True,
        )

        log.info(
            f"[TOURNAMENT] Closed registration for tournament {tournament.id} "
            f"with {entry_count} entries"
        )

    # -------------------------------------------------------------------------
    # /tournament_cancel
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="tournament_cancel",
        description="Cancel the current tournament (Admin only)",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def tournament_cancel(
        self,
        interaction: discord.Interaction,
    ):
        """Cancel the current tournament."""
        await interaction.response.defer(ephemeral=True)

        # Get active tournament
        tournament = await self.tournament_service.get_active_for_guild(
            interaction.guild.id
        )

        if not tournament:
            await interaction.followup.send(
                "❌ No active tournament found.",
                ephemeral=True,
            )
            return

        # Update status
        await self.tournament_service.set_status(tournament.id, "cancelled")

        await interaction.followup.send(
            f"✅ Tournament **{tournament.name}** has been cancelled.",
            ephemeral=True,
        )

        log.info(f"[TOURNAMENT] Cancelled tournament {tournament.id}")

    # -------------------------------------------------------------------------
    # /tournament_status
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="tournament_status",
        description="View current tournament status (Admin only)",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def tournament_status(
        self,
        interaction: discord.Interaction,
    ):
        """View current tournament status."""
        # Get active tournament
        tournament = await self.tournament_service.get_active_for_guild(
            interaction.guild.id
        )

        if not tournament:
            await interaction.response.send_message(
                "ℹ️ No active tournament. Use `/tournament_create` to start one.",
                ephemeral=True,
            )
            return

        entry_count = await self.tournament_service.count_entries(tournament.id)

        embed = discord.Embed(
            title=f"🏆 {tournament.name}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Format", value=tournament.format, inline=True)
        embed.add_field(name="Size", value=str(tournament.size), inline=True)
        embed.add_field(name="Status", value=tournament.status, inline=True)
        embed.add_field(
            name="Entries",
            value=f"{entry_count}/{tournament.size}",
            inline=True,
        )
        embed.set_footer(text=f"Tournament ID: {tournament.id}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -------------------------------------------------------------------------
    # /tournament_entries
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="tournament_entries",
        description="View registered entries (Admin only)",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def tournament_entries(
        self,
        interaction: discord.Interaction,
    ):
        """View all registered entries."""
        # Get active tournament
        tournament = await self.tournament_service.get_active_for_guild(
            interaction.guild.id
        )

        if not tournament:
            await interaction.response.send_message(
                "ℹ️ No active tournament.",
                ephemeral=True,
            )
            return

        entries = await self.tournament_service.list_entries(tournament.id)

        if not entries:
            await interaction.response.send_message(
                f"**{tournament.name}** has no entries yet.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📋 {tournament.name} — Entries",
            color=discord.Color.blue(),
        )

        lines = []
        for i, entry in enumerate(entries, 1):
            if tournament.format == "1v1":
                lines.append(f"{i}. <@{entry.player1_id}>")
            else:
                team_name = entry.team_name or f"Team {entry.id}"
                lines.append(
                    f"{i}. **{team_name}** — <@{entry.player1_id}> + <@{entry.player2_id}>"
                )

        embed.description = "\n".join(lines) if lines else "No entries"
        embed.set_footer(text=f"{len(entries)}/{tournament.size} entries")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -------------------------------------------------------------------------
    # /tournament_start
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="tournament_start",
        description="Generate bracket and start the tournament (Admin only)",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def tournament_start(
        self,
        interaction: discord.Interaction,
    ):
        """Generate bracket and start the tournament."""
        await interaction.response.defer(ephemeral=True)

        # Get active tournament
        tournament = await self.tournament_service.get_active_for_guild(
            interaction.guild.id
        )

        if not tournament:
            await interaction.followup.send(
                "❌ No active tournament found.",
                ephemeral=True,
            )
            return

        # Check status
        if tournament.status != "reg_closed":
            await interaction.followup.send(
                f"❌ Cannot start tournament. Status is **{tournament.status}**.\n"
                f"Use `/tournament_close_registration` first.",
                ephemeral=True,
            )
            return

        # Build bracket
        matches, error = await self.tournament_service.build_bracket(tournament.id)

        if error:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        # Update status
        await self.tournament_service.set_status(tournament.id, "in_progress")

        # Build match list for display
        pending_matches = [m for m in matches if m.status == "pending"]
        bye_matches = [m for m in matches if m.status == "completed"]

        # Create embed with round 1 matches
        embed = discord.Embed(
            title=f"🏆 {tournament.name} — Round 1",
            description="Bracket generated! Here are the Round 1 matches:",
            color=discord.Color.green(),
        )

        # Show pending matches
        match_lines = []
        for m in pending_matches:
            entry1_name = await self.tournament_service.get_entry_display_name(
                m.entry1_id, tournament.format
            )
            entry2_name = await self.tournament_service.get_entry_display_name(
                m.entry2_id, tournament.format
            )
            match_lines.append(f"**Match {m.id}:** {entry1_name} vs {entry2_name}")

        if match_lines:
            embed.add_field(
                name=f"⚔️ Active Matches ({len(pending_matches)})",
                value="\n".join(match_lines[:10]),  # Limit for embed size
                inline=False,
            )

        # Show BYE info
        if bye_matches:
            embed.add_field(
                name="👋 BYE Advances",
                value=f"{len(bye_matches)} entries advance with a BYE",
                inline=False,
            )

        embed.add_field(
            name="📋 Next Steps",
            value=(
                "Use `/tournament_report_result` to record match results.\n"
                f"Match IDs: {', '.join(str(m.id) for m in pending_matches[:15])}"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Tournament ID: {tournament.id}")

        # Post to admin channel
        config = await self.config_service.get(interaction.guild.id)
        if config and config.admin_channel:
            admin_channel = interaction.guild.get_channel(config.admin_channel)
            if admin_channel:
                await admin_channel.send(embed=embed)

        await interaction.followup.send(
            f"✅ Tournament **{tournament.name}** has started!\n\n"
            f"**Round 1:** {len(pending_matches)} matches to play, {len(bye_matches)} BYEs.\n\n"
            f"Bracket posted to admin channel.",
            ephemeral=True,
        )

        log.info(
            f"[TOURNAMENT] Started tournament {tournament.id} with "
            f"{len(pending_matches)} round 1 matches"
        )

    # -------------------------------------------------------------------------
    # /ums_report_result
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="ums_report_result",
        description="Report a match result (Admin only)",
    )
    @app_commands.describe(
        winner="The winner of the match",
        loser="The loser of the match",
        score="Optional score (e.g., 2-1)",
        tournament_id="Optional tournament ID (defaults to active)",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def ums_report_result(
        self,
        interaction: discord.Interaction,
        winner: discord.Member,
        loser: discord.Member,
        score: Optional[str] = None,
        tournament_id: Optional[int] = None,
    ):
        """Report a match result."""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need Manage Server permission to report results.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Report result
        tournament, match, error = await self.tournament_service.report_result(
            guild_id=interaction.guild.id,
            winner_id=winner.id,
            loser_id=loser.id,
            score=score,
            tournament_id=tournament_id,
        )

        if error:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        # Build response
        response = (
            f"✅ **Match Result Recorded**\n\n"
            f"**Winner:** {winner.mention}\n"
            f"**Loser:** {loser.mention}\n"
        )
        if score:
            response += f"**Score:** {score}\n"

        response += f"\n**Match ID:** {match.id} | **Round:** {match.round}"

        if tournament.status == "completed":
            response += f"\n\n🏆 **Tournament Complete!** {winner.mention} wins!"

        await interaction.followup.send(response, ephemeral=True)

        log.info(
            f"[TOURNAMENT] Admin {interaction.user.id} reported result: "
            f"winner={winner.id}, loser={loser.id}, match={match.id}"
        )

    # -------------------------------------------------------------------------
    # DEV-ONLY COMMANDS
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="ums_dev_fill_dummies",
        description="[DEV] Fill tournament with dummy entries for testing",
    )
    @app_commands.describe(
        tournament="Tournament code or ID (defaults to active tournament)",
        count="Number of dummy entries to add (defaults to fill remaining slots)",
    )
    @app_commands.guild_only()
    async def dev_fill_dummies(
        self,
        interaction: discord.Interaction,
        tournament: Optional[str] = None,
        count: Optional[int] = None,
    ):
        """Fill tournament with dummy entries for dev testing."""
        # Dev-only gate
        if not is_dev_user(interaction.user):
            await interaction.response.send_message(
                "❌ This command is for development use only.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Resolve tournament by code or ID
        if tournament:
            t = await self.tournament_service.get_by_code_or_id(tournament)
            if not t or t.guild_id != interaction.guild.id:
                await interaction.followup.send(
                    f"❌ Tournament `{tournament}` not found in this server.",
                    ephemeral=True,
                )
                return
        else:
            # Get latest tournament with suitable status
            t = await self.tournament_service.get_active_for_guild(interaction.guild.id)
            if not t:
                await interaction.followup.send(
                    "❌ No suitable tournament found to fill with dummies.",
                    ephemeral=True,
                )
                return

        tournament_obj = t  # Renamed to avoid shadowing

        # Check status
        if tournament_obj.status not in ("draft", "reg_open", "reg_closed"):
            await interaction.followup.send(
                f"❌ Tournament status is **{tournament_obj.status}**. "
                f"Cannot add dummies to an in-progress or completed tournament.",
                ephemeral=True,
            )
            return

        # Calculate how many to add
        current_entries = await self.tournament_service.count_entries(tournament_obj.id)
        max_size = tournament_obj.size
        remaining = max_size - current_entries

        if remaining <= 0:
            await interaction.followup.send(
                f"❌ Tournament is already full ({current_entries}/{max_size}).",
                ephemeral=True,
            )
            return

        to_add = min(count, remaining) if count else remaining

        if to_add <= 0:
            await interaction.followup.send(
                "❌ No slots available to fill.",
                ephemeral=True,
            )
            return

        # Generate dummy entries
        # Use high synthetic IDs: 990000000000xxxx (won't conflict with real Discord IDs)
        base_dummy_id = 9900000000000000 + (tournament_obj.id * 1000)
        added = 0

        for i in range(to_add):
            dummy_player_id = base_dummy_id + current_entries + i

            # Create dummy player record (optional, entries work with just player_id)
            try:
                await self.bot.player_service.db.execute(
                    """
                    INSERT OR IGNORE INTO players (user_id, discord_id, display_name, region, claimed_rank, has_onboarded)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (
                        dummy_player_id,
                        dummy_player_id,
                        f"DummyPlayer{i+1}",
                        "USE",
                        "Gold",
                    ),
                )
                await self.bot.player_service.db.commit()
            except Exception as e:
                log.warning(f"[DEV] Could not create dummy player record: {e}")

            # Add tournament entry
            entry = await self.tournament_service.add_dummy_entry(
                tournament_id=tournament_obj.id,
                dummy_player_id=dummy_player_id,
            )
            if entry:
                added += 1

        new_count = current_entries + added

        log.info(
            f"[DEV] Added {added} dummy entries to tournament {tournament_obj.id} (code={tournament_obj.tournament_code})"
        )

        await interaction.followup.send(
            f"✅ Added **{added}** dummy entries to **{tournament_obj.name}** (`{tournament_obj.tournament_code}`).\n"
            f"Total entries: **{new_count}/{max_size}**",
            ephemeral=True,
        )

    @app_commands.command(
        name="ums_dev_auto_resolve",
        description="[DEV] Auto-resolve all dummy vs dummy matches in tournament",
    )
    @app_commands.describe(
        tournament="Tournament code or ID (defaults to active in_progress tournament)",
    )
    @app_commands.guild_only()
    async def dev_auto_resolve(
        self,
        interaction: discord.Interaction,
        tournament: Optional[str] = None,
    ):
        """Auto-resolve dummy vs dummy matches for dev testing."""
        # Dev-only gate
        if not is_dev_user(interaction.user):
            await interaction.response.send_message(
                "❌ This command is for development use only.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Resolve tournament by code or ID
        if tournament:
            tournament_obj = await self.tournament_service.get_by_code_or_id(tournament)
            if not tournament_obj or tournament_obj.guild_id != interaction.guild.id:
                await interaction.followup.send(
                    f"❌ Tournament `{tournament}` not found in this server.",
                    ephemeral=True,
                )
                return
        else:
            tournament_obj = await self.tournament_service.get_active_for_guild(
                interaction.guild.id
            )
            if not tournament_obj:
                await interaction.followup.send(
                    "❌ No active tournament found.",
                    ephemeral=True,
                )
                return

        if tournament_obj.status != "in_progress":
            await interaction.followup.send(
                f"❌ Tournament status is **{tournament_obj.status}**. Must be in_progress.",
                ephemeral=True,
            )
            return

        # Walk bracket and resolve dummy vs dummy matches
        resolved = 0
        skipped_live = 0
        errors = []

        # Keep resolving until no more dummy vs dummy matches
        while True:
            matches = await self.tournament_service.list_matches(tournament_obj.id)
            pending = [
                m for m in matches if m.status == "pending" and m.entry2_id is not None
            ]

            if not pending:
                break

            resolved_this_round = 0

            for match in pending:
                entry1_dummy, entry2_dummy, both_dummy = (
                    await self.tournament_service.is_dummy_match(match.id)
                )

                if both_dummy:
                    # Auto-resolve
                    t, m, err = await self.tournament_service.auto_resolve_dummy_match(
                        match.id
                    )
                    if err:
                        errors.append(f"Match #{match.id}: {err}")
                    else:
                        resolved += 1
                        resolved_this_round += 1
                else:
                    # Live player involved
                    skipped_live += 1

            if resolved_this_round == 0:
                # No more dummy vs dummy matches to resolve
                break

            # Refresh tournament status
            tournament_obj = await self.tournament_service.get_by_id(tournament_obj.id)
            if tournament_obj.status == "completed":
                break

        # Update dashboard (will show trophy if completed)
        await update_tournament_dashboard(
            self.bot, interaction.guild, tournament_obj.id
        )

        # Build response
        response = f"✅ **Auto-Resolve Complete**\n\n"
        response += f"**Tournament:** {tournament_obj.name} (`{tournament_obj.tournament_code}`)\n"
        response += f"**Resolved:** {resolved} dummy vs dummy matches\n"
        response += f"**Skipped:** {skipped_live} matches with live players\n"
        response += f"**Status:** {tournament_obj.status}\n"

        if errors:
            response += f"\n**Errors:**\n" + "\n".join(errors[:5])

        await interaction.followup.send(response, ephemeral=True)

        log.info(
            f"[DEV] Auto-resolved {resolved} matches in tournament {tournament_obj.id} (code={tournament_obj.tournament_code})"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TournamentsCog(bot))
