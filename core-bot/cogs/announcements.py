"""
Server Announcements - UMS Announcement Wizard

This cog replaces one-off announcement slash commands with a single, flexible
/ums_announce command that drives an announcement wizard.

The wizard:
- Is admin-only (default_permissions(administrator=True))
- Runs ephemeral
- Lets you pick an announcement type (Core Release, Feature Release, Patch Notes, etc.)
- Shows a preview embed
- Lets you publish the announcement into the current channel
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ui.brand import Colors, create_embed, FOOTER_TEXT

log = logging.getLogger(__name__)


ANNOUNCEMENT_TYPES = [
    ("Core Release", "core_release"),
    ("Feature Release", "feature_release"),
    ("Patch Notes", "patch_notes"),
    ("Roadmap Update", "roadmap"),
    ("Event Announcement", "event"),
    ("Custom", "custom"),
]


def build_core_release_embed() -> discord.Embed:
    """Template for a UMS Bot Core production-ready announcement."""
    embed = discord.Embed(
        title="🎉 UMS Bot Core — Now Live & Production Ready!",
        description=(
            "After months of refinement and a ground-up redesign, the **UMS Bot Core** is now "
            "stable, lean, and officially ready for production tournament hosting.\n\n"
            "This release marks the beginning of a truly professional tournament platform."
        ),
        color=Colors.PRIMARY,
    )

    embed.add_field(
        name="⚙️ What Makes UMS Bot Core Special",
        value=(
            "• Clean, predictable architecture\n"
            "• Single-source-of-truth dashboards\n"
            "• Unified match completion logic\n"
            "• Brand-standard UI across all features\n"
            "• Zero legacy codepaths\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🧪 Admin & Dev Tools Included",
        value=(
            "• **Admin Override Wizard** (fix matches instantly)\n"
            "• **Dev Tools Hub** (`/ums_dev_tools`)\n"
            "• **Bracket Tools** panel (advance matches / rounds)\n"
            "• Dummy entry generator for stress testing\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="📊 Stable Tournament Hosting",
        value=(
            "• Clean bracket creation\n"
            "• Automatic dashboards\n"
            "• Self-managed match channels\n"
            "• Safe archiving & lifecycle control\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🚀 Why This Release Matters",
        value=(
            "UMS Bot Core is the foundation of a **commercial-grade tournament platform**.\n"
            "It's lean, hardened, easy to host, and ready for premium feature expansion.\n"
            "This is the gold standard for Sideswipe tournament automation."
        ),
        inline=False,
    )

    embed.add_field(
        name="🧩 Commands to Try",
        value=(
            "**Players:** `/dashboard`\n"
            "**Admins:** `/ums_report_result`\n"
            "**Developers:** `/ums_dev_tools`"
        ),
        inline=False,
    )

    embed.set_footer(text=FOOTER_TEXT)
    return embed


def build_generic_feature_embed() -> discord.Embed:
    """Template for a generic feature release announcement."""
    embed = discord.Embed(
        title="✨ New UMS Feature Release",
        description=(
            "We've shipped new improvements to the Unified Match System. "
            "Here's what's changed in this update:"
        ),
        color=Colors.PRIMARY,
    )

    embed.add_field(
        name="📦 Highlights",
        value=(
            "• New or improved commands\n"
            "• Smoother admin tools\n"
            "• Quality-of-life fixes\n"
            "• Better visibility for players\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🧠 What You Should Do",
        value=(
            "• Type `/dashboard` to explore the updated flows\n"
            "• Check pinned messages or the help command for details\n"
            "• Report any issues in the support channel"
        ),
        inline=False,
    )

    embed.set_footer(text=FOOTER_TEXT)
    return embed


def build_patch_notes_embed() -> discord.Embed:
    """Template for a generic patch notes style announcement."""
    embed = discord.Embed(
        title="🛠️ UMS Patch Notes",
        description=(
            "Small but important improvements have been deployed. "
            "These changes focus on stability, performance, and polish."
        ),
        color=Colors.SUCCESS,
    )

    embed.add_field(
        name="✅ Fixes",
        value=(
            "• Fixed minor bugs in tournament flows\n"
            "• Improved error handling for edge cases\n"
            "• Cleaned up logs and internal tooling\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="⚙️ Under-the-Hood",
        value=(
            "• Better alignment between docs and implementation\n"
            "• Test coverage extended for critical paths\n"
            "• Dev tools refined for faster iteration\n"
        ),
        inline=False,
    )

    embed.set_footer(text=FOOTER_TEXT)
    return embed


def build_roadmap_embed() -> discord.Embed:
    """Template for a roadmap-style announcement."""
    embed = discord.Embed(
        title="🧭 UMS Roadmap Update",
        description=(
            "Here's a quick look at what's coming next for UMS. "
            "This roadmap is subject to change based on feedback and testing."
        ),
        color=Colors.WARNING,
    )

    embed.add_field(
        name="✅ Recently Shipped",
        value=(
            "• Core tournament flows stabilized\n"
            "• Admin Override Wizard\n"
            "• Dev Tools Hub and Bracket Tools\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔜 In Progress",
        value=(
            "• Expanded stats and history\n"
            "• Enhanced dashboards\n"
            "• More admin automation tools\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="🧪 Under Consideration",
        value=(
            "• Premium tournament formats\n"
            "• Web dashboards\n"
            "• Advanced analytics and seasonal ladders\n"
        ),
        inline=False,
    )

    embed.set_footer(text=FOOTER_TEXT)
    return embed


def build_event_embed() -> discord.Embed:
    """Template for a generic tournament/event announcement."""
    embed = discord.Embed(
        title="🏆 Tournament / Event Announcement",
        description=(
            "A new event is being hosted using the Unified Match System. "
            "Check the details below and get ready to queue up."
        ),
        color=Colors.ACCENT,
    )

    embed.add_field(
        name="📅 Basic Details",
        value=(
            "• Date & Time: *(fill this in)*\n"
            "• Mode / Format: *(1v1 / 2v2 / etc.)*\n"
            "• Region / Server: *(NA / EU / etc.)*\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="📝 How to Join",
        value=(
            "• Watch for the registration panel in the tournament channel\n"
            "• Use the buttons on the panel to register\n"
            "• Type `/dashboard` to confirm your registration and match times"
        ),
        inline=False,
    )

    embed.add_field(
        name="📣 Notes",
        value=(
            "• Please be on time for your matches\n"
            "• Follow any rules posted in the event channel\n"
            "• Reach out to staff if you have issues"
        ),
        inline=False,
    )

    embed.set_footer(text=FOOTER_TEXT)
    return embed


class CustomAnnouncementModal(discord.ui.Modal, title="Custom Announcement"):
    """Modal used to collect custom announcement content from the user."""

    heading: discord.ui.TextInput = discord.ui.TextInput(
        label="Title",
        style=discord.TextStyle.short,
        max_length=256,
        required=True,
    )
    body: discord.ui.TextInput = discord.ui.TextInput(
        label="Body",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )
    footer: discord.ui.TextInput = discord.ui.TextInput(
        label="Footer (optional)",
        style=discord.TextStyle.short,
        max_length=256,
        required=False,
    )

    def __init__(self, wizard: "AnnouncementWizardView") -> None:
        super().__init__()
        self.wizard = wizard

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Build an embed from custom text and update the wizard preview."""
        embed = discord.Embed(
            title=self.heading.value,
            description=self.body.value,
            color=Colors.PRIMARY,
        )
        if self.footer.value:
            embed.set_footer(text=self.footer.value)
        else:
            embed.set_footer(text=FOOTER_TEXT)

        # Store on wizard and update the preview message
        self.wizard.current_embed = embed

        if self.wizard.message:
            await self.wizard.message.edit(embed=embed, view=self.wizard)

        await interaction.response.send_message(
            "✅ Custom announcement preview updated. Review and press **Publish** when ready.",
            ephemeral=True,
        )


class AnnouncementTypeSelect(discord.ui.Select):
    """Dropdown to choose which type of announcement to prepare."""

    def __init__(self, wizard: "AnnouncementWizardView") -> None:
        options = [
            discord.SelectOption(label=label, value=value)
            for (label, value) in ANNOUNCEMENT_TYPES
        ]
        super().__init__(
            placeholder="Choose the announcement type...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        # Restrict usage to the original invoker
        if interaction.user.id != self.wizard.author.id:
            await interaction.response.send_message(
                "You didn't start this wizard.", ephemeral=True
            )
            return

        announcement_type = self.values[0]
        self.wizard.selected_type = announcement_type

        # Build the appropriate template
        if announcement_type == "core_release":
            embed = build_core_release_embed()
        elif announcement_type == "feature_release":
            embed = build_generic_feature_embed()
        elif announcement_type == "patch_notes":
            embed = build_patch_notes_embed()
        elif announcement_type == "roadmap":
            embed = build_roadmap_embed()
        elif announcement_type == "event":
            embed = build_event_embed()
        else:
            # Custom: open the modal and let the user fill in the content
            await interaction.response.send_modal(CustomAnnouncementModal(self.wizard))
            return

        # For non-custom types, update the preview directly
        self.wizard.current_embed = embed

        # Acknowledge the interaction and update the wizard message
        await interaction.response.defer(ephemeral=True, thinking=False)
        if self.wizard.message:
            await self.wizard.message.edit(embed=embed, view=self.wizard)


class AnnouncementWizardView(discord.ui.View):
    """View that drives the announcement creation and publishing process."""

    def __init__(self, author: discord.Member, *, timeout: int = 300) -> None:
        super().__init__(timeout=timeout)
        self.author: discord.Member = author
        self.message: Optional[discord.Message] = None
        self.selected_type: Optional[str] = None
        self.current_embed: Optional[discord.Embed] = None

        # Add the type select to the view
        self.add_item(AnnouncementTypeSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the original invoker can interact with this view."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "You didn't start this wizard.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="Publish",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def publish_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Publish the currently previewed announcement into the channel."""
        if not self.current_embed:
            await interaction.response.send_message(
                "There is no announcement to publish yet. Choose a type or submit custom content first.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not isinstance(
            channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)
        ):
            await interaction.response.send_message(
                "Cannot determine a valid text channel to publish this announcement.",
                ephemeral=True,
            )
            return

        # Publish publicly
        await channel.send(embed=self.current_embed)

        # Disable the view to avoid double-publishing
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True

        if self.message:
            await self.message.edit(view=self)

        await interaction.response.send_message(
            "✅ Announcement published!", ephemeral=True
        )

        log.info(
            f"[ANNOUNCE] User {interaction.user.id} published announcement type={self.selected_type} "
            f"in channel={channel.id}"
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Cancel the wizard and delete the ephemeral message."""
        if self.message:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            "❌ Announcement wizard closed.", ephemeral=True
        )
        self.stop()


class AnnouncementsCog(commands.Cog):
    """UMS Announcement Wizard cog."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ums_announce",
        description="Open the UMS Announcement Wizard (admin-only).",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def ums_announce(self, interaction: discord.Interaction) -> None:
        """Entry point for the announcement wizard."""
        await interaction.response.defer(ephemeral=True, thinking=False)

        embed = create_embed(
            "UMS Announcement Wizard",
            (
                "Use this wizard to prepare and publish server announcements for UMS.\n\n"
                "1. Choose the announcement type from the dropdown.\n"
                "2. Review or customize the preview embed.\n"
                "3. Press **Publish** to post it in this channel.\n\n"
                "For 'Custom' announcements, you'll be asked to fill in the title and body."
            ),
        )

        view = AnnouncementWizardView(author=interaction.user)
        # Send the initial ephemeral message and attach the view
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = msg


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AnnouncementsCog(bot))
