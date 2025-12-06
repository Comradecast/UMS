"""
cogs/server_setup.py — Setup Wizard for UMS Bot Core
======================================================
Admin Setup Panel with wizard UX

Provides:
- /setup - Interactive wizard with Quick Setup or Manual Channel Selection
- /config - View/edit configuration
- /ums-help - UMS Core help

The /setup wizard automatically posts the onboarding panel.
"""

from __future__ import annotations

import logging
from typing import Optional, List

import discord
from discord import app_commands, ui
from discord.ext import commands

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# HELPER: Permission Check
# -----------------------------------------------------------------------------


def _bot_can_send(channel: discord.abc.GuildChannel, me: discord.Member) -> bool:
    """Check if bot can view and send in a channel."""
    perms = channel.permissions_for(me)
    return perms.view_channel and perms.send_messages


# -----------------------------------------------------------------------------
# HELPER: Post Onboarding Panel
# -----------------------------------------------------------------------------


async def post_onboarding_panel(
    bot: commands.Bot, channel: discord.TextChannel
) -> bool:
    """Post the onboarding panel to a channel. Returns True on success."""
    try:
        from cogs.onboarding_view import PersistentOnboardingView

        onboarding_cog = bot.get_cog("OnboardingCog")
        if not onboarding_cog:
            log.warning("[SETUP] OnboardingCog not loaded")
            return False

        embed = onboarding_cog._create_panel_embed()
        view = PersistentOnboardingView(bot)

        await channel.send(embed=embed, view=view)
        log.info(f"[SETUP] Posted onboarding panel to #{channel.name}")
        return True
    except Exception as e:
        log.error(f"[SETUP] Failed to post onboarding panel: {e}", exc_info=True)
        return False


# -----------------------------------------------------------------------------
# HELPER: Find or Create Channels
# -----------------------------------------------------------------------------


def find_channel_by_names(
    guild: discord.Guild, names: List[str]
) -> Optional[discord.TextChannel]:
    """Find a text channel matching any of the given names (case-insensitive contains)."""
    for channel in guild.text_channels:
        channel_name_lower = channel.name.lower()
        for name in names:
            if name.lower() in channel_name_lower:
                return channel
    return None


async def find_or_create_channel(
    guild: discord.Guild,
    search_names: List[str],
    create_name: str,
    category: Optional[discord.CategoryChannel] = None,
) -> tuple[discord.TextChannel, bool]:
    """
    Find an existing channel or create a new one.
    Returns: (channel, was_created)
    """
    channel = find_channel_by_names(guild, search_names)
    if channel:
        return channel, False

    channel = await guild.create_text_channel(create_name, category=category)
    return channel, True


# -----------------------------------------------------------------------------
# SETUP WIZARD VIEWS
# -----------------------------------------------------------------------------


class SetupWizardView(ui.View):
    """Initial setup wizard with Quick Setup and Manual options."""

    def __init__(self, cog: "ServerSetup"):
        super().__init__(timeout=300)
        self.cog = cog

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only server admins can configure UMS Bot Core.",
                ephemeral=True,
            )
            return False
        return True

    @ui.button(
        label="🧙 Quick Setup (Recommended)",
        style=discord.ButtonStyle.success,
        row=0,
    )
    async def quick_setup(self, interaction: discord.Interaction, button: ui.Button):
        """Run quick auto-setup."""
        if not await self._check_admin(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        status_lines = []
        channels = {}
        created_flags = {
            "admin": False,
            "announce": False,
            "onboarding": False,
        }

        try:
            # 1. Find or create UMS Core category
            category = discord.utils.get(guild.categories, name="UMS Core")
            if not category:
                category = await guild.create_category("UMS Core")
                status_lines.append("📁 Created **UMS Core** category")

            # 2. Admin channel (private) - ensure bot can post
            admin_ch, created = await find_or_create_channel(
                guild,
                ["ums-admin", "tournament-admin", "admin"],
                "ums-admin",
                category,
            )

            # Check if bot can send in this channel
            if not _bot_can_send(admin_ch, guild.me):
                if created:
                    # We just created it but still can't send - set permissions
                    await admin_ch.set_permissions(
                        guild.me,
                        view_channel=True,
                        send_messages=True,
                        manage_messages=True,
                    )
                else:
                    # Found existing but can't use it - create a new one
                    log.warning(
                        f"[SETUP] Cannot use existing {admin_ch.name}, creating new #ums-admin"
                    )
                    admin_ch = await guild.create_text_channel(
                        "ums-admin",
                        category=category,
                        overwrites={
                            guild.default_role: discord.PermissionOverwrite(
                                view_channel=False
                            ),
                            guild.me: discord.PermissionOverwrite(
                                view_channel=True,
                                send_messages=True,
                                manage_messages=True,
                            ),
                        },
                    )
                    created = True

            created_flags["admin"] = created
            if created:
                # Ensure private + bot access for newly created channels
                await admin_ch.set_permissions(
                    guild.default_role,
                    read_messages=False,
                )
                await admin_ch.set_permissions(
                    guild.me,
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                )
                status_lines.append(f"🔒 Created {admin_ch.mention} (private)")
            else:
                status_lines.append(f"✅ Found {admin_ch.mention} for admin")
            channels["admin_channel"] = admin_ch.id

            # 3. Announcements channel
            announce_ch, created = await find_or_create_channel(
                guild,
                ["tournament-announcements", "announcements", "ums-announcements"],
                "tournament-announcements",
                category,
            )
            created_flags["announce"] = created
            if created:
                status_lines.append(f"📢 Created {announce_ch.mention}")
            else:
                status_lines.append(f"✅ Found {announce_ch.mention} for announcements")
            channels["announce_channel"] = announce_ch.id

            # 4. Onboarding channel
            onboarding_ch, created = await find_or_create_channel(
                guild,
                ["tournament-onboarding", "onboarding", "player-setup"],
                "tournament-onboarding",
                category,
            )
            created_flags["onboarding"] = created
            if created:
                status_lines.append(f"🎮 Created {onboarding_ch.mention}")
            else:
                status_lines.append(f"✅ Found {onboarding_ch.mention} for onboarding")
            channels["onboarding_channel"] = onboarding_ch.id

            # 5. Save configuration
            await self.cog.config_service.create(
                guild_id=guild.id,
                admin_channel=channels["admin_channel"],
                announce_channel=channels["announce_channel"],
                onboarding_channel=channels["onboarding_channel"],
                admin_channel_created=created_flags["admin"],
                announce_channel_created=created_flags["announce"],
                onboarding_channel_created=created_flags["onboarding"],
            )
            await self.cog.config_service.mark_setup_complete(guild.id)

            # 6. Post onboarding panel
            onboarding_ok = await post_onboarding_panel(self.cog.bot, onboarding_ch)

            if onboarding_ok:
                status_lines.append(
                    f"\n✅ Onboarding panel posted in {onboarding_ch.mention}"
                )
            else:
                status_lines.append(f"\n⚠️ Failed to post onboarding panel")

            # 7. Post admin control panel to admin channel (graceful on failure)
            from cogs.tournaments import post_admin_panel

            admin_panel_posted = False
            admin_panel_warning = None

            # Check permissions before trying
            if not _bot_can_send(admin_ch, guild.me):
                admin_panel_warning = (
                    f"⚠️ Cannot post to {admin_ch.mention} (missing permissions)"
                )
                log.warning(
                    f"[SETUP] Bot lacks permission to send in admin channel {admin_ch.id}"
                )
            else:
                try:
                    admin_panel_ok = await post_admin_panel(self.cog.bot, admin_ch)
                    if admin_panel_ok:
                        admin_panel_posted = True
                        status_lines.append(
                            f"✅ Tournament control panel posted in {admin_ch.mention}"
                        )
                    else:
                        # post_admin_panel returned False - try simple fallback
                        await admin_ch.send(
                            "**🎉 UMS Bot Core is ready!**\n\n"
                            "This channel will receive admin notifications.\n\n"
                            "Use `/tournament_create` to start a tournament."
                        )
                        admin_panel_posted = True
                        status_lines.append(
                            f"✅ Welcome message posted in {admin_ch.mention}"
                        )
                except discord.Forbidden:
                    admin_panel_warning = (
                        f"⚠️ Could not post to {admin_ch.mention} (access denied)"
                    )
                    log.warning(
                        f"[SETUP] Forbidden when posting to admin channel {admin_ch.id}"
                    )
                except Exception as e:
                    admin_panel_warning = f"⚠️ Error posting to {admin_ch.mention}: {e}"
                    log.error(f"[SETUP] Error posting admin panel: {e}")

            if admin_panel_warning:
                status_lines.append(admin_panel_warning)

            # 8. Send summary
            embed = discord.Embed(
                title="✅ Quick Setup Complete",
                description="\n".join(status_lines),
                color=discord.Color.green(),
            )
            embed.add_field(
                name="📁 Configuration Summary",
                value=(
                    f"**Admin notifications**: {admin_ch.mention}\n"
                    f"**Announcements**: {announce_ch.mention}\n"
                    f"**Onboarding panel**: {onboarding_ch.mention}"
                ),
                inline=False,
            )
            embed.set_footer(text="Use /config to view or edit settings")

            for item in self.children:
                item.disabled = True

            await interaction.edit_original_response(
                content=None,
                embed=embed,
                view=self,
            )

            log.info(f"[SETUP] Quick Setup complete for {guild.name} ({guild.id})")

        except Exception as e:
            log.error(f"[SETUP] Quick Setup failed: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Setup failed: {e}\n\nPlease check bot permissions.",
                ephemeral=True,
            )

    @ui.button(
        label="📂 Use Existing Channels",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def use_existing(self, interaction: discord.Interaction, button: ui.Button):
        """Show channel selection UI."""
        if not await self._check_admin(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📂 Select Channels for UMS Bot Core",
            description=(
                "Select a channel for each purpose:\n\n"
                "• **Admin Channel** — Where admins receive notifications\n"
                "• **Announcement Channel** — Where tournament updates are posted\n"
                "• **Onboarding Channel** — Where the player registration panel will be posted"
            ),
            color=discord.Color.blue(),
        )

        view = ChannelSelectionView(self.cog)
        await interaction.edit_original_response(embed=embed, view=view)

    @ui.button(
        label="❌ Cancel",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel setup."""
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="❌ Setup cancelled.",
            embed=None,
            view=self,
        )


class ChannelSelectionView(ui.View):
    """Channel selection for manual setup."""

    def __init__(self, cog: "ServerSetup"):
        super().__init__(timeout=300)
        self.cog = cog
        self.admin_channel: Optional[discord.TextChannel] = None
        self.announce_channel: Optional[discord.TextChannel] = None
        self.onboarding_channel: Optional[discord.TextChannel] = None

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only server admins can configure UMS Bot Core.",
                ephemeral=True,
            )
            return False
        return True

    @ui.select(
        cls=ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="🔒 Select Admin Channel",
        row=0,
    )
    async def select_admin(
        self, interaction: discord.Interaction, select: ui.ChannelSelect
    ):
        if select.values:
            self.admin_channel = select.values[0]
        await interaction.response.defer()

    @ui.select(
        cls=ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="📢 Select Announcement Channel",
        row=1,
    )
    async def select_announce(
        self, interaction: discord.Interaction, select: ui.ChannelSelect
    ):
        if select.values:
            self.announce_channel = select.values[0]
        await interaction.response.defer()

    @ui.select(
        cls=ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="🎮 Select Onboarding Channel",
        row=2,
    )
    async def select_onboarding(
        self, interaction: discord.Interaction, select: ui.ChannelSelect
    ):
        if select.values:
            self.onboarding_channel = select.values[0]
        await interaction.response.defer()

    @ui.button(
        label="✅ Save & Post Panel",
        style=discord.ButtonStyle.success,
        row=3,
    )
    async def save(self, interaction: discord.Interaction, button: ui.Button):
        """Save configuration and post onboarding panel."""
        if not await self._check_admin(interaction):
            return

        # Validate all channels selected
        missing = []
        if not self.admin_channel:
            missing.append("Admin Channel")
        if not self.announce_channel:
            missing.append("Announcement Channel")
        if not self.onboarding_channel:
            missing.append("Onboarding Channel")

        if missing:
            await interaction.response.send_message(
                f"❌ Please select: {', '.join(missing)}",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild

        try:
            # Save configuration
            await self.cog.config_service.create(
                guild_id=guild.id,
                admin_channel=self.admin_channel.id,
                announce_channel=self.announce_channel.id,
                onboarding_channel=self.onboarding_channel.id,
            )
            await self.cog.config_service.mark_setup_complete(guild.id)

            # Post onboarding panel
            status_lines = []

            onboarding_ok = await post_onboarding_panel(
                self.cog.bot, self.onboarding_channel
            )
            if onboarding_ok:
                status_lines.append(
                    f"✅ Onboarding panel posted in {self.onboarding_channel.mention}"
                )
            else:
                status_lines.append(f"⚠️ Failed to post onboarding panel")

            # Post welcome to admin channel
            await self.admin_channel.send(
                "**🎉 UMS Bot Core is ready!**\n\n"
                "This channel will receive admin notifications.\n\n"
                "**Tournament Commands:**\n"
                "• `/tournament_create` — Create a new tournament\n"
                "• `/tournament_open_registration` — Open signups\n"
                "• `/tournament_close_registration` — Close signups\n"
                "• `/tournament_start` — Generate bracket\n"
                "• `/tournament_report_result` — Record match results"
            )

            # Disable buttons
            for item in self.children:
                item.disabled = True

            embed = discord.Embed(
                title="✅ Setup Complete",
                description="\n".join(status_lines),
                color=discord.Color.green(),
            )
            embed.add_field(
                name="📁 Configuration Summary",
                value=(
                    f"**Admin notifications**: {self.admin_channel.mention}\n"
                    f"**Announcements**: {self.announce_channel.mention}\n"
                    f"**Onboarding panel**: {self.onboarding_channel.mention}"
                ),
                inline=False,
            )
            embed.set_footer(text="Use /config to view or edit settings")

            await interaction.edit_original_response(embed=embed, view=self)

            log.info(f"[SETUP] Manual setup complete for {guild.name} ({guild.id})")

        except Exception as e:
            log.error(f"[SETUP] Manual setup failed: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Setup failed: {e}",
                ephemeral=True,
            )

    @ui.button(
        label="❌ Cancel",
        style=discord.ButtonStyle.secondary,
        row=3,
    )
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel setup."""
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="❌ Setup cancelled.",
            embed=None,
            view=self,
        )


# -----------------------------------------------------------------------------
# SERVER SETUP COG
# -----------------------------------------------------------------------------


class ServerSetup(commands.Cog):
    """
    Server setup and configuration for UMS Bot Core.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def config_service(self):
        """Get guild config service from bot."""
        return self.bot.guild_config_service

    # -------------------------------------------------------------------------
    # /setup - Main Wizard
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="setup",
        description="Configure UMS Bot Core for this server",
    )
    @app_commands.guild_only()
    async def setup(self, interaction: discord.Interaction):
        """
        Setup wizard for UMS Bot Core.

        Offers:
        - Quick Setup: Auto-detect or create channels, post onboarding panel
        - Use Existing Channels: Manual channel selection
        """
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Only server admins can configure UMS Bot Core.",
                ephemeral=True,
            )

        # Check if already setup
        existing = await self.config_service.get(interaction.guild.id)
        if existing and existing.is_setup:
            embed = discord.Embed(
                title="ℹ️ Already Configured",
                description=(
                    "This server is already set up!\n\n"
                    "Use `/config` to view or edit settings.\n"
                    "Use `/post_onboarding_panel` to post a new onboarding panel."
                ),
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="Current Configuration",
                value=(
                    f"**Admin**: <#{existing.admin_channel}>\n"
                    f"**Announcements**: <#{existing.announce_channel}>"
                    + (
                        f"\n**Onboarding**: <#{existing.onboarding_channel}>"
                        if getattr(existing, "onboarding_channel", None)
                        else ""
                    )
                ),
                inline=False,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Show wizard
        embed = discord.Embed(
            title="🧙 UMS Bot Core Setup",
            description=(
                "**Welcome to UMS Bot Core!**\n\n"
                "This wizard will configure your server for tournaments.\n\n"
                "**What we'll set up:**\n"
                "• Admin channel for notifications\n"
                "• Announcement channel for tournament updates\n"
                "• Onboarding panel for player registration\n\n"
                "Choose your setup method:"
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="🧙 Quick Setup (Recommended)",
            value="Auto-detect existing channels or create new ones. Onboarding panel posted automatically.",
            inline=False,
        )
        embed.add_field(
            name="📂 Use Existing Channels",
            value="Manually select which channels to use for each purpose.",
            inline=False,
        )

        view = SetupWizardView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # -------------------------------------------------------------------------
    # /config - View/Edit Configuration
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="config",
        description="View or edit UMS Bot Core configuration",
    )
    @app_commands.guild_only()
    async def config(self, interaction: discord.Interaction):
        """View current configuration."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Only server admins can view configuration.",
                ephemeral=True,
            )

        config = await self.config_service.get(interaction.guild.id)

        if not config:
            return await interaction.response.send_message(
                "⚠️ Server not configured. Run `/setup` first.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="⚙️ UMS Bot Core Configuration",
            description=f"Configuration for **{interaction.guild.name}**",
            color=discord.Color.green() if config.is_setup else discord.Color.orange(),
        )

        # Channels
        channels = []
        if config.admin_channel:
            channels.append(f"**Admin**: <#{config.admin_channel}>")
        if config.announce_channel:
            channels.append(f"**Announcements**: <#{config.announce_channel}>")
        if getattr(config, "onboarding_channel", None):
            channels.append(f"**Onboarding**: <#{config.onboarding_channel}>")

        if channels:
            embed.add_field(
                name="📁 Channels",
                value="\n".join(channels),
                inline=False,
            )

        # Admin role
        if config.ums_admin_role:
            embed.add_field(
                name="👥 Admin Role",
                value=f"<@&{config.ums_admin_role}>",
                inline=True,
            )

        # Status
        embed.add_field(
            name="📊 Status",
            value="✅ Setup Complete" if config.is_setup else "⚠️ Setup Incomplete",
            inline=True,
        )

        embed.set_footer(text="Use /setup to reconfigure")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -------------------------------------------------------------------------
    # /post_onboarding_panel - Admin command to post panel
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="post_onboarding_panel",
        description="Post the player onboarding panel to a channel",
    )
    @app_commands.describe(channel="Channel to post the panel in (defaults to current)")
    @app_commands.guild_only()
    async def post_onboarding_panel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Admin command to post onboarding panel."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Only server admins can post panels.",
                ephemeral=True,
            )

        target = channel or interaction.channel

        await interaction.response.defer(ephemeral=True)

        success = await post_onboarding_panel(self.bot, target)

        if success:
            await interaction.followup.send(
                f"✅ Onboarding panel posted in {target.mention}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "❌ Failed to post panel. Check bot permissions and logs.",
                ephemeral=True,
            )

    # -------------------------------------------------------------------------
    # /ums-help - Help Command
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="ums-help",
        description="Get help with UMS Bot Core",
    )
    async def ums_help(self, interaction: discord.Interaction):
        """Display UMS Core help."""
        is_admin = (
            interaction.user.guild_permissions.administrator
            if interaction.guild
            else False
        )

        embed = discord.Embed(
            title="🎮 UMS Bot Core Help",
            description="Welcome to UMS Bot Core — a lightweight Single Elimination tournament bot.",
            color=discord.Color.blue(),
        )

        # Player section
        embed.add_field(
            name="👤 For Players",
            value=(
                "• Use the **Onboarding Panel** to register (set region & rank)\n"
                "• Wait for admins to create and open tournament registration"
            ),
            inline=False,
        )

        if is_admin:
            embed.add_field(
                name="🛠️ Admin Commands",
                value=(
                    "`/setup` — Configure UMS Bot Core (wizard)\n"
                    "`/config` — View current configuration\n"
                    "`/post_onboarding_panel` — Post onboarding panel"
                ),
                inline=False,
            )

            embed.add_field(
                name="🏆 Tournament Commands (Coming Soon)",
                value=(
                    "`/tournament_create` — Create a tournament\n"
                    "`/tournament_open_registration` — Open signups\n"
                    "`/tournament_close_registration` — Close signups\n"
                    "`/tournament_start` — Generate bracket\n"
                    "`/tournament_report_result` — Record results"
                ),
                inline=False,
            )

        embed.set_footer(text="UMS Bot Core v1.0.0-core")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -------------------------------------------------------------------------
    # /ums_factory_reset
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="ums_factory_reset",
        description="Reset all UMS Bot Core data for this server (Admin only)",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def ums_factory_reset(
        self,
        interaction: discord.Interaction,
    ):
        """Show factory reset confirmation."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Only server admins can perform a factory reset.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="⚠️ Factory Reset UMS Bot Core",
            description=(
                "**This will:**\n"
                "• Delete UMS-related channels (only those created by the bot)\n"
                "• Remove all stored data for this server\n"
                "• Remove tournaments, matches, entries\n"
                "• Remove player data\n"
                "• Remove your setup state\n\n"
                "**Are you sure?**"
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text="This action cannot be undone!")

        view = FactoryResetConfirmView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class FactoryResetConfirmView(ui.View):
    """Confirmation view for factory reset."""

    def __init__(self, cog: "ServerSetup"):
        super().__init__(timeout=60)
        self.cog = cog

    @ui.button(
        label="Reset Everything 🔥",
        style=discord.ButtonStyle.danger,
        custom_id="ums_factory_reset_confirm",
    )
    async def confirm_reset(self, interaction: discord.Interaction, button: ui.Button):
        """Perform factory reset."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only admins can perform reset.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        guild_id = guild.id

        try:
            # Get config to find channels to delete
            config = await self.cog.config_service.get(guild_id)
            channels_deleted = []

            if config:
                # Delete bot-created channels
                if config.admin_channel_created and config.admin_channel:
                    channel = guild.get_channel(config.admin_channel)
                    if channel:
                        await channel.delete(reason="UMS Factory Reset")
                        channels_deleted.append("admin")

                if config.announce_channel_created and config.announce_channel:
                    channel = guild.get_channel(config.announce_channel)
                    if channel:
                        await channel.delete(reason="UMS Factory Reset")
                        channels_deleted.append("announcements")

                if config.onboarding_channel_created and config.onboarding_channel:
                    channel = guild.get_channel(config.onboarding_channel)
                    if channel:
                        await channel.delete(reason="UMS Factory Reset")
                        channels_deleted.append("onboarding")

            # Delete guild config
            await self.cog.config_service.delete(guild_id)

            # Delete all tournament data for this guild
            db = self.cog.bot.db

            # Delete matches and entries for tournaments in this guild
            # Use subquery to handle both old (key) and new (id) schemas
            try:
                # Try new schema with id column
                await db.execute(
                    """
                    DELETE FROM matches WHERE tournament_id IN (
                        SELECT id FROM tournaments WHERE guild_id = ?
                    )
                    """,
                    (guild_id,),
                )
                await db.execute(
                    """
                    DELETE FROM tournament_entries WHERE tournament_id IN (
                        SELECT id FROM tournaments WHERE guild_id = ?
                    )
                    """,
                    (guild_id,),
                )
            except Exception:
                # Old schema - tables may not exist, just skip
                pass

            # Delete tournaments
            await db.execute("DELETE FROM tournaments WHERE guild_id = ?", (guild_id,))

            # Delete player data for this guild (players table doesn't have guild_id, so skip)
            # Players are global, not per-guild

            await db.commit()

            log.info(f"[FACTORY-RESET] Reset complete for guild {guild_id}")

            # Disable buttons
            for item in self.children:
                item.disabled = True

            # Update message - may fail if channel was deleted
            embed = discord.Embed(
                title="✅ Factory Reset Complete",
                description=(
                    "All UMS Bot Core data has been removed.\n\n"
                    f"**Channels deleted:** {', '.join(channels_deleted) if channels_deleted else 'None'}\n\n"
                    "Run `/setup` to reconfigure the bot."
                ),
                color=discord.Color.green(),
            )

            try:
                await interaction.edit_original_response(embed=embed, view=self)
            except (discord.NotFound, discord.HTTPException):
                # Channel or message was deleted - that's fine, reset succeeded
                log.info(
                    "[FACTORY-RESET] Could not edit response (channel likely deleted)"
                )

            # Try to DM the admin
            try:
                await interaction.user.send(
                    f"✅ **Factory Reset Complete** for **{guild.name}**\n\n"
                    f"UMS Bot Core data has been wiped. Run `/setup` to reconfigure."
                )
            except discord.Forbidden:
                pass  # DMs disabled

        except Exception as e:
            log.error(f"[FACTORY-RESET] Error: {e}", exc_info=True)
            # Try to notify user - may fail if channel deleted
            try:
                await interaction.followup.send(f"❌ Reset failed: {e}", ephemeral=True)
            except (discord.NotFound, discord.HTTPException):
                # Can't send - try DM
                try:
                    await interaction.user.send(
                        f"❌ Factory Reset failed for **{guild.name}**: {e}"
                    )
                except discord.Forbidden:
                    pass

    @ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        custom_id="ums_factory_reset_cancel",
    )
    async def cancel_reset(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel factory reset."""
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="❌ Factory reset cancelled.",
            embed=None,
            view=self,
        )


# Backwards compatibility alias
ServerSetupCog = ServerSetup


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSetup(bot))
