"""
Bracket UI Views and Modals.

Extracted from cogs/brackets.py to separate UI layer from cog logic.
These components handle score reporting and match verification UI.
"""

from typing import TYPE_CHECKING, Any, Optional
import math

import discord
from discord import ui

if TYPE_CHECKING:
    from cogs.brackets import BracketCog


class ScoreModal(ui.Modal):
    """Modal for players to report their match scores."""

    def __init__(
        self, cog: "BracketCog", key: str, opponent_id: Any, opponent_name: str
    ):
        # Get match format from tournament data
        reg_cog = cog.bot.get_cog("RegistrationCog")
        match_format = "Bo3"
        if reg_cog:
            state = reg_cog.tournaments.get(key)
            if state:
                match_format = state.get("match_length", "Bo3")

        # Set dynamic title based on format
        super().__init__(title=f"Report {match_format} Match Result")
        self.cog = cog
        self.key = key
        self.opponent_id = opponent_id
        self.opponent_name = opponent_name

        # Determine what to display based on format
        if "1" in match_format and "3" not in match_format and "5" not in match_format:
            example = "e.g., 1 (winner takes all)"
        elif "3" in match_format and "5" not in match_format:
            example = "e.g., 2 (for 2-1 victory)"
        elif "5" in match_format:
            example = "e.g., 3 (for 3-2 victory)"
        else:  # Bo3 + Bo5
            example = "e.g., 2 or 3"

        self.your_score = ui.TextInput(
            label="Games YOU Won (not individual scores!)",
            style=discord.TextStyle.short,
            placeholder=example,
            required=True,
            max_length=2,
        )
        self.opponent_score = ui.TextInput(
            label=f"Games {opponent_name} Won",
            style=discord.TextStyle.short,
            placeholder=example,
            required=True,
            max_length=2,
        )

        self.add_item(self.your_score)
        self.add_item(self.opponent_score)

    async def on_submit(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)

        # Verify match exists
        match = await self.cog.find_match(self.key, inter.user.id, self.opponent_id)

        # If not found directly (e.g. team match), try to find via get_active_match
        if not match:
            match = await self.cog.get_active_match(self.key, inter.user.id)

        if not match:
            return await inter.followup.send(
                "❌ No active match found between you and this player.", ephemeral=True
            )

        # Check Captaincy for Team Matches
        teams_cog = self.cog.bot.get_cog("TeamsCog")
        p1 = match["p1"]
        p2 = match["p2"]

        if isinstance(p1, str) and teams_cog:
            # Determine user's team
            user_team_id = None
            if await teams_cog.is_user_in_team(inter.user.id, p1):
                user_team_id = p1
            elif await teams_cog.is_user_in_team(inter.user.id, p2):
                user_team_id = p2

            if user_team_id:
                # Check if captain
                if not await teams_cog.is_captain(user_team_id, inter.user.id):
                    return await inter.followup.send(
                        "❌ Only the team captain can report scores.", ephemeral=True
                    )

        try:
            s1 = int(self.your_score.value.strip())
            s2 = int(self.opponent_score.value.strip())
        except ValueError:
            return await inter.followup.send(
                "❌ Scores must be valid integers.", ephemeral=True
            )

        if s1 == s2:
            return await inter.followup.send(
                "❌ Draws are not allowed. Please play a tiebreaker.", ephemeral=True
            )

        # Validate Match Length (Bo1 / Bo3 / Bo5)
        reg_cog = self.cog.bot.get_cog("RegistrationCog")
        target_wins = 2  # Default Bo3

        if reg_cog:
            state = reg_cog.tournaments.get(self.key)
            if state:
                match_length = state.get("match_length", "Bo3").lower()

                # Determine target wins based on format
                if (
                    "1" in match_length
                    and "3" not in match_length
                    and "5" not in match_length
                ):
                    target_wins = 1
                elif "5" in match_length and "3" in match_length:
                    # Hybrid: Bo3 + Bo5 Finals
                    participants = state.get("participants", [])
                    if len(participants) > 1:
                        total_rounds = math.ceil(math.log2(len(participants)))
                        if match.get("round", 0) >= total_rounds:
                            target_wins = 3
                elif "5" in match_length:
                    target_wins = 3  # Pure Bo5

                # Validate
                if s1 != target_wins and s2 != target_wins:
                    return await inter.followup.send(
                        f"❌ Invalid score for {state.get('match_length')}. Winner must have exactly {target_wins} wins.",
                        ephemeral=True,
                    )

                if s1 > target_wins or s2 > target_wins:
                    return await inter.followup.send(
                        f"❌ Invalid score. Cannot exceed {target_wins} wins.",
                        ephemeral=True,
                    )

        # Determine winner
        # If user is p1 (or in p1 team), s1 is their score.
        # If user is p2 (or in p2 team), s1 is their score.

        # We need to map s1/s2 to p1/p2 scores
        p1_score = 0
        p2_score = 0

        is_p1 = False
        if isinstance(p1, str) and teams_cog:
            if await teams_cog.is_user_in_team(inter.user.id, p1):
                is_p1 = True
        else:
            if p1 == inter.user.id:
                is_p1 = True

        if is_p1:
            p1_score = s1
            p2_score = s2
        else:
            p1_score = s2
            p2_score = s1

        winner_id = p1 if p1_score > p2_score else p2
        score_str = f"{max(s1, s2)}-{min(s1, s2)}"

        # Submit report
        await self.cog.handle_match_report(inter, self.key, match, winner_id, score_str)


class ScoreSubmissionView(ui.View):
    """Persistent view in #submit-score for players to report results."""

    def __init__(self, cog: "BracketCog", key: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.key = key

        # Update button custom_id to be unique per tournament
        for item in self.children:
            if isinstance(item, ui.Button) and item.label == "Report Match Result":
                item.custom_id = f"bracket:report:{key}"

    @ui.button(
        label="Report Match Result",
        style=discord.ButtonStyle.success,
        custom_id="bracket:report_btn_placeholder",
    )
    async def report_btn(self, inter: discord.Interaction, _: ui.Button):
        # Auto-detect active match
        match = await self.cog.get_active_match(self.key, inter.user.id)
        if not match:
            return await inter.response.send_message(
                "❌ You have no active match to report.", ephemeral=True
            )

        # Identify opponent
        teams_cog = self.cog.bot.get_cog("TeamsCog")
        p1 = match["p1"]
        p2 = match["p2"]

        opponent_id = None
        opponent_name = "Unknown"

        if isinstance(p1, str) and teams_cog:
            # Team Match
            if await teams_cog.is_user_in_team(inter.user.id, p1):
                opponent_id = p2
            else:
                opponent_id = p1

            if isinstance(opponent_id, int) and opponent_id < 0:
                opponent_name = f"Dummy {abs(opponent_id)}"
            else:
                opponent_name = await teams_cog.get_team_name(opponent_id)
        else:
            # Individual Match
            opponent_id = p1 if p2 == inter.user.id else p2

            # Resolve name
            opponent_name = (
                f"Dummy {abs(opponent_id)}" if opponent_id < 0 else f"<@{opponent_id}>"
            )
            if opponent_id > 0:
                member = inter.guild.get_member(opponent_id)
                if member:
                    opponent_name = member.display_name

        await inter.response.send_modal(
            ScoreModal(self.cog, self.key, opponent_id, opponent_name)
        )


class ScoreVerificationView(ui.View):
    """Admin view for confirming or rejecting match score reports."""

    def __init__(
        self, cog: "BracketCog", key: str, match_id: int, winner_id: int, score_str: str
    ):
        super().__init__(timeout=None)
        self.cog = cog
        self.key = key
        self.match_id = match_id
        self.winner_id = winner_id
        self.score_str = score_str

    @ui.button(
        label="Confirm", style=discord.ButtonStyle.success, custom_id="verify:confirm"
    )
    async def confirm(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.defer()
        await self.cog.confirm_match(
            inter, self.key, self.match_id, self.winner_id, self.score_str
        )
        self.stop()

    @ui.button(
        label="Reject", style=discord.ButtonStyle.danger, custom_id="verify:reject"
    )
    async def reject(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.send_message(
            f"❌ Match report rejected by {inter.user.mention}.", ephemeral=False
        )
        await inter.message.delete()
        self.stop()
