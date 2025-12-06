"""
ui/tournament_embeds.py — Tournament Embed Builders
====================================================
Embed construction for dashboards and announcements.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


async def build_dashboard_embed(bot: commands.Bot, tournament) -> discord.Embed:
    """Build the tournament dashboard embed (or trophy embed when completed)."""
    # Get matches
    matches = await bot.tournament_service.list_matches(tournament.id)

    # Determine status color and mode
    if tournament.status == "completed":
        color = discord.Color.gold()
        status_emoji = "🏆"
    elif tournament.status == "archived":
        color = discord.Color.dark_gold()
        status_emoji = "🏆"
    elif tournament.status == "in_progress":
        color = discord.Color.green()
        status_emoji = "⚔️"
    else:
        color = discord.Color.blue()
        status_emoji = "📋"

    # TROPHY MODE: When tournament is completed or archived
    if tournament.status in ("completed", "archived"):
        embed = discord.Embed(
            title=f"{status_emoji} {tournament.name} — Tournament Complete",
            description="Congratulations to the champion!",
            color=color,
        )

        embed.add_field(
            name="Code",
            value=(
                f"`{tournament.tournament_code}`"
                if tournament.tournament_code
                else "N/A"
            ),
            inline=True,
        )
        embed.add_field(name="Format", value=tournament.format, inline=True)
        embed.add_field(name="Size", value=str(tournament.size), inline=True)

        # Get winner from final match
        if matches:
            final_match = max(matches, key=lambda m: m.round)
            if final_match.winner_entry_id:
                winner_name = await bot.tournament_service.get_entry_display_name(
                    final_match.winner_entry_id, tournament.format
                )
                embed.add_field(name="🥇 Winner", value=winner_name, inline=True)

                # Get runner-up (loser of final match)
                loser_entry_id = (
                    final_match.entry2_id
                    if final_match.winner_entry_id == final_match.entry1_id
                    else final_match.entry1_id
                )
                if loser_entry_id:
                    runner_up_name = (
                        await bot.tournament_service.get_entry_display_name(
                            loser_entry_id, tournament.format
                        )
                    )
                    embed.add_field(
                        name="🥈 Runner-up", value=runner_up_name, inline=True
                    )

        # Add empty field for alignment if needed
        if len(embed.fields) % 3 == 2:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.set_footer(text="Thank you for participating!")
        return embed

    # LIVE MODE: In-progress tournament
    embed = discord.Embed(
        title=f"{status_emoji} {tournament.name}",
        color=color,
    )

    embed.add_field(
        name="Code",
        value=(
            f"`{tournament.tournament_code}`" if tournament.tournament_code else "N/A"
        ),
        inline=True,
    )
    embed.add_field(name="Format", value=tournament.format, inline=True)
    embed.add_field(
        name="Status", value=tournament.status.replace("_", " ").title(), inline=True
    )

    # Add current round matches
    if matches:
        current_round = max(m.round for m in matches)
        round_matches = [m for m in matches if m.round == current_round]

        match_lines = []
        for m in round_matches:
            entry1_name = await bot.tournament_service.get_entry_display_name(
                m.entry1_id, tournament.format
            )

            if m.entry2_id:
                entry2_name = await bot.tournament_service.get_entry_display_name(
                    m.entry2_id, tournament.format
                )

                if m.status == "pending":
                    line = f"#{m.match_index+1}: {entry1_name} vs {entry2_name} — ⏳ pending"
                else:
                    winner_name = await bot.tournament_service.get_entry_display_name(
                        m.winner_entry_id, tournament.format
                    )
                    score_text = f" ({m.score_text})" if m.score_text else ""
                    line = f"#{m.match_index+1}: ✅ {winner_name} wins{score_text}"
            else:
                line = f"#{m.match_index+1}: {entry1_name} — BYE"

            match_lines.append(line)

        embed.add_field(
            name=f"Round {current_round}",
            value="\n".join(match_lines) or "No matches",
            inline=False,
        )

    embed.set_footer(text="Click 🏅 My Match to report your result")

    return embed
