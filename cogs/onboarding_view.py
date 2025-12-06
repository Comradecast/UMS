"""
cogs/onboarding_view.py — Player Onboarding Panel (Option A)
=============================================================
UMS Bot Core - Hero Feature A: One-Shot Onboarding

Behavior:
- Public panel has single "Start Onboarding" button
- If NOT onboarded: Shows ephemeral view with Region/Rank dropdowns + Submit/Cancel
- If already onboarded: Shows ephemeral read-only summary
- One-shot: Users cannot change region/rank after completing (admin reset required)
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands, ui
from discord.ext import commands

# Brand kit imports
from ui.brand import Colors, FOOTER_TEXT, create_embed, success_embed, error_embed

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

REGIONS = {
    "USE": "US-East",
    "USW": "US-West",
    "USC": "US-Central",
    "EU": "Europe",
    "ME": "Middle East",
    "JPN": "Japan",
    "OCE": "Oceania",
    "ASIA": "Asia",
    "SAM": "South America",
}

REGION_CODES = list(REGIONS.keys())

RANKS = [
    ("Bronze", None),
    ("Silver", None),
    ("Gold", None),
    ("Platinum", None),
    ("Diamond", None),
    ("Champion", None),
    ("Grand Champion", None),
]


# -----------------------------------------------------------------------------
# Ephemeral Onboarding Session View (shown after clicking Start Onboarding)
# -----------------------------------------------------------------------------


class OnboardingRegionSelect(ui.Select):
    """Region dropdown for ephemeral onboarding session."""

    def __init__(self):
        options = [
            discord.SelectOption(label=REGIONS[code], value=code)
            for code in REGION_CODES
        ]
        super().__init__(
            placeholder="Select your region",
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()


class OnboardingRankSelect(ui.Select):
    """Rank dropdown for ephemeral onboarding session."""

    def __init__(self):
        options = [discord.SelectOption(label=name, value=name) for name, _ in RANKS]
        super().__init__(
            placeholder="Select your rank",
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()


class OnboardingSessionView(ui.View):
    """
    Ephemeral onboarding session view.

    Shown when user clicks "Start Onboarding" and is NOT yet onboarded.
    Contains Region/Rank dropdowns + Submit/Cancel buttons.
    """

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id

        self.region_select = OnboardingRegionSelect()
        self.rank_select = OnboardingRankSelect()
        self.add_item(self.region_select)
        self.add_item(self.rank_select)

    @ui.button(
        label="Submit",
        style=discord.ButtonStyle.primary,
        row=2,
    )
    async def submit_button(self, interaction: discord.Interaction, button: ui.Button):
        """Save onboarding data and show completion summary."""
        if interaction.user.id != self.user_id:
            embed = error_embed("Access Denied", "This is not your onboarding session.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        region = self.region_select.values[0] if self.region_select.values else None
        rank = self.rank_select.values[0] if self.rank_select.values else None

        if not region or not rank:
            embed = error_embed(
                "Selection Required", "Please select both a region and a rank."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if not hasattr(self.bot, "player_service"):
            embed = error_embed(
                "Service Unavailable", "Player service unavailable. Please try again."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        success = await self.bot.player_service.complete_onboarding(
            discord_id=self.user_id,
            region=region,
            claimed_rank=rank,
            display_name=interaction.user.display_name,
        )

        if not success:
            embed = error_embed(
                "Save Failed", "Failed to save profile. Please try again."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        for item in self.children:
            item.disabled = True

        region_display = REGIONS.get(region, region)
        embed = success_embed(
            "Onboarding Complete", "Your UMS profile has been created."
        )
        embed.add_field(name="Region", value=region_display, inline=True)
        embed.add_field(name="Rank", value=rank, inline=True)
        embed.add_field(
            name="Need Changes?",
            value="Contact a mod/admin to reset your profile.",
            inline=False,
        )

        await interaction.response.edit_message(embed=embed, view=self)

        log.info(
            f"[ONBOARDING] User {self.user_id} completed: region={region}, rank={rank}"
        )

        if interaction.guild:
            region_role = discord.utils.get(interaction.guild.roles, name=region)
            if region_role:
                try:
                    await interaction.user.add_roles(region_role)
                    log.info(
                        f"[ONBOARDING] Assigned role {region} to user {self.user_id}"
                    )
                except discord.Forbidden:
                    log.warning(f"[ONBOARDING] Could not assign role {region}")
                except Exception as e:
                    log.warning(f"[ONBOARDING] Role assignment error: {e}")

    @ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        row=2,
    )
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel onboarding session."""
        if interaction.user.id != self.user_id:
            embed = error_embed("Access Denied", "This is not your onboarding session.")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        for item in self.children:
            item.disabled = True

        embed = create_embed(
            "Onboarding Cancelled",
            "No changes were made to your profile.",
            Colors.WARNING,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Handle timeout - disable all components."""
        for item in self.children:
            item.disabled = True


# -----------------------------------------------------------------------------
# Persistent Public Panel View (single button)
# -----------------------------------------------------------------------------


class PersistentOnboardingView(ui.View):
    """
    Persistent onboarding panel view.

    Posted by admins, survives bot restarts.
    Contains only a "Start Onboarding" button.
    """

    def __init__(self, bot: commands.Bot = None):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(
        label="Start Onboarding",
        style=discord.ButtonStyle.primary,
        custom_id="ums_core_onboarding_start",
    )
    async def start_onboarding(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """Handle Start Onboarding button click."""
        bot = interaction.client
        user_id = interaction.user.id

        if hasattr(bot, "player_service"):
            player = await bot.player_service.get_by_discord_id(user_id)

            if player and player.has_onboarded:
                region_display = REGIONS.get(player.region, player.region or "Unknown")
                rank = player.claimed_rank or "Unknown"

                embed = success_embed(
                    "Already Onboarded", "Your UMS profile is already set up."
                )
                embed.add_field(name="Region", value=region_display, inline=True)
                embed.add_field(name="Rank", value=rank, inline=True)
                embed.add_field(
                    name="Need Changes?",
                    value="Contact a mod/admin to reset your profile.",
                    inline=False,
                )

                return await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True,
                )

        embed = create_embed(
            "Player Onboarding", "Select your region and rank, then press Submit."
        )
        embed.add_field(name="Region", value="Used for matchmaking", inline=True)
        embed.add_field(name="Rank", value="Used for tournament seeding", inline=True)

        view = OnboardingSessionView(bot, user_id)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )


# -----------------------------------------------------------------------------
# Onboarding Cog
# -----------------------------------------------------------------------------


class OnboardingCog(commands.Cog):
    """
    Player onboarding for UMS Bot Core.

    Hero Feature A: One-Shot Onboarding Panel
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Register persistent view."""
        self.bot.add_view(PersistentOnboardingView(self.bot))
        log.info("[ONBOARDING] Registered PersistentOnboardingView")

    def _create_panel_embed(self) -> discord.Embed:
        """Create onboarding panel embed."""
        embed = create_embed(
            "Player Onboarding", "Set up your profile to join tournaments."
        )
        embed.add_field(
            name="Region", value="Select your region for fair matchmaking", inline=False
        )
        embed.add_field(
            name="Rank", value="Set your starting rank for seeding", inline=False
        )
        return embed

    @app_commands.command(
        name="onboarding_panel",
        description="Post the player onboarding panel (Admin)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def onboarding_panel(self, interaction: discord.Interaction):
        """Post persistent onboarding panel."""
        embed = self._create_panel_embed()
        view = PersistentOnboardingView(self.bot)

        await interaction.channel.send(embed=embed, view=view)

        confirm = success_embed(
            "Panel Posted", f"Onboarding panel posted in {interaction.channel.mention}"
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)

        log.info(
            f"[ONBOARDING] Panel posted in #{interaction.channel.name} "
            f"({interaction.guild.name})"
        )

    @app_commands.command(
        name="onboard",
        description="Set up your player profile",
    )
    async def onboard(self, interaction: discord.Interaction):
        """Send ephemeral onboarding UI (same logic as button click)."""
        user_id = interaction.user.id

        if hasattr(self.bot, "player_service"):
            player = await self.bot.player_service.get_by_discord_id(user_id)

            if player and player.has_onboarded:
                region_display = REGIONS.get(player.region, player.region or "Unknown")
                rank = player.claimed_rank or "Unknown"

                embed = success_embed(
                    "Already Onboarded", "Your UMS profile is already set up."
                )
                embed.add_field(name="Region", value=region_display, inline=True)
                embed.add_field(name="Rank", value=rank, inline=True)
                embed.add_field(
                    name="Need Changes?",
                    value="Contact a mod/admin to reset your profile.",
                    inline=False,
                )

                return await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True,
                )

        embed = create_embed(
            "Player Onboarding", "Select your region and rank, then press Submit."
        )
        embed.add_field(name="Region", value="Used for matchmaking", inline=True)
        embed.add_field(name="Rank", value="Used for tournament seeding", inline=True)

        view = OnboardingSessionView(self.bot, user_id)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(OnboardingCog(bot))
