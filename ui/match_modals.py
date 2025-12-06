"""
ui/match_modals.py — Match Result Modals
========================================
Modal dialogs for reporting and overriding match results.
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


class MatchOverrideModal(ui.Modal, title="Override Match Result"):
    """Modal for admin to override match result."""

    winner = ui.TextInput(
        label="Winner (1 or 2)",
        placeholder="Enter 1 for Entry 1, or 2 for Entry 2",
        required=True,
        max_length=1,
    )

    score = ui.TextInput(
        label="Score (optional)",
        placeholder="e.g., 2-1",
        required=False,
        max_length=20,
    )

    def __init__(self, bot: commands.Bot, match):
        super().__init__()
        self.bot = bot
        self.match = match

    async def on_submit(self, interaction: discord.Interaction):
        """Apply override."""
        # Parse winner
        try:
            winner_num = int(self.winner.value.strip())
            if winner_num not in (1, 2):
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "❌ Winner must be **1** or **2**.",
                ephemeral=True,
            )
            return

        winner_entry_id = (
            self.match.entry1_id if winner_num == 1 else self.match.entry2_id
        )
        score = self.score.value.strip() if self.score.value else None

        tournament, updated_match, error = (
            await self.bot.tournament_service.report_result_by_entry(
                match_id=self.match.id,
                winner_entry_id=winner_entry_id,
                score=score,
            )
        )

        if error:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        winner_name = await self.bot.tournament_service.get_entry_display_name(
            winner_entry_id, tournament.format
        )

        await interaction.response.send_message(
            f"✅ Override applied. Winner: **{winner_name}**"
            + (f" | Score: {score}" if score else ""),
            ephemeral=True,
        )

        # Update original message
        try:
            loser_entry_id = (
                self.match.entry1_id
                if winner_entry_id == self.match.entry2_id
                else self.match.entry2_id
            )
            loser_name = await self.bot.tournament_service.get_entry_display_name(
                loser_entry_id, tournament.format
            )

            # Build title with score if provided
            title = f"✅ Match Complete — {winner_name} defeated {loser_name}"
            if score:
                title += f" ({score})"

            completed_embed = discord.Embed(
                title=title,
                color=discord.Color.gold(),  # Gold for override
            )
            completed_embed.add_field(
                name="Tournament", value=tournament.name, inline=True
            )
            completed_embed.add_field(
                name="Round", value=str(updated_match.round), inline=True
            )
            completed_embed.set_footer(
                text=f"Overridden by {interaction.user.display_name}"
            )

            from ui.match_views import CompletedMatchView

            await interaction.message.edit(
                embed=completed_embed, view=CompletedMatchView()
            )
        except Exception as e:
            log.warning(f"[MATCH-CARD] Could not update override message: {e}")

        # Import here to avoid circular imports
        from cogs.tournaments import (
            update_tournament_dashboard,
            maybe_post_next_round_cards,
        )

        # Check for tournament completion or next round
        if tournament.status == "completed":
            await update_tournament_dashboard(
                bot=self.bot,
                guild=interaction.guild,
                tournament_id=tournament.id,
            )
        else:
            await maybe_post_next_round_cards(
                bot=self.bot,
                guild=interaction.guild,
                tournament_id=tournament.id,
            )


class ReportResultModal(ui.Modal, title="Report Match Result"):
    """Modal for player to report their match result."""

    result = ui.TextInput(
        label="Did you win or lose? (win/lose)",
        placeholder="Enter 'win' or 'lose'",
        required=True,
        max_length=10,
    )

    score = ui.TextInput(
        label="Score (optional)",
        placeholder="e.g., 2-1",
        required=False,
        max_length=20,
    )

    def __init__(
        self,
        bot: commands.Bot,
        tournament,
        match,
        player_entry_id: int,
        opponent_entry_id: int,
        opponent_name: str,
    ):
        super().__init__(title=f"Report Result vs {opponent_name[:20]}")
        self.bot = bot
        self.tournament = tournament
        self.match = match
        self.player_entry_id = player_entry_id
        self.opponent_entry_id = opponent_entry_id

    async def on_submit(self, interaction: discord.Interaction):
        """Process the result submission with confirmation logic."""
        result_text = self.result.value.strip().lower()

        if result_text not in ("win", "lose", "won", "lost"):
            await interaction.response.send_message(
                "❌ Please enter **win** or **lose**.",
                ephemeral=True,
            )
            return

        # Determine winner based on what THIS player says
        if result_text in ("win", "won"):
            claimed_winner = self.player_entry_id
        else:
            claimed_winner = self.opponent_entry_id

        score = self.score.value.strip() if self.score.value else None

        # Check if opponent is a dummy
        opponent_player_id = await self.bot.tournament_service.get_entry_player_id(
            self.opponent_entry_id
        )
        opponent_is_dummy = (
            opponent_player_id is not None
            and self.bot.tournament_service.is_dummy_player_id(opponent_player_id)
        )

        # Re-fetch match to check for pending result
        match = await self.bot.tournament_service.get_match(self.match.id)
        if not match or match.status != "pending":
            await interaction.response.send_message(
                "❌ This match is no longer pending.",
                ephemeral=True,
            )
            return

        # CASE 1: Opponent is dummy - just report directly
        if opponent_is_dummy:
            tournament, match, error = (
                await self.bot.tournament_service.report_result_by_entry(
                    match_id=self.match.id,
                    winner_entry_id=claimed_winner,
                    score=score,
                )
            )

            if error:
                await interaction.response.send_message(f"❌ {error}", ephemeral=True)
                return

            await interaction.response.send_message(
                "✅ Your result has been recorded!",
                ephemeral=True,
            )

        # CASE 2: Live vs live - check for pending or conflict
        else:
            # Check if there's a pending result from the other player
            if match.pending_winner_entry_id is not None:
                # Other player already reported
                if match.pending_reported_by == interaction.user.id:
                    await interaction.response.send_message(
                        "⏳ You already reported. Waiting for opponent to confirm.",
                        ephemeral=True,
                    )
                    return

                # Check if results agree
                if match.pending_winner_entry_id == claimed_winner:
                    # Results match! Finalize
                    tournament, match, error = (
                        await self.bot.tournament_service.report_result_by_entry(
                            match_id=self.match.id,
                            winner_entry_id=claimed_winner,
                            score=score,
                        )
                    )

                    if error:
                        await interaction.response.send_message(
                            f"❌ {error}", ephemeral=True
                        )
                        return

                    await interaction.response.send_message(
                        "✅ Both players agree! Result confirmed.",
                        ephemeral=True,
                    )
                else:
                    # CONFLICT! Both say they won
                    await interaction.response.send_message(
                        "⚠️ **Conflict detected!** Both players claim to have won.\n\n"
                        "An admin must resolve this match using the Override button.",
                        ephemeral=True,
                    )

                    # Try to ping admins in the channel
                    try:
                        config = await self.bot.guild_config_service.get(
                            interaction.guild.id
                        )
                        if config and config.admin_channel:
                            admin_channel = interaction.guild.get_channel(
                                config.admin_channel
                            )
                            if admin_channel:
                                await admin_channel.send(
                                    f"⚠️ **Match Conflict** in **{self.tournament.name}**\n"
                                    f"Match #{self.match.id}: Both players claim victory!\n"
                                    f"Please use the admin override to resolve."
                                )
                    except Exception as e:
                        log.warning(
                            f"[DASHBOARD] Could not ping admins about conflict: {e}"
                        )

                    return

            else:
                # First report - store as pending
                # NOTE: This is direct DB access; ideally move to service layer
                await self.bot.tournament_service.db.execute(
                    """
                    UPDATE matches
                    SET pending_winner_entry_id = ?, pending_reported_by = ?
                    WHERE id = ?
                    """,
                    (claimed_winner, interaction.user.id, self.match.id),
                )
                await self.bot.tournament_service.db.commit()

                await interaction.response.send_message(
                    "⏳ Your result is pending. Waiting for your opponent to confirm.",
                    ephemeral=True,
                )
                return

        # Import here to avoid circular imports
        from cogs.tournaments import update_tournament_dashboard

        # Update dashboard (will show trophy if completed)
        await update_tournament_dashboard(
            self.bot, interaction.guild, self.tournament.id
        )
