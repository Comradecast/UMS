"""
ui/match_views.py — Match Card UI Views
=======================================
Persistent match card views for announce channel.
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


class MatchCardView(ui.View):
    """
    Persistent match card with winner buttons.

    Each pending match gets one of these posted to the announce channel.
    Buttons call report_result_by_entry to update the match.
    """

    def __init__(
        self,
        bot: commands.Bot,
        match_id: int,
        entry1_id: int,
        entry2_id: int,
        entry1_name: str,
        entry2_name: str,
    ):
        # Create unique custom_id based on match_id for persistence
        super().__init__(timeout=None)
        self.bot = bot
        self.match_id = match_id
        self.entry1_id = entry1_id
        self.entry2_id = entry2_id
        self.entry1_name = entry1_name
        self.entry2_name = entry2_name

        # Dynamically add winner buttons (can't use decorators for dynamic labels)
        self.add_item(
            WinnerButton(
                entry_id=entry1_id,
                entry_name=entry1_name,
                match_id=match_id,
                style=discord.ButtonStyle.success,
                position=1,
            )
        )
        self.add_item(
            WinnerButton(
                entry_id=entry2_id,
                entry_name=entry2_name,
                match_id=match_id,
                style=discord.ButtonStyle.primary,
                position=2,
            )
        )
        self.add_item(OverrideButton(match_id=match_id))


class WinnerButton(ui.Button):
    """Button to declare a winner for the match."""

    def __init__(
        self,
        entry_id: int,
        entry_name: str,
        match_id: int,
        style: discord.ButtonStyle,
        position: int,
    ):
        # Use match_id + position for unique persistent custom_id
        super().__init__(
            label=f"🏆 Winner: {entry_name}",
            style=style,
            custom_id=f"match_winner_{match_id}_{position}",
            row=0,
        )
        self.entry_id = entry_id
        self.entry_name = entry_name
        self.match_id = match_id

    async def callback(self, interaction: discord.Interaction):
        """Report this entry as winner."""
        bot = interaction.client

        # Get match to verify it's still pending
        match = await bot.tournament_service.get_match(self.match_id)
        if not match:
            await interaction.response.send_message(
                "❌ Match not found.", ephemeral=True
            )
            return

        if match.status != "pending":
            await interaction.response.send_message(
                "❌ This match has already been completed.",
                ephemeral=True,
            )
            return

        # Permission check: only match players or admins can report
        is_admin = interaction.user.guild_permissions.manage_guild
        if not is_admin:
            player_ids = await bot.tournament_service.get_match_player_ids(
                self.match_id
            )
            if interaction.user.id not in player_ids:
                await interaction.response.send_message(
                    "❌ Only the two players in this match or a server admin can report this result.",
                    ephemeral=True,
                )
                return

        # Defer after permission checks pass
        await interaction.response.defer()

        # Report result by entry ID
        tournament, updated_match, error = (
            await bot.tournament_service.report_result_by_entry(
                match_id=self.match_id,
                winner_entry_id=self.entry_id,
            )
        )

        if error:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        # Get loser name for the embed
        loser_entry_id = (
            match.entry1_id if self.entry_id == match.entry2_id else match.entry2_id
        )
        loser_name = await bot.tournament_service.get_entry_display_name(
            loser_entry_id, tournament.format
        )

        # Update the match card to show completed state (this IS the announcement)
        completed_embed = discord.Embed(
            title=f"✅ Match Complete — {self.entry_name} defeated {loser_name}",
            color=discord.Color.green(),
        )
        completed_embed.add_field(name="Tournament", value=tournament.name, inline=True)
        completed_embed.add_field(
            name="Round", value=str(updated_match.round), inline=True
        )
        completed_embed.set_footer(text=f"Reported by {interaction.user.display_name}")

        # Disable buttons - update the card
        await interaction.message.edit(embed=completed_embed, view=CompletedMatchView())

        log.info(
            f"[MATCH-CARD] Match {self.match_id} completed: winner={self.entry_id}, reporter={interaction.user.id}"
        )

        # Import here to avoid circular imports
        from cogs.tournaments import (
            update_tournament_dashboard,
            maybe_post_next_round_cards,
        )

        # Check if tournament completed → update dashboard to trophy mode
        if tournament.status == "completed":
            await update_tournament_dashboard(
                bot=bot,
                guild=interaction.guild,
                tournament_id=tournament.id,
            )
        else:
            # Check if new round started and post cards for it
            await maybe_post_next_round_cards(
                bot=bot,
                guild=interaction.guild,
                tournament_id=tournament.id,
            )


class OverrideButton(ui.Button):
    """Admin override button to manually set result."""

    def __init__(self, match_id: int):
        super().__init__(
            label="⚙️ Override",
            style=discord.ButtonStyle.secondary,
            custom_id=f"match_override_{match_id}",
            row=1,
        )
        self.match_id = match_id

    async def callback(self, interaction: discord.Interaction):
        """Open override modal (admin only)."""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ Only admins can override results.",
                ephemeral=True,
            )
            return

        # Get match info
        bot = interaction.client
        match = await bot.tournament_service.get_match(self.match_id)

        if not match:
            await interaction.response.send_message(
                "❌ Match not found.", ephemeral=True
            )
            return

        # Import here to avoid circular imports
        from ui.match_modals import MatchOverrideModal

        modal = MatchOverrideModal(bot, match)
        await interaction.response.send_modal(modal)


class CompletedMatchView(ui.View):
    """Empty view for completed matches (buttons disabled)."""

    def __init__(self):
        super().__init__(timeout=None)
