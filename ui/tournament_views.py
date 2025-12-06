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
            reg_embed = discord.Embed(
                title=f"🏆 {tournament.name}",
                description="**Registration is now OPEN!**\n\nClick the button below to register.",
                color=discord.Color.blue(),
            )
            reg_embed.add_field(name="Format", value=format_text, inline=True)
            reg_embed.add_field(
                name="Max Entries", value=str(tournament.size), inline=True
            )
            reg_embed.add_field(name="Registered", value="0", inline=True)
            reg_embed.set_footer(text="UMS Bot Core • Single Elimination Tournament")

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

        embed = discord.Embed(
            title=f"🏆 {tournament.name}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Format", value=tournament.format, inline=True)
        embed.add_field(name="Size", value=str(tournament.size), inline=True)
        embed.add_field(name="Status", value=tournament.status, inline=True)
        embed.add_field(
            name="Entries", value=f"{entry_count}/{tournament.size}", inline=True
        )
        embed.set_footer(text=f"Tournament ID: {tournament.id}")

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

                    embed = discord.Embed(
                        title="🎮 Welcome to UMS!",
                        description=(
                            "Complete your profile to participate in tournaments.\n\n"
                            "Click the button below to set your region and rank."
                        ),
                        color=discord.Color.blue(),
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
