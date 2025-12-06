"""
cogs/requests.py — Tournament Request Flow (Approval Required)
---------------------------------------------------------------
UMS Bot Core - Hero Feature C: Tournament Request Flow

Flow:
1. Member clicks "Request Tournament" button → multi-step form
2. Request saved to DB with status='pending'
3. Admin channel receives review message with Approve/Decline buttons
4. Admin approves → Tournament created, announcement posted
5. Admin declines → Request closed, optional DM to requester

All admin actions re-verify permissions and request state.
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

import discord
from discord import app_commands, ui
from discord.ext import commands

log = logging.getLogger(__name__)

# Custom IDs for persistent views
REQUEST_BUTTON_CUSTOM_ID = "ums_core:request_tournament"
APPROVE_BUTTON_PREFIX = "ums_core:approve:"
DECLINE_BUTTON_PREFIX = "ums_core:decline:"

# Valid region options
REGION_OPTIONS = [
    ("OPEN", "All Regions Welcome"),
    ("EU", "Europe"),
    ("US-E", "US East"),
    ("US-W", "US West"),
    ("US-C", "US Central"),
    ("ME", "Middle East"),
    ("JPN", "Japan"),
    ("OCE", "Oceania"),
    ("SAM", "South America"),
    ("ASIA", "Asia"),
]

# Valid format options (Single Elimination only for UMS Core)
FORMAT_OPTIONS = [
    ("1v1 Single Elimination", "1v1 SE"),
    ("2v2 Single Elimination", "2v2 SE"),
    ("3v3 Single Elimination", "3v3 SE"),
]

SIZE_OPTIONS = [
    ("4", "4 Players"),
    ("8", "8 Players"),
    ("16", "16 Players"),
    ("32", "32 Players"),
]

MATCH_LENGTH_OPTIONS = [
    ("Bo1", "Best of 1"),
    ("Bo3", "Best of 3"),
    ("Bo5", "Best of 5"),
]


# -----------------------------------------------------------------------------
# TIME PARSING
# -----------------------------------------------------------------------------


def parse_start_time(time_str: str) -> Tuple[Optional[int], str]:
    """
    Parse start time string into Unix timestamp.

    Returns: (timestamp, display_string) or (None, original_string)
    """
    if not time_str:
        return None, "TBD"

    time_str = time_str.strip().lower()
    now = datetime.now()

    # Relative: 30m, 2h, 1d
    relative_match = re.match(r"^(\d+)\s*([mhd])", time_str)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)

        if unit == "m":
            delta = timedelta(minutes=amount)
            display = f"in {amount} minute(s)"
        elif unit == "h":
            delta = timedelta(hours=amount)
            display = f"in {amount} hour(s)"
        else:  # d
            delta = timedelta(days=amount)
            display = f"in {amount} day(s)"

        target = now + delta
        return int(target.timestamp()), display

    # Tomorrow + time: "tomorrow 6pm"
    if time_str.startswith("tomorrow"):
        time_part = time_str.replace("tomorrow", "").strip()
        time_match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_part)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3)

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            target = (now + timedelta(days=1)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            return int(target.timestamp()), f"tomorrow at {hour}:{minute:02d}"

    # Simple time: "6pm", "18:00"
    time_match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_str)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        period = time_match.group(3)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        return int(target.timestamp()), target.strftime("%I:%M %p")

    return None, time_str


# -----------------------------------------------------------------------------
# REQUEST FORM VIEWS
# -----------------------------------------------------------------------------


class RegionSelect(ui.Select):
    """Region selection dropdown."""

    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=value)
            for value, label in REGION_OPTIONS
        ]
        super().__init__(
            placeholder="🌍 Select region...",
            options=options,
            custom_id="request_form:region",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.region = self.values[0]
        await interaction.response.defer()


class FormatSelect(ui.Select):
    """Format selection dropdown."""

    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=value)
            for value, label in FORMAT_OPTIONS
        ]
        super().__init__(
            placeholder="🎮 Select format...",
            options=options,
            custom_id="request_form:format",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.format = self.values[0]
        await interaction.response.defer()


class SizeSelect(ui.Select):
    """Size selection dropdown."""

    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=value)
            for value, label in SIZE_OPTIONS
        ]
        super().__init__(
            placeholder="👥 Select size...",
            options=options,
            custom_id="request_form:size",
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.size = self.values[0]
        await interaction.response.defer()


class RequestFormView(ui.View):
    """Multi-select form for tournament request details."""

    def __init__(self, cog: "RequestsCog"):
        super().__init__(timeout=300)
        self.cog = cog
        self.region: Optional[str] = None
        self.format: Optional[str] = None
        self.size: Optional[str] = None

        self.add_item(RegionSelect())
        self.add_item(FormatSelect())
        self.add_item(SizeSelect())

    @ui.button(
        label="Continue →",
        style=discord.ButtonStyle.primary,
        row=3,
    )
    async def continue_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        # Validate selections
        if not self.region:
            return await interaction.response.send_message(
                "❌ Please select a region.", ephemeral=True
            )
        if not self.format:
            return await interaction.response.send_message(
                "❌ Please select a format.", ephemeral=True
            )
        if not self.size:
            return await interaction.response.send_message(
                "❌ Please select a size.", ephemeral=True
            )

        # Open final modal
        modal = RequestDetailsModal(
            self.cog,
            region=self.region,
            format=self.format,
            size=self.size,
        )
        await interaction.response.send_modal(modal)


class RequestDetailsModal(ui.Modal, title="Tournament Details"):
    """Final modal for name and start time."""

    name = ui.TextInput(
        label="Tournament Name",
        placeholder="e.g., Weekend Showdown",
        max_length=50,
        required=True,
    )

    start_time = ui.TextInput(
        label="Start Time (optional)",
        placeholder="e.g., 6pm, tomorrow 8pm, 2h",
        max_length=50,
        required=False,
    )

    match_length = ui.TextInput(
        label="Match Length",
        placeholder="Bo1, Bo3, or Bo5",
        default="Bo3",
        max_length=10,
        required=False,
    )

    def __init__(self, cog: "RequestsCog", region: str, format: str, size: str):
        super().__init__()
        self.cog = cog
        self._region = region
        self._format = format
        self._size = size

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.handle_request_submit(
            interaction=interaction,
            name=str(self.name.value).strip(),
            region=self._region,
            format=self._format,
            size=self._size,
            match_length=str(self.match_length.value).strip() or "Bo3",
            start_time=str(self.start_time.value).strip(),
        )


# -----------------------------------------------------------------------------
# PERSISTENT REQUEST BUTTON
# -----------------------------------------------------------------------------


class RequestButtonView(ui.View):
    """Persistent button to start request flow."""

    def __init__(self, cog: "RequestsCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(
        label="Request Tournament",
        style=discord.ButtonStyle.primary,
        custom_id=REQUEST_BUTTON_CUSTOM_ID,
        emoji="🏆",
    )
    async def request_button(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await self.cog.start_request_flow(interaction)
        except Exception as e:
            log.error(f"[REQUESTS] Error in request button: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ An error occurred. Please try again.", ephemeral=True
                )
            except:
                pass


# -----------------------------------------------------------------------------
# ADMIN REVIEW VIEW
# -----------------------------------------------------------------------------


class AdminReviewView(ui.View):
    """Approve/Decline buttons for admin review."""

    def __init__(self, cog: "RequestsCog", request_id: int):
        super().__init__(timeout=None)  # Persistent
        self.cog = cog
        self.request_id = request_id

        # Create buttons with unique custom_ids
        approve_btn = ui.Button(
            label="✅ Approve",
            style=discord.ButtonStyle.success,
            custom_id=f"{APPROVE_BUTTON_PREFIX}{request_id}",
        )
        approve_btn.callback = self.approve_callback
        self.add_item(approve_btn)

        decline_btn = ui.Button(
            label="❌ Decline",
            style=discord.ButtonStyle.danger,
            custom_id=f"{DECLINE_BUTTON_PREFIX}{request_id}",
        )
        decline_btn.callback = self.decline_callback
        self.add_item(decline_btn)

    async def approve_callback(self, interaction: discord.Interaction):
        await self.cog.handle_approve(interaction, self.request_id)

    async def decline_callback(self, interaction: discord.Interaction):
        await self.cog.handle_decline(interaction, self.request_id)


class DeclineReasonModal(ui.Modal, title="Decline Reason (Optional)"):
    """Modal for entering decline reason."""

    reason = ui.TextInput(
        label="Reason",
        placeholder="Why is this request being declined?",
        max_length=200,
        required=False,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, cog: "RequestsCog", request_id: int):
        super().__init__()
        self.cog = cog
        self.request_id = request_id

    async def on_submit(self, interaction: discord.Interaction):
        reason = str(self.reason.value).strip() or None
        await self.cog.complete_decline(interaction, self.request_id, reason)


# -----------------------------------------------------------------------------
# REQUESTS COG
# -----------------------------------------------------------------------------


class RequestsCog(commands.Cog):
    """
    Tournament Request Flow — UMS Bot Core Hero Feature C

    Approval-required workflow:
    1. Members submit requests via persistent button
    2. Requests stored in DB with status='pending'
    3. Admins review and approve/decline
    4. Approved requests create tournaments
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._pending_declines: dict[int, int] = {}  # request_id -> message_id

    @property
    def request_service(self):
        """Get request service from bot."""
        return self.bot.request_service

    @property
    def config_service(self):
        """Get config service from bot."""
        return self.bot.guild_config_service

    async def cog_load(self):
        """Register persistent views on load."""
        self.bot.add_view(RequestButtonView(self))
        log.info("[REQUESTS] Registered RequestButtonView")

        # Defer restoring review views until bot is ready
        # Using create_task to avoid blocking cog load (which would deadlock)
        import asyncio

        asyncio.create_task(self._restore_review_views())

    async def _restore_review_views(self):
        """Restore admin review views for pending requests on startup."""
        # Wait for bot to be ready before accessing guilds
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            try:
                pending = await self.request_service.get_pending_for_guild(guild.id)
                for req in pending:
                    if req.admin_message_id:
                        view = AdminReviewView(self, req.id)
                        self.bot.add_view(view)

                if pending:
                    log.info(
                        f"[REQUESTS] Restored {len(pending)} review views for {guild.name}"
                    )
            except Exception as e:
                log.error(f"[REQUESTS] Error restoring views for {guild.name}: {e}")

    # -------------------------------------------------------------------------
    # REQUEST FLOW
    # -------------------------------------------------------------------------

    async def start_request_flow(self, interaction: discord.Interaction):
        """Start the tournament request flow."""
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ This can only be used in a server.", ephemeral=True
            )

        # Check config exists
        config = await self.config_service.get(interaction.guild.id)
        if not config or not config.is_setup:
            return await interaction.response.send_message(
                "❌ Server not configured. An admin must run `/setup` first.",
                ephemeral=True,
            )

        # Check rate limit
        can_submit, reason = await self.request_service.check_rate_limit(
            interaction.user.id
        )
        if not can_submit:
            return await interaction.response.send_message(
                f"❌ {reason}", ephemeral=True
            )

        # Show request form
        view = RequestFormView(self)
        embed = discord.Embed(
            title="🏆 Request a Tournament",
            description=(
                "Select the tournament details below.\n\n"
                "**Note:** Your request will be reviewed by an admin before the tournament is created."
            ),
            color=discord.Color.blue(),
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def handle_request_submit(
        self,
        interaction: discord.Interaction,
        name: str,
        region: str,
        format: str,
        size: str,
        match_length: str,
        start_time: str,
    ):
        """Handle the final request submission."""
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return await interaction.followup.send(
                "❌ This can only be used in a server.", ephemeral=True
            )

        # Parse start time
        scheduled_start, time_display = parse_start_time(start_time)

        # Create request
        request, error = await self.request_service.create_request(
            guild_id=interaction.guild.id,
            requester_id=interaction.user.id,
            name=name,
            region=region,
            format=format,
            size=size,
            match_length=match_length,
            start_time=time_display,
            scheduled_start=scheduled_start,
        )

        if error:
            return await interaction.followup.send(f"❌ {error}", ephemeral=True)

        # Send to admin channel
        config = await self.config_service.get(interaction.guild.id)
        if config and config.admin_channel:
            admin_channel = interaction.guild.get_channel(config.admin_channel)
            if admin_channel and isinstance(admin_channel, discord.TextChannel):
                await self._send_admin_review(admin_channel, request, interaction.user)

        # Confirm to user
        await interaction.followup.send(
            f"✅ **Request Submitted!**\n\n"
            f"Your request for **{name}** has been submitted for admin review.\n"
            f"You'll receive a notification when it's approved or declined.",
            ephemeral=True,
        )

        log.info(
            f"[REQUESTS] Request #{request.id} submitted: '{name}' "
            f"by {interaction.user} in {interaction.guild.name}"
        )

    async def _send_admin_review(
        self,
        channel: discord.TextChannel,
        request,
        requester: discord.User,
    ):
        """Send review message to admin channel."""
        embed = discord.Embed(
            title="📋 Tournament Request",
            description=f"A new tournament request from {requester.mention}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow(),
        )

        embed.add_field(name="Name", value=request.name, inline=True)
        embed.add_field(name="Region", value=request.region or "Open", inline=True)
        embed.add_field(name="Format", value=request.format, inline=True)
        embed.add_field(name="Size", value=f"{request.size} players", inline=True)
        embed.add_field(
            name="Match Length", value=request.match_length or "Bo3", inline=True
        )
        embed.add_field(
            name="Start Time", value=request.start_time or "TBD", inline=True
        )

        embed.set_footer(text=f"Request ID: {request.id}")

        view = AdminReviewView(self, request.id)
        self.bot.add_view(view)  # Register for persistence

        message = await channel.send(embed=embed, view=view)

        # Store message ID
        await self.request_service.set_admin_message_id(request.id, message.id)

    # -------------------------------------------------------------------------
    # ADMIN ACTIONS
    # -------------------------------------------------------------------------

    async def _check_admin_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permission."""
        if not interaction.guild:
            return False

        # Check Discord admin permission
        if interaction.user.guild_permissions.administrator:
            return True

        # Check custom admin role
        config = await self.config_service.get(interaction.guild.id)
        if config and config.ums_admin_role:
            admin_role = interaction.guild.get_role(config.ums_admin_role)
            if admin_role and admin_role in interaction.user.roles:
                return True

        return False

    async def handle_approve(self, interaction: discord.Interaction, request_id: int):
        """Handle tournament approval."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Check permissions
            if not await self._check_admin_permission(interaction):
                return await interaction.followup.send(
                    "❌ You don't have permission to approve requests.",
                    ephemeral=True,
                )

            # Get request (checks pending status)
            request = await self.request_service.get_pending_by_id(request_id)
            if not request:
                await self._disable_review_buttons(interaction)
                return await interaction.followup.send(
                    "⚠️ This request has already been resolved.",
                    ephemeral=True,
                )

            # Generate tournament key
            tournament_key = f"t-{uuid.uuid4().hex[:8]}"

            # Approve request
            success, error = await self.request_service.approve_request(
                request_id=request_id,
                admin_id=interaction.user.id,
                tournament_key=tournament_key,
            )

            if not success:
                return await interaction.followup.send(f"❌ {error}", ephemeral=True)

            # Create tournament record
            await self._create_tournament(interaction.guild, request, tournament_key)

            # Post announcement
            config = await self.config_service.get(interaction.guild.id)
            if config and config.announce_channel:
                await self._post_announcement(
                    interaction.guild, request, config.announce_channel
                )

            # Update review message
            await self._disable_review_buttons(interaction)

            # Notify requester via DM
            try:
                requester = await self.bot.fetch_user(request.requester_id)
                await requester.send(
                    f"✅ Your tournament request **{request.name}** has been approved!\n"
                    f"Check the server for the announcement."
                )
            except Exception as e:
                log.debug(f"[REQUESTS] Could not DM requester: {e}")

            await interaction.followup.send(
                f"✅ Approved! Tournament **{request.name}** has been announced.",
                ephemeral=True,
            )

            log.info(f"[REQUESTS] Request #{request_id} approved by {interaction.user}")

        except Exception as e:
            log.error(f"[REQUESTS] Approve error: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while approving. Please try again.",
                ephemeral=True,
            )

    async def handle_decline(self, interaction: discord.Interaction, request_id: int):
        """Handle decline button - show reason modal."""
        # Check permissions
        if not await self._check_admin_permission(interaction):
            return await interaction.response.send_message(
                "❌ You don't have permission to decline requests.",
                ephemeral=True,
            )

        # Check request still pending
        request = await self.request_service.get_pending_by_id(request_id)
        if not request:
            await self._disable_review_buttons(interaction)
            return await interaction.response.send_message(
                "⚠️ This request has already been resolved.",
                ephemeral=True,
            )

        # Show decline reason modal
        modal = DeclineReasonModal(self, request_id)
        await interaction.response.send_modal(modal)

    async def complete_decline(
        self,
        interaction: discord.Interaction,
        request_id: int,
        reason: Optional[str],
    ):
        """Complete the decline after modal submission."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get request
            request = await self.request_service.get_pending_by_id(request_id)
            if not request:
                return await interaction.followup.send(
                    "⚠️ This request has already been resolved.",
                    ephemeral=True,
                )

            # Decline request
            success, error = await self.request_service.decline_request(
                request_id=request_id,
                admin_id=interaction.user.id,
                reason=reason,
            )

            if not success:
                return await interaction.followup.send(f"❌ {error}", ephemeral=True)

            # Clear requester's cooldown
            await self.request_service.clear_cooldown(request.requester_id)

            # Update review message
            if interaction.message:
                try:
                    embed = (
                        interaction.message.embeds[0]
                        if interaction.message.embeds
                        else None
                    )
                    if embed:
                        embed.color = discord.Color.red()
                        embed.title = "📋 Tournament Request — DECLINED"
                        if reason:
                            embed.add_field(name="Reason", value=reason, inline=False)
                        await interaction.message.edit(embed=embed, view=None)
                except:
                    pass

            # Notify requester via DM
            try:
                requester = await self.bot.fetch_user(request.requester_id)
                dm_msg = f"❌ Your tournament request **{request.name}** was declined."
                if reason:
                    dm_msg += f"\n\n**Reason:** {reason}"
                dm_msg += "\n\nYou may submit a new request."
                await requester.send(dm_msg)
            except Exception as e:
                log.debug(f"[REQUESTS] Could not DM requester: {e}")

            await interaction.followup.send(
                f"✅ Declined request **{request.name}**.",
                ephemeral=True,
            )

            log.info(
                f"[REQUESTS] Request #{request_id} declined by {interaction.user}"
                + (f" - {reason}" if reason else "")
            )

        except Exception as e:
            log.error(f"[REQUESTS] Decline error: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred. Please try again.",
                ephemeral=True,
            )

    async def _disable_review_buttons(self, interaction: discord.Interaction):
        """Disable buttons on the review message."""
        try:
            if interaction.message:
                await interaction.message.edit(view=None)
        except Exception as e:
            log.debug(f"[REQUESTS] Could not disable buttons: {e}")

    async def _create_tournament(self, guild, request, tournament_key: str):
        """Create a minimal tournament record."""
        try:
            await self.bot.db.execute(
                """
                INSERT INTO tournaments (
                    key, name, guild_id, organizer_id, region, format,
                    size, match_length, start_time, scheduled_start,
                    status, rank_restriction, region_restriction, request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'announced', ?, ?, ?)
                """,
                (
                    tournament_key,
                    request.name,
                    guild.id,
                    request.requester_id,
                    request.region,
                    request.format,
                    request.size,
                    request.match_length,
                    request.start_time,
                    request.scheduled_start,
                    request.rank_restriction,
                    request.region_restriction,
                    request.id,
                ),
            )
            await self.bot.db.commit()
            log.info(f"[REQUESTS] Created tournament: {tournament_key}")
        except Exception as e:
            log.error(f"[REQUESTS] Failed to create tournament: {e}")

    async def _post_announcement(self, guild: discord.Guild, request, channel_id: int):
        """Post tournament announcement to announce channel."""
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title=f"🏆 {request.name}",
            description="A new tournament has been announced!",
            color=discord.Color.green(),
        )

        embed.add_field(name="🌍 Region", value=request.region or "Open", inline=True)
        embed.add_field(name="🎮 Format", value=request.format, inline=True)
        embed.add_field(name="👥 Size", value=f"{request.size} players", inline=True)

        if request.start_time:
            embed.add_field(name="🕐 Start Time", value=request.start_time, inline=True)

        embed.set_footer(text="Registration details coming soon!")

        try:
            message = await channel.send(embed=embed)

            # Store announcement message ID
            await self.bot.db.execute(
                "UPDATE tournaments SET announce_message_id = ? WHERE request_id = ?",
                (message.id, request.id),
            )
            await self.bot.db.commit()
        except Exception as e:
            log.error(f"[REQUESTS] Failed to post announcement: {e}")

    # -------------------------------------------------------------------------
    # COMMANDS
    # -------------------------------------------------------------------------

    # NOTE: /post_request_panel is defined in cogs/server_setup.py to avoid
    # duplicate command registration. It uses the shared post_request_panel()
    # helper function which creates the same embed + RequestButtonView.

    @app_commands.command(
        name="pending_requests",
        description="View pending tournament requests (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def pending_requests(self, interaction: discord.Interaction):
        """List pending requests for this guild."""
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Use in a server.", ephemeral=True
            )

        pending = await self.request_service.get_pending_for_guild(interaction.guild.id)

        if not pending:
            return await interaction.response.send_message(
                "📭 No pending requests.", ephemeral=True
            )

        embed = discord.Embed(
            title="📋 Pending Tournament Requests",
            color=discord.Color.orange(),
        )

        for req in pending[:10]:  # Limit to 10
            requester = f"<@{req.requester_id}>"
            created = f"<t:{req.created_at}:R>" if req.created_at else "Unknown"
            embed.add_field(
                name=f"#{req.id}: {req.name}",
                value=f"By: {requester}\nCreated: {created}",
                inline=False,
            )

        if len(pending) > 10:
            embed.set_footer(text=f"Showing 10 of {len(pending)} requests")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RequestsCog(bot))
