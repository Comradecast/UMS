"""
ui/tournament_views.py — Tournament Dashboard and Admin Panel Views
===================================================================
Dashboard, admin control panel, and related confirmation views.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import ui
from discord.ext import commands

# Brand kit imports
from ui.brand import Colors, FOOTER_TEXT, create_embed, success_embed, error_embed

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class DashboardView(ui.View):
    """Tournament dashboard view with My Match and Refresh buttons."""

    def __init__(self, bot: commands.Bot, tournament_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.tournament_id = tournament_id

    @ui.button(
        label="🏅 My Match",
        style=discord.ButtonStyle.primary,
        custom_id="dashboard_my_match",
        row=0,
    )
    async def my_match(self, interaction: discord.Interaction, button: ui.Button):
        """Find and report result for user's current match."""
        # Get tournament
        tournament = await self.bot.tournament_service.get_by_id(self.tournament_id)
        if not tournament:
            await interaction.response.send_message(
                "❌ Tournament not found.",
                ephemeral=True,
            )
            return

        if tournament.status != "in_progress":
            await interaction.response.send_message(
                "❌ This tournament is not currently in progress.",
                ephemeral=True,
            )
            return

        # Find active match for this player
        match = await self.bot.tournament_service.find_active_match_for_player(
            self.tournament_id,
            interaction.user.id,
        )

        if not match:
            await interaction.response.send_message(
                "❌ You do not have an active match right now.",
                ephemeral=True,
            )
            return

        # Get player's entry and opponent's entry
        player_entry = await self.bot.tournament_service.get_entry_for_player(
            self.tournament_id,
            interaction.user.id,
        )

        opponent_entry_id = (
            match.entry2_id if match.entry1_id == player_entry.id else match.entry1_id
        )
        opponent_name = await self.bot.tournament_service.get_entry_display_name(
            opponent_entry_id, tournament.format
        )

        # Show modal
        from ui.match_modals import ReportResultModal

        modal = ReportResultModal(
            self.bot,
            tournament,
            match,
            player_entry.id,
            opponent_entry_id,
            opponent_name,
        )
        await interaction.response.send_modal(modal)

    @ui.button(
        label="📊 Refresh",
        style=discord.ButtonStyle.secondary,
        custom_id="dashboard_refresh",
        row=0,
    )
    async def refresh_dashboard(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Refresh the dashboard display."""
        await interaction.response.defer()

        # Import here to avoid circular imports
        from cogs.tournaments import update_tournament_dashboard

        await update_tournament_dashboard(
            self.bot, interaction.guild, self.tournament_id
        )


class AdminControlPanel(ui.View):
    """Persistent admin control panel for tournament management."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)  # Persistent
        self.bot = bot

    @ui.button(
        label="🏆 Create Tournament",
        style=discord.ButtonStyle.primary,
        custom_id="admin_create_tournament",
        row=0,
    )
    async def create_tournament(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Open create tournament modal."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Admin only.", ephemeral=True
            )

        # Check for existing active tournament
        tournament = await self.bot.tournament_service.get_active_for_guild(
            interaction.guild.id
        )
        if tournament:
            await interaction.response.send_message(
                f"❌ There's already an active tournament: **{tournament.name}** ({tournament.status})\n"
                f"Cancel or complete it first.",
                ephemeral=True,
            )
            return

        modal = CreateTournamentModal(self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(
        label="📖 Open Registration",
        style=discord.ButtonStyle.success,
        custom_id="admin_open_reg",
        row=0,
    )
    async def open_registration(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Open registration for current tournament."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Admin only.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        tournament = await self.bot.tournament_service.get_active_for_guild(
            interaction.guild.id
        )
        if not tournament:
            await interaction.followup.send("❌ No active tournament.", ephemeral=True)
            return

        if tournament.status not in ("draft", "reg_open"):
            await interaction.followup.send(
                f"❌ Can't open registration. Status is **{tournament.status}**.",
                ephemeral=True,
            )
            return

        # Update status
        await self.bot.tournament_service.set_status(tournament.id, "reg_open")

        # Get announce channel
        config = await self.bot.guild_config_service.get(interaction.guild.id)
        target = interaction.channel
        if config and config.announce_channel:
            ch = interaction.guild.get_channel(config.announce_channel)
            if ch:
                target = ch

        # Post registration panel
        cog = self.bot.get_cog("TournamentsCog")
        if cog:
            format_text = "Solo (1v1)" if tournament.format == "1v1" else "Teams (2v2)"
            reg_embed = create_embed(
                tournament.name,
                "**Registration is now OPEN!**\n\nClick the button below to register.",
            )
            reg_embed.add_field(name="Format", value=format_text, inline=True)
            reg_embed.add_field(
                name="Max Entries", value=str(tournament.size), inline=True
            )
            reg_embed.add_field(name="Registered", value="0", inline=True)

            from ui.registration_views import Registration1v1View, Registration2v2View

            if tournament.format == "1v1":
                view = Registration1v1View(cog, tournament.id)
            else:
                view = Registration2v2View(cog, tournament.id)

            reg_message = await target.send(embed=reg_embed, view=view)
            await self.bot.tournament_service.set_registration_message(
                tournament.id, reg_message.id, target.id
            )

        await interaction.followup.send(
            f"✅ Registration opened for **{tournament.name}**!\nPanel posted in {target.mention}",
            ephemeral=True,
        )

    @ui.button(
        label="🔒 Close Registration",
        style=discord.ButtonStyle.secondary,
        custom_id="admin_close_reg",
        row=1,
    )
    async def close_registration(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Close registration."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Admin only.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        tournament = await self.bot.tournament_service.get_active_for_guild(
            interaction.guild.id
        )
        if not tournament:
            await interaction.followup.send("❌ No active tournament.", ephemeral=True)
            return

        if tournament.status != "reg_open":
            await interaction.followup.send(
                f"❌ Can't close registration. Status is **{tournament.status}**.",
                ephemeral=True,
            )
            return

        entry_count = await self.bot.tournament_service.count_entries(tournament.id)
        await self.bot.tournament_service.set_status(tournament.id, "reg_closed")

        await interaction.followup.send(
            f"✅ Registration closed for **{tournament.name}**!\n"
            f"**Entries:** {entry_count}/{tournament.size}\n\n"
            f"Click **Start Tournament** when ready.",
            ephemeral=True,
        )

    @ui.button(
        label="🚀 Start Tournament",
        style=discord.ButtonStyle.success,
        custom_id="admin_start_tournament",
        row=1,
    )
    async def start_tournament(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Generate bracket and start."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Admin only.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        tournament = await self.bot.tournament_service.get_active_for_guild(
            interaction.guild.id
        )
        if not tournament:
            await interaction.followup.send("❌ No active tournament.", ephemeral=True)
            return

        if tournament.status != "reg_closed":
            await interaction.followup.send(
                f"❌ Can't start. Status is **{tournament.status}**.\n"
                f"Close registration first.",
                ephemeral=True,
            )
            return

        # Build bracket
        matches, error = await self.bot.tournament_service.build_bracket(tournament.id)
        if error:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        await self.bot.tournament_service.set_status(tournament.id, "in_progress")

        pending = [m for m in matches if m.status == "pending"]
        byes = [m for m in matches if m.status == "completed"]

        # Refresh tournament to get updated status
        tournament = await self.bot.tournament_service.get_by_id(tournament.id)

        # Delete registration panel (cleanup)
        reg_deleted = False
        if tournament.reg_channel_id and tournament.reg_message_id:
            try:
                reg_channel = interaction.guild.get_channel(tournament.reg_channel_id)
                if reg_channel:
                    reg_msg = await reg_channel.fetch_message(tournament.reg_message_id)
                    await reg_msg.delete()
                    reg_deleted = True
                    log.info(
                        f"[TOURNAMENT] Deleted registration panel for tournament {tournament.id}"
                    )
            except discord.NotFound:
                log.warning(
                    f"[TOURNAMENT] Registration message already deleted for tournament {tournament.id}"
                )
            except Exception as e:
                log.warning(f"[TOURNAMENT] Could not delete registration panel: {e}")

        # Post tournament dashboard
        from cogs.tournaments import post_tournament_dashboard

        dashboard_posted = await post_tournament_dashboard(
            self.bot, interaction.guild, tournament
        )

        await interaction.followup.send(
            (
                f"✅ **{tournament.name}** has started!\n\n"
                f"**Round 1:** {len(pending)} matches, {len(byes)} BYEs\n"
                f"📊 Tournament dashboard posted to announcements channel."
                if dashboard_posted
                else f"⚠️ Could not post dashboard. Check announce channel config."
            ),
            ephemeral=True,
        )

    @ui.button(
        label="📊 Status",
        style=discord.ButtonStyle.secondary,
        custom_id="admin_tournament_status",
        row=1,
    )
    async def tournament_status(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Show current tournament status."""
        tournament = await self.bot.tournament_service.get_active_for_guild(
            interaction.guild.id
        )

        if not tournament:
            await interaction.response.send_message(
                "ℹ️ No active tournament. Click **Create Tournament** to start.",
                ephemeral=True,
            )
            return

        entry_count = await self.bot.tournament_service.count_entries(tournament.id)

        embed = create_embed(tournament.name, f"Status: **{tournament.status}**")
        embed.add_field(name="Format", value=tournament.format, inline=True)
        embed.add_field(name="Size", value=str(tournament.size), inline=True)
        embed.add_field(name="Status", value=tournament.status, inline=True)
        embed.add_field(
            name="Entries", value=f"{entry_count}/{tournament.size}", inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(
        label="❌ Cancel",
        style=discord.ButtonStyle.danger,
        custom_id="admin_cancel_tournament",
        row=2,
    )
    async def cancel_tournament(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Cancel current tournament."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Admin only.", ephemeral=True
            )

        tournament = await self.bot.tournament_service.get_active_for_guild(
            interaction.guild.id
        )
        if not tournament:
            await interaction.response.send_message(
                "❌ No active tournament to cancel.",
                ephemeral=True,
            )
            return

        await self.bot.tournament_service.set_status(tournament.id, "cancelled")
        await interaction.response.send_message(
            f"✅ **{tournament.name}** has been cancelled.",
            ephemeral=True,
        )

    @ui.button(
        label="🔁 Refresh Panels",
        style=discord.ButtonStyle.secondary,
        custom_id="admin_refresh_panels",
        row=2,
    )
    async def refresh_panels(self, interaction: discord.Interaction, button: ui.Button):
        """Refresh UMS panels (onboarding + admin)."""
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "❌ Admin only.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        # Get guild config
        config = await self.bot.guild_config_service.get(interaction.guild.id)
        if not config:
            await interaction.followup.send(
                "❌ No configuration found. Run quick setup first.",
                ephemeral=True,
            )
            return

        refreshed = []

        # Refresh onboarding panel
        if config.onboarding_channel:
            channel = interaction.guild.get_channel(config.onboarding_channel)
            if channel:
                try:
                    # Import here to avoid circular imports
                    from cogs.onboarding_view import PersistentOnboardingView

                    embed = create_embed(
                        "Player Onboarding",
                        "Complete your profile to participate in tournaments.\n\nClick the button below to set your region and rank.",
                    )
                    view = PersistentOnboardingView(self.bot)
                    await channel.send(embed=embed, view=view)
                    refreshed.append("Onboarding Panel")
                except Exception as e:
                    log.warning(f"[REFRESH] Could not refresh onboarding: {e}")

        # Refresh admin panel
        if config.admin_channel:
            channel = interaction.guild.get_channel(config.admin_channel)
            if channel:
                try:
                    from cogs.tournaments import post_admin_panel

                    await post_admin_panel(self.bot, channel)
                    refreshed.append("Admin Panel")
                except Exception as e:
                    log.warning(f"[REFRESH] Could not refresh admin panel: {e}")

        if refreshed:
            await interaction.followup.send(
                f"✅ Panels refreshed: {', '.join(refreshed)}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "❌ No panels to refresh. Check channel configuration.",
                ephemeral=True,
            )

    @ui.button(
        label="🗑️ Delete Tournament",
        style=discord.ButtonStyle.danger,
        custom_id="admin_delete_tournament",
        row=2,
    )
    async def delete_tournament(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Archive and delete tournament data."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Admin only.", ephemeral=True
            )

        # Get completed/cancelled tournament
        tournament = await self.bot.tournament_service.get_active_for_guild(
            interaction.guild.id
        )

        # If no active, look for most recent completed/cancelled
        if not tournament:
            # Query for most recent completed/cancelled
            cursor = await self.bot.tournament_service.db.execute(
                """
                SELECT * FROM tournaments
                WHERE guild_id = ? AND status IN ('completed', 'cancelled')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (interaction.guild.id,),
            )
            row = await cursor.fetchone()
            if row:
                tournament = await self.bot.tournament_service.get_by_id(row["id"])

        if not tournament:
            await interaction.response.send_message(
                "❌ No tournament found to archive.",
                ephemeral=True,
            )
            return

        if tournament.status not in ("completed", "cancelled"):
            await interaction.response.send_message(
                "❌ Finish or cancel the tournament before deleting it.",
                ephemeral=True,
            )
            return

        # Show confirmation
        view = DeleteTournamentConfirmView(self.bot, tournament)
        await interaction.response.send_message(
            f"⚠️ **Delete Tournament: {tournament.name}?**\n\n"
            f"This will:\n"
            f"• Delete all match data and entries\n"
            f"• Clean up registration and dashboard messages from Discord\n"
            f"• Preserve trophy summary (winner/runner-up) in database\n"
            f"• Mark tournament as archived\n\n"
            f"This action cannot be undone.",
            view=view,
            ephemeral=True,
        )


class DeleteTournamentConfirmView(ui.View):
    """Confirmation view for deleting/archiving a tournament."""

    def __init__(self, bot: commands.Bot, tournament):
        super().__init__(timeout=60)
        self.bot = bot
        self.tournament = tournament

    @ui.button(
        label="Yes, Delete Tournament",
        style=discord.ButtonStyle.danger,
    )
    async def confirm_delete(self, interaction: discord.Interaction, button: ui.Button):
        """Confirm deletion."""
        # Fetch tournament before archiving to get message IDs
        tournament = await self.bot.tournament_service.get_by_id(self.tournament.id)
        if not tournament:
            await interaction.response.send_message(
                "❌ Tournament not found.",
                ephemeral=True,
            )
            return

        success, error = await self.bot.tournament_service.archive_tournament(
            self.tournament.id
        )

        if error:
            await interaction.response.send_message(
                f"❌ {error}",
                ephemeral=True,
            )
            return

        # Clean up Discord messages
        messages_deleted = []

        # Delete registration panel
        if tournament.reg_channel_id and tournament.reg_message_id:
            try:
                reg_channel = interaction.guild.get_channel(tournament.reg_channel_id)
                if reg_channel:
                    reg_msg = await reg_channel.fetch_message(tournament.reg_message_id)
                    await reg_msg.delete()
                    messages_deleted.append("registration panel")
                    log.info(
                        f"[TOURNAMENT] Deleted registration panel for archived tournament {tournament.id}"
                    )
            except discord.NotFound:
                log.warning(
                    f"[TOURNAMENT] Registration message already deleted for tournament {tournament.id}"
                )
            except Exception as e:
                log.warning(
                    f"[TOURNAMENT] Could not delete registration panel on archive: {e}"
                )

        # Delete dashboard/trophy message
        if tournament.dashboard_channel_id and tournament.dashboard_message_id:
            try:
                dash_channel = interaction.guild.get_channel(
                    tournament.dashboard_channel_id
                )
                if dash_channel:
                    dash_msg = await dash_channel.fetch_message(
                        tournament.dashboard_message_id
                    )
                    await dash_msg.delete()
                    messages_deleted.append("dashboard/trophy")
                    log.info(
                        f"[TOURNAMENT] Deleted dashboard for archived tournament {tournament.id}"
                    )
            except discord.NotFound:
                log.warning(
                    f"[TOURNAMENT] Dashboard message already deleted for tournament {tournament.id}"
                )
            except Exception as e:
                log.warning(f"[TOURNAMENT] Could not delete dashboard on archive: {e}")

        cleanup_msg = (
            f" ({', '.join(messages_deleted)} cleaned up)" if messages_deleted else ""
        )

        await interaction.response.send_message(
            f"✅ Tournament **{self.tournament.name}** archived{cleanup_msg}.",
            ephemeral=True,
        )

        log.info(
            f"[TOURNAMENT] Archived tournament {self.tournament.id} "
            f"in guild {interaction.guild.id}"
        )

    @ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_delete(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel deletion."""
        await interaction.response.send_message(
            "❌ Deletion cancelled.",
            ephemeral=True,
        )


class CreateTournamentModal(ui.Modal, title="Create Tournament"):
    """Modal for creating a new tournament."""

    name = ui.TextInput(
        label="Tournament Name",
        placeholder="e.g., Weekend 1v1 Cup",
        required=True,
        max_length=100,
    )

    format = ui.TextInput(
        label="Format (1v1 or 2v2)",
        placeholder="1v1",
        required=True,
        max_length=3,
    )

    size = ui.TextInput(
        label="Size (8, 16, 32, or 64)",
        placeholder="8",
        required=True,
        max_length=2,
    )

    allowed_regions = ui.TextInput(
        label="Allowed Regions (optional, comma-separated)",
        placeholder="e.g., USE,EU,USW (leave blank for any)",
        required=False,
        max_length=100,
    )

    allowed_ranks = ui.TextInput(
        label="Allowed Ranks (optional, comma-separated)",
        placeholder="e.g., Gold,Platinum (leave blank for any)",
        required=False,
        max_length=100,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        """Create the tournament."""
        # Validate format
        fmt = self.format.value.strip().lower()
        if fmt not in ("1v1", "2v2"):
            await interaction.response.send_message(
                "❌ Format must be **1v1** or **2v2**.",
                ephemeral=True,
            )
            return

        # Validate size
        try:
            sz = int(self.size.value.strip())
            if sz not in (8, 16, 32, 64):
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "❌ Size must be **8**, **16**, **32**, or **64**.",
                ephemeral=True,
            )
            return

        # Parse restrictions (convert to uppercase CSV)
        regions = None
        if self.allowed_regions.value and self.allowed_regions.value.strip():
            regions = ",".join(
                r.strip().upper()
                for r in self.allowed_regions.value.split(",")
                if r.strip()
            )

        ranks = None
        if self.allowed_ranks.value and self.allowed_ranks.value.strip():
            # Capitalize first letter of each rank
            ranks = ",".join(
                r.strip().title()
                for r in self.allowed_ranks.value.split(",")
                if r.strip()
            )

        # Create tournament
        tournament, error = await self.bot.tournament_service.create_tournament(
            guild_id=interaction.guild.id,
            name=self.name.value.strip(),
            format=fmt,
            size=sz,
            allowed_regions=regions,
            allowed_ranks=ranks,
        )

        if error:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        # Build response
        response = (
            f"✅ Created **{tournament.name}**!\n\n"
            f"**Format:** {tournament.format} | **Size:** {tournament.size}\n"
        )
        if regions:
            response += f"**Regions:** {regions}\n"
        if ranks:
            response += f"**Ranks:** {ranks}\n"
        response += "\nClick **Open Registration** to start signups."

        await interaction.response.send_message(response, ephemeral=True)

        log.info(
            f"[TOURNAMENT] Created '{tournament.name}' via panel in guild {interaction.guild.id}"
        )


# -----------------------------------------------------------------------------
# Admin Override Wizard Views
# -----------------------------------------------------------------------------


class MatchOverrideSelect(ui.Select):
    """Dropdown to select an unresolved match for admin override."""

    def __init__(self, matches: list, match_names: dict[int, tuple[str, str]]):
        """
        Args:
            matches: List of Match objects (pending only)
            match_names: Dict mapping match.id -> (entry1_name, entry2_name)
        """
        self.matches = matches
        self.match_names = match_names

        options = []
        for match in matches[:25]:  # Discord limit
            entry1_name, entry2_name = match_names.get(match.id, ("???", "???"))
            options.append(
                discord.SelectOption(
                    label=f"R{match.round} M{match.match_index + 1}",
                    description=f"{entry1_name} vs {entry2_name}"[:100],
                    value=str(match.id),
                )
            )

        super().__init__(
            placeholder="Select a match to override...",
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        """When a match is selected, show winner selection buttons."""
        match_id = int(self.values[0])
        match = next((m for m in self.matches if m.id == match_id), None)

        if not match:
            embed = error_embed("Match Not Found", "Could not find the selected match.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        entry1_name, entry2_name = self.match_names.get(
            match_id, ("Entry 1", "Entry 2")
        )

        embed = create_embed(
            "Select Winner", f"**Round {match.round} • Match {match.match_index + 1}**"
        )
        embed.add_field(name="Player 1", value=entry1_name, inline=True)
        embed.add_field(name="vs", value="⚔️", inline=True)
        embed.add_field(name="Player 2", value=entry2_name, inline=True)

        view = WinnerSelectView(
            interaction.client,
            match,
            match.entry1_id,
            match.entry2_id,
            entry1_name,
            entry2_name,
        )

        await interaction.response.edit_message(embed=embed, view=view)


class MatchOverrideView(ui.View):
    """View containing the match selection dropdown."""

    def __init__(self, matches: list, match_names: dict[int, tuple[str, str]]):
        super().__init__(timeout=120)
        self.add_item(MatchOverrideSelect(matches, match_names))

    @ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel the override wizard."""
        embed = create_embed(
            "Override Cancelled", "No changes were made.", Colors.WARNING
        )
        await interaction.response.edit_message(embed=embed, view=None)


class WinnerSelectView(ui.View):
    """View with buttons to select the winner of a match."""

    def __init__(
        self,
        bot: commands.Bot,
        match,
        entry1_id: int,
        entry2_id: int,
        entry1_name: str,
        entry2_name: str,
    ):
        super().__init__(timeout=60)
        self.bot = bot
        self.match = match
        self.entry1_id = entry1_id
        self.entry2_id = entry2_id
        self.entry1_name = entry1_name
        self.entry2_name = entry2_name

    @ui.button(
        label="Winner: Player 1",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def winner_entry1(self, interaction: discord.Interaction, button: ui.Button):
        """Set entry1 as winner."""
        await self._report_winner(interaction, self.entry1_id, self.entry1_name)

    @ui.button(
        label="Winner: Player 2",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def winner_entry2(self, interaction: discord.Interaction, button: ui.Button):
        """Set entry2 as winner."""
        await self._report_winner(interaction, self.entry2_id, self.entry2_name)

    @ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel."""
        embed = create_embed(
            "Override Cancelled", "No changes were made.", Colors.WARNING
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def _report_winner(
        self,
        interaction: discord.Interaction,
        winner_entry_id: int,
        winner_name: str,
    ):
        """Report the winner using TournamentService."""
        await interaction.response.defer(ephemeral=True)

        tournament, match, error = (
            await self.bot.tournament_service.report_result_by_entry(
                match_id=self.match.id,
                winner_entry_id=winner_entry_id,
                score="ADMIN",
            )
        )

        if error:
            embed = error_embed("Override Failed", error)
            await interaction.edit_original_response(embed=embed, view=None)
            return

        # Update dashboard
        from cogs.tournaments import update_tournament_dashboard

        await update_tournament_dashboard(self.bot, interaction.guild, tournament.id)

        embed = success_embed("Match Result Updated", f"**Winner:** {winner_name}")
        embed.add_field(name="Round", value=str(self.match.round), inline=True)
        embed.add_field(
            name="Match", value=str(self.match.match_index + 1), inline=True
        )

        if tournament.status == "completed":
            embed.add_field(
                name="Tournament Complete",
                value=f"🏆 {winner_name} wins the tournament!",
                inline=False,
            )

        await interaction.edit_original_response(embed=embed, view=None)

        log.info(
            f"[TOURNAMENT] Admin {interaction.user.id} override: "
            f"match={self.match.id}, winner_entry={winner_entry_id}"
        )


# -----------------------------------------------------------------------------
# Dev Bracket Tools View (DEV-ONLY)
# -----------------------------------------------------------------------------


class DevMatchSelect(ui.Select):
    """Dropdown to select a match for dev advance."""

    def __init__(
        self,
        view: "DevBracketToolsView",
        matches: list,
        match_names: dict[int, tuple[str, str]],
    ):
        self.parent_view = view
        self.matches = matches
        self.match_names = match_names

        options = []
        for match in matches[:25]:  # Discord limit
            entry1_name, entry2_name = match_names.get(match.id, ("???", "???"))
            options.append(
                discord.SelectOption(
                    label=f"R{match.round} M{match.match_index + 1}",
                    description=f"{entry1_name} vs {entry2_name}"[:100],
                    value=str(match.id),
                )
            )

        super().__init__(
            placeholder="Select a match to advance...",
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        """When a match is selected, resolve it with random winner."""
        import random

        match_id = int(self.values[0])
        match = next((m for m in self.matches if m.id == match_id), None)

        if not match:
            embed = error_embed("Match Not Found", "Could not find the selected match.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # Pick random winner
        winner_entry_id = random.choice([match.entry1_id, match.entry2_id])

        tournament, updated_match, error = (
            await self.parent_view.bot.tournament_service.report_result_by_entry(
                match_id=match.id,
                winner_entry_id=winner_entry_id,
                score="DEV",
            )
        )

        if error:
            embed = error_embed("Advance Failed", error)
            await interaction.edit_original_response(embed=embed, view=None)
            return

        # Get winner name
        winner_name = (
            await self.parent_view.bot.tournament_service.get_entry_display_name(
                winner_entry_id, tournament.format
            )
        )

        # Update dashboard
        from cogs.tournaments import update_tournament_dashboard

        await update_tournament_dashboard(
            self.parent_view.bot, interaction.guild, tournament.id
        )

        log.info(
            f"[DEV] Manually advanced match {match.id} in tournament {tournament.id}"
        )

        # Refresh the main panel
        await self.parent_view.refresh_panel(
            interaction,
            f"Advanced R{match.round} M{match.match_index + 1}: Winner → {winner_name}",
        )


class DevBracketToolsView(ui.View):
    """Dev-only ephemeral panel for bracket testing tools."""

    def __init__(self, bot: commands.Bot, tournament):
        super().__init__(timeout=300)  # 5 min timeout
        self.bot = bot
        self.tournament = tournament
        self.message_content = None

    async def refresh_panel(
        self, interaction: discord.Interaction, status_msg: str = None
    ):
        """Refresh the panel with current tournament state."""
        # Refresh tournament
        self.tournament = await self.bot.tournament_service.get_by_id(
            self.tournament.id
        )

        # Get match counts
        all_matches = await self.bot.tournament_service.list_matches(self.tournament.id)
        pending = [m for m in all_matches if m.status == "pending"]
        completed = [m for m in all_matches if m.status == "completed"]

        embed = create_embed(
            "Dev Bracket Tools",
            f"**Tournament:** {self.tournament.name}\n**Code:** `{self.tournament.tournament_code}`",
        )
        embed.add_field(name="Status", value=self.tournament.status, inline=True)
        embed.add_field(name="Pending", value=str(len(pending)), inline=True)
        embed.add_field(name="Completed", value=str(len(completed)), inline=True)

        if status_msg:
            embed.add_field(name="Last Action", value=status_msg, inline=False)

        embed.add_field(
            name="Actions",
            value=(
                "• **Advance One** — Pick and resolve a single match\n"
                "• **Advance Round** — Resolve all matches in lowest round\n"
                "• **Auto-resolve** — Resolve all dummy vs dummy matches"
            ),
            inline=False,
        )

        # Disable buttons if tournament completed
        if self.tournament.status == "completed":
            for item in self.children:
                if hasattr(item, "disabled"):
                    item.disabled = True

        await interaction.edit_original_response(embed=embed, view=self)

    @ui.button(
        label="Advance One Match",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def advance_one(self, interaction: discord.Interaction, button: ui.Button):
        """Show match selector for single match advance."""
        await interaction.response.defer(ephemeral=True)

        # Get pending matches
        all_matches = await self.bot.tournament_service.list_matches(self.tournament.id)
        pending = [
            m
            for m in all_matches
            if m.status == "pending" and m.entry1_id and m.entry2_id
        ]

        if not pending:
            await self.refresh_panel(interaction, "No pending matches to advance.")
            return

        # Build match names
        match_names = {}
        for match in pending:
            entry1_name = await self.bot.tournament_service.get_entry_display_name(
                match.entry1_id, self.tournament.format
            )
            entry2_name = await self.bot.tournament_service.get_entry_display_name(
                match.entry2_id, self.tournament.format
            )
            match_names[match.id] = (entry1_name, entry2_name)

        # Show selector
        embed = create_embed(
            "Select Match to Advance",
            f"**Tournament:** {self.tournament.name}\n\nSelect a match to resolve with random winner:",
        )

        # Create a new view with just the select
        select_view = ui.View(timeout=60)
        select_view.add_item(DevMatchSelect(self, pending, match_names))

        await interaction.edit_original_response(embed=embed, view=select_view)

    @ui.button(
        label="Advance Current Round",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def advance_round(self, interaction: discord.Interaction, button: ui.Button):
        """Resolve all matches in the lowest unresolved round."""
        import random

        await interaction.response.defer(ephemeral=True)

        # Get pending matches
        all_matches = await self.bot.tournament_service.list_matches(self.tournament.id)
        pending = [
            m
            for m in all_matches
            if m.status == "pending" and m.entry1_id and m.entry2_id
        ]

        if not pending:
            await self.refresh_panel(interaction, "No pending matches to advance.")
            return

        # Find lowest round
        lowest_round = min(m.round for m in pending)
        round_matches = [m for m in pending if m.round == lowest_round]

        resolved = 0
        for match in round_matches:
            # Pick random winner
            winner_entry_id = random.choice([match.entry1_id, match.entry2_id])

            t, m, err = await self.bot.tournament_service.report_result_by_entry(
                match_id=match.id,
                winner_entry_id=winner_entry_id,
                score="DEV",
            )
            if not err:
                resolved += 1

        # Update dashboard
        self.tournament = await self.bot.tournament_service.get_by_id(
            self.tournament.id
        )
        from cogs.tournaments import update_tournament_dashboard

        await update_tournament_dashboard(
            self.bot, interaction.guild, self.tournament.id
        )

        log.info(
            f"[DEV] Advanced round {lowest_round} ({resolved} matches) in tournament {self.tournament.id}"
        )

        await self.refresh_panel(
            interaction, f"Advanced round {lowest_round}: resolved {resolved} matches"
        )

    @ui.button(
        label="Auto-resolve All",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def auto_resolve_all(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Auto-resolve all dummy vs dummy matches (calls existing logic)."""
        await interaction.response.defer(ephemeral=True)

        resolved = 0

        # Keep resolving until no more dummy matches
        while True:
            matches = await self.bot.tournament_service.list_matches(self.tournament.id)
            pending = [
                m for m in matches if m.status == "pending" and m.entry2_id is not None
            ]

            if not pending:
                break

            resolved_this_round = 0

            for match in pending:
                entry1_dummy, entry2_dummy, both_dummy = (
                    await self.bot.tournament_service.is_dummy_match(match.id)
                )

                if both_dummy:
                    t, m, err = (
                        await self.bot.tournament_service.auto_resolve_dummy_match(
                            match.id
                        )
                    )
                    if not err:
                        resolved += 1
                        resolved_this_round += 1

            if resolved_this_round == 0:
                break

            self.tournament = await self.bot.tournament_service.get_by_id(
                self.tournament.id
            )
            if self.tournament.status == "completed":
                break

        # Update dashboard
        from cogs.tournaments import update_tournament_dashboard

        await update_tournament_dashboard(
            self.bot, interaction.guild, self.tournament.id
        )

        log.info(
            f"[DEV] Auto-resolved {resolved} matches in tournament {self.tournament.id}"
        )

        await self.refresh_panel(interaction, f"Auto-resolved {resolved} dummy matches")

    @ui.button(
        label="Close",
        style=discord.ButtonStyle.secondary,
        row=2,
    )
    async def close_panel(self, interaction: discord.Interaction, button: ui.Button):
        """Close the dev panel."""
        embed = create_embed(
            "Dev Bracket Tools Closed",
            "Panel closed. Use `/ums_dev_bracket_tools` to reopen.",
            Colors.WARNING,
        )
        await interaction.response.edit_message(embed=embed, view=None)


# -----------------------------------------------------------------------------
# Dev Tools Hub View (DEV-ONLY)
# -----------------------------------------------------------------------------


class DevToolsHubView(ui.View):
    """Dev-only hub panel providing quick access to all dev tools."""

    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=300)  # 5 min timeout
        self.bot = bot
        self.guild_id = guild_id
        self.last_action = "Waiting for an action..."

    async def _get_tournament(self, status_filter: list[str] = None) -> tuple:
        """Get active tournament, optionally filtered by status."""
        tournament = await self.bot.tournament_service.get_active_for_guild(
            self.guild_id
        )
        if not tournament:
            return None, "No active tournament in this server."
        if status_filter and tournament.status not in status_filter:
            return (
                None,
                f"Tournament is in status: **{tournament.status}** (expected: {', '.join(status_filter)})",
            )
        return tournament, None

    def _build_embed(self, tournament=None) -> discord.Embed:
        """Build the hub embed with current state."""
        embed = create_embed(
            "Dev Tools Hub", "Quick access to developer tools for UMS Bot Core."
        )

        if tournament:
            embed.add_field(
                name="Current Tournament",
                value=f"**{tournament.name}** (`{tournament.tournament_code}`)\nStatus: {tournament.status}",
                inline=False,
            )
        else:
            embed.add_field(
                name="Current Tournament", value="None active", inline=False
            )

        embed.add_field(
            name="Available Tools",
            value=(
                "• **Bracket Tools** — Open Dev Bracket Tools panel\n"
                "• **Add Dummies** — Fill tournament with dummy entries\n"
                "• **Auto-resolve** — Resolve all dummy vs dummy matches"
            ),
            inline=False,
        )

        embed.add_field(name="Last Action", value=self.last_action, inline=False)

        return embed

    async def refresh_hub(
        self, interaction: discord.Interaction, status_msg: str = None
    ):
        """Refresh the hub with updated state."""
        if status_msg:
            self.last_action = status_msg

        tournament, _ = await self._get_tournament()
        embed = self._build_embed(tournament)
        await interaction.edit_original_response(embed=embed, view=self)

    @ui.button(
        label="Bracket Tools",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def open_bracket_tools(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Open the Dev Bracket Tools panel."""
        await interaction.response.defer(ephemeral=True)

        tournament, error = await self._get_tournament(["in_progress"])
        if error:
            self.last_action = f"❌ {error}"
            await self.refresh_hub(interaction)
            return

        # Get match counts
        all_matches = await self.bot.tournament_service.list_matches(tournament.id)
        pending = [m for m in all_matches if m.status == "pending"]
        completed = [m for m in all_matches if m.status == "completed"]

        # Show bracket tools panel (replaces this message)
        embed = create_embed(
            "Dev Bracket Tools",
            f"**Tournament:** {tournament.name}\n**Code:** `{tournament.tournament_code}`",
        )
        embed.add_field(name="Status", value=tournament.status, inline=True)
        embed.add_field(name="Pending", value=str(len(pending)), inline=True)
        embed.add_field(name="Completed", value=str(len(completed)), inline=True)
        embed.add_field(
            name="Actions",
            value=(
                "• **Advance One** — Pick and resolve a single match\n"
                "• **Advance Round** — Resolve all matches in lowest round\n"
                "• **Auto-resolve** — Resolve all dummy vs dummy matches"
            ),
            inline=False,
        )

        view = DevBracketToolsView(self.bot, tournament)
        await interaction.edit_original_response(embed=embed, view=view)

        log.info(
            f"[DEV] Dev Tools Hub: opened bracket tools for tournament {tournament.id}"
        )

    @ui.button(
        label="Add Dummy Entries",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def add_dummies(self, interaction: discord.Interaction, button: ui.Button):
        """Add dummy entries to the active tournament."""
        await interaction.response.defer(ephemeral=True)

        tournament, error = await self._get_tournament(
            ["draft", "reg_open", "reg_closed"]
        )
        if error:
            self.last_action = f"❌ {error}"
            await self.refresh_hub(interaction)
            return

        # Calculate how many to add
        current_entries = await self.bot.tournament_service.count_entries(tournament.id)
        max_size = tournament.size
        remaining = max_size - current_entries

        if remaining <= 0:
            self.last_action = (
                f"❌ Tournament is already full ({current_entries}/{max_size})"
            )
            await self.refresh_hub(interaction)
            return

        # Add dummy entries (up to remaining slots)
        base_dummy_id = 9900000000000000 + (tournament.id * 1000)
        added = 0

        for i in range(remaining):
            dummy_player_id = base_dummy_id + current_entries + i

            # Create dummy player record
            try:
                await self.bot.player_service.db.execute(
                    """
                    INSERT OR IGNORE INTO players (user_id, discord_id, display_name, region, claimed_rank, has_onboarded)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (
                        dummy_player_id,
                        dummy_player_id,
                        f"DummyPlayer{current_entries + i + 1}",
                        "USE",
                        "Gold",
                    ),
                )
                await self.bot.player_service.db.commit()
            except Exception:
                pass

            # Add tournament entry
            entry = await self.bot.tournament_service.add_dummy_entry(
                tournament_id=tournament.id,
                dummy_player_id=dummy_player_id,
            )
            if entry:
                added += 1

        log.info(
            f"[DEV] Dev Tools Hub: added {added} dummy entries to tournament {tournament.id}"
        )

        self.last_action = f"✅ Added {added} dummy entries to {tournament.name} (`{tournament.tournament_code}`)"
        await self.refresh_hub(interaction)

    @ui.button(
        label="Auto-resolve All",
        style=discord.ButtonStyle.danger,
        row=0,
    )
    async def auto_resolve(self, interaction: discord.Interaction, button: ui.Button):
        """Auto-resolve all dummy vs dummy matches."""
        await interaction.response.defer(ephemeral=True)

        tournament, error = await self._get_tournament(["in_progress"])
        if error:
            self.last_action = f"❌ {error}"
            await self.refresh_hub(interaction)
            return

        resolved = 0

        # Keep resolving until no more dummy matches
        while True:
            matches = await self.bot.tournament_service.list_matches(tournament.id)
            pending = [
                m for m in matches if m.status == "pending" and m.entry2_id is not None
            ]

            if not pending:
                break

            resolved_this_round = 0

            for match in pending:
                entry1_dummy, entry2_dummy, both_dummy = (
                    await self.bot.tournament_service.is_dummy_match(match.id)
                )

                if both_dummy:
                    t, m, err = (
                        await self.bot.tournament_service.auto_resolve_dummy_match(
                            match.id
                        )
                    )
                    if not err:
                        resolved += 1
                        resolved_this_round += 1

            if resolved_this_round == 0:
                break

            tournament = await self.bot.tournament_service.get_by_id(tournament.id)
            if tournament.status == "completed":
                break

        # Update dashboard
        from cogs.tournaments import update_tournament_dashboard

        await update_tournament_dashboard(self.bot, interaction.guild, tournament.id)

        log.info(f"[DEV] Dev Tools Hub: auto-resolved tournament {tournament.id}")

        if resolved > 0:
            self.last_action = (
                f"✅ Auto-resolved {resolved} matches for {tournament.name}"
            )
        else:
            self.last_action = "ℹ️ No dummy vs dummy matches to resolve"

        await self.refresh_hub(interaction)

    @ui.button(
        label="Close",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def close_hub(self, interaction: discord.Interaction, button: ui.Button):
        """Close the dev tools hub."""
        embed = create_embed(
            "Dev Tools Hub Closed", "Use `/ums_dev_tools` to reopen.", Colors.WARNING
        )
        await interaction.response.edit_message(embed=embed, view=None)
