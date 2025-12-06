"""
cogs/onboarding_view.py — Player Onboarding Panel
===================================================
UMS Bot Core - Hero Feature A: Onboarding Panel

Provides:
- /onboarding_panel (admin) - Posts persistent onboarding panel
- /onboard (user) - Ephemeral onboarding UI
- Persistent views that survive bot restarts

Users select region + rank to complete their profile.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands, ui
from discord.ext import commands

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
    ("Bronze", "🟤"),
    ("Silver", "⚪"),
    ("Gold", "🟡"),
    ("Platinum", "💠"),
    ("Diamond", "💎"),
    ("Champion", "🏆"),
    ("Grand Champion", "👑"),
]


# -----------------------------------------------------------------------------
# Persistent Select Menus
# -----------------------------------------------------------------------------


class PersistentRegionSelect(ui.Select):
    """Region selection - persistent across restarts."""

    def __init__(self):
        options = [
            discord.SelectOption(label=REGIONS[code], value=code)
            for code in REGION_CODES
        ]
        super().__init__(
            placeholder="🌍 Select your region...",
            options=options,
            custom_id="ums_onboard:region",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        view: PersistentOnboardingView = self.view
        view.selected_region = self.values[0]
        view._update_confirm_button()
        await interaction.response.edit_message(view=view)


class PersistentRankSelect(ui.Select):
    """Rank selection - persistent across restarts."""

    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=name, emoji=emoji)
            for name, emoji in RANKS
        ]
        super().__init__(
            placeholder="🎮 Select your current rank...",
            options=options,
            custom_id="ums_onboard:rank",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        view: PersistentOnboardingView = self.view
        view.selected_rank = self.values[0]
        view._update_confirm_button()
        await interaction.response.edit_message(view=view)


# -----------------------------------------------------------------------------
# Persistent Onboarding View
# -----------------------------------------------------------------------------


class PersistentOnboardingView(ui.View):
    """
    Persistent onboarding panel view.

    Posted by admins, survives bot restarts.
    """

    def __init__(self, bot: commands.Bot = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.selected_region: Optional[str] = None
        self.selected_rank: Optional[str] = None

        self.add_item(PersistentRegionSelect())
        self.add_item(PersistentRankSelect())

    def _update_confirm_button(self):
        """Enable confirm button when both selections made."""
        for item in self.children:
            if isinstance(item, ui.Button) and item.custom_id == "ums_onboard:confirm":
                item.disabled = not (self.selected_region and self.selected_rank)

    @ui.button(
        label="✅ Complete Onboarding",
        style=discord.ButtonStyle.success,
        custom_id="ums_onboard:confirm",
        disabled=True,
        row=2,
    )
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle onboarding confirmation."""
        try:
            # Get selections from component state
            region = None
            rank = None

            if interaction.message:
                for action_row in interaction.message.components:
                    for component in action_row.children:
                        if hasattr(component, "values") and component.values:
                            if component.custom_id == "ums_onboard:region":
                                region = component.values[0]
                            elif component.custom_id == "ums_onboard:rank":
                                rank = component.values[0]

            # Fallback to view state
            region = region or self.selected_region
            rank = rank or self.selected_rank

            if not region or not rank:
                return await interaction.response.send_message(
                    "❌ Please select both region and rank.",
                    ephemeral=True,
                )

            await interaction.response.defer(ephemeral=True)

            # Get player service from bot
            bot = interaction.client
            if not hasattr(bot, "player_service"):
                return await interaction.followup.send(
                    "❌ Player service unavailable.",
                    ephemeral=True,
                )

            # Complete onboarding
            success = await bot.player_service.complete_onboarding(
                discord_id=interaction.user.id,
                region=region,
                claimed_rank=rank,
                display_name=interaction.user.display_name,
            )

            if not success:
                return await interaction.followup.send(
                    "❌ Failed to save profile. Please try again.",
                    ephemeral=True,
                )

            # Try to assign region role
            role_msg = ""
            if interaction.guild:
                region_role = discord.utils.get(interaction.guild.roles, name=region)
                if region_role:
                    try:
                        await interaction.user.add_roles(region_role)
                        role_msg = f"\n🏷️ Region role `{region}` assigned!"
                    except discord.Forbidden:
                        log.warning(f"[ONBOARDING] Could not assign role {region}")
                    except Exception as e:
                        log.warning(f"[ONBOARDING] Role assignment error: {e}")

            region_display = REGIONS.get(region, region)
            await interaction.followup.send(
                f"✅ **Welcome aboard!**\n\n"
                f"🌍 **Region**: {region_display}\n"
                f"🎮 **Starting Rank**: {rank}\n"
                f"{role_msg}\n\n"
                f"You're all set to join tournaments!",
                ephemeral=True,
            )

            log.info(
                f"[ONBOARDING] User {interaction.user.id} completed: "
                f"region={region}, rank={rank}"
            )

        except Exception as e:
            log.error(f"[ONBOARDING] Error: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ An error occurred. Please try again.",
                    ephemeral=True,
                )
            except:
                pass


# -----------------------------------------------------------------------------
# Ephemeral Onboarding View
# -----------------------------------------------------------------------------


class EphemeralRegionSelect(ui.Select):
    """Region select for ephemeral use."""

    def __init__(self):
        options = [
            discord.SelectOption(label=REGIONS[code], value=code)
            for code in REGION_CODES
        ]
        super().__init__(
            placeholder="🌍 Select your region...",
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        view: EphemeralOnboardingView = self.view
        view.selected_region = self.values[0]
        view._update_confirm_button()
        await interaction.response.edit_message(view=view)


class EphemeralRankSelect(ui.Select):
    """Rank select for ephemeral use."""

    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=name, emoji=emoji)
            for name, emoji in RANKS
        ]
        super().__init__(
            placeholder="🎮 Select your current rank...",
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        view: EphemeralOnboardingView = self.view
        view.selected_rank = self.values[0]
        view._update_confirm_button()
        await interaction.response.edit_message(view=view)


class EphemeralOnboardingView(ui.View):
    """Ephemeral onboarding view for /onboard command."""

    def __init__(self, bot: commands.Bot, user_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
        self.user_id = user_id
        self.selected_region: Optional[str] = None
        self.selected_rank: Optional[str] = None

        self.add_item(EphemeralRegionSelect())
        self.add_item(EphemeralRankSelect())

    def _update_confirm_button(self):
        """Enable confirm when both selected."""
        self.confirm_button.disabled = not (self.selected_region and self.selected_rank)

    @ui.button(
        label="✅ Complete Onboarding",
        style=discord.ButtonStyle.success,
        disabled=True,
        row=2,
    )
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle confirmation."""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "❌ This is not your onboarding session.",
                ephemeral=True,
            )

        if not self.selected_region or not self.selected_rank:
            return await interaction.response.send_message(
                "❌ Please select both region and rank.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        # Complete onboarding
        success = await self.bot.player_service.complete_onboarding(
            discord_id=self.user_id,
            region=self.selected_region,
            claimed_rank=self.selected_rank,
            display_name=interaction.user.display_name,
        )

        if not success:
            return await interaction.followup.send(
                "❌ Failed to save. Please try again.",
                ephemeral=True,
            )

        # Disable view
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        region_display = REGIONS.get(self.selected_region, self.selected_region)
        await interaction.followup.send(
            f"✅ **Welcome aboard!**\n\n"
            f"🌍 **Region**: {region_display}\n"
            f"🎮 **Starting Rank**: {self.selected_rank}\n\n"
            f"You're all set!",
            ephemeral=True,
        )

    async def on_timeout(self):
        """Handle timeout."""
        for item in self.children:
            item.disabled = True


# -----------------------------------------------------------------------------
# Onboarding Cog
# -----------------------------------------------------------------------------


class OnboardingCog(commands.Cog):
    """
    Player onboarding for UMS Bot Core.

    Hero Feature A: Modern Onboarding Panel
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Register persistent view."""
        self.bot.add_view(PersistentOnboardingView(self.bot))
        log.info("[ONBOARDING] Registered PersistentOnboardingView")

    def _create_panel_embed(self) -> discord.Embed:
        """Create onboarding panel embed."""
        embed = discord.Embed(
            title="🎮 Player Onboarding",
            description=(
                "**Welcome to the tournament system!**\n\n"
                "Set up your profile to get started:\n"
                "• 🌍 Select your **region** for fair matchmaking\n"
                "• 🎮 Set your **starting rank** for seeding\n\n"
                "This ensures balanced tournaments and fair matches!"
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Complete onboarding to join tournaments")
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
        await interaction.response.send_message(
            "✅ Onboarding panel posted!",
            ephemeral=True,
        )

        log.info(
            f"[ONBOARDING] Panel posted in #{interaction.channel.name} "
            f"({interaction.guild.name})"
        )

    @app_commands.command(
        name="onboard",
        description="Set up your player profile",
    )
    async def onboard(self, interaction: discord.Interaction):
        """Send ephemeral onboarding UI."""
        # Check if already onboarded
        if hasattr(self.bot, "player_service"):
            player = await self.bot.player_service.get_by_discord_id(
                interaction.user.id
            )
            if player and player.has_onboarded:
                region_display = REGIONS.get(player.region, player.region or "Not set")
                return await interaction.response.send_message(
                    f"✅ You've already completed onboarding!\n\n"
                    f"🌍 **Region**: {region_display}\n"
                    f"🎮 **Rank**: {player.claimed_rank or 'Not set'}\n\n"
                    f"You can update your profile by onboarding again.",
                    ephemeral=True,
                )

        embed = self._create_panel_embed()
        view = EphemeralOnboardingView(self.bot, interaction.user.id)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(OnboardingCog(bot))
