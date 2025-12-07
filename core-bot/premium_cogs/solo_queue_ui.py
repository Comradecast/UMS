"""
premium_cogs/solo_queue_ui.py — Premium Solo Queue UI Cog

Thin UI layer over the UMS Premium Service backend.
All business logic (Elo, matchmaking, match lifecycle) lives in the backend.
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from premium_cogs.premium_client import PremiumClient, PremiumAPIError

log = logging.getLogger(__name__)


class PremiumMatchResultView(discord.ui.View):
    """View for reporting Premium match results.

    Shows I Won / Opponent Won / Cancel buttons.
    All actions route through the Premium API.
    """

    def __init__(
        self,
        client: PremiumClient,
        match_id: int,
        player1_id: int,
        player2_id: int,
    ):
        super().__init__(timeout=None)
        self.client = client
        self.match_id = match_id
        self.player1_id = player1_id
        self.player2_id = player2_id

    def _get_opponent_id(self, user_id: int) -> int:
        """Get the opponent's Discord ID."""
        if user_id == self.player1_id:
            return self.player2_id
        return self.player1_id

    def _get_team(self, user_id: int) -> int:
        """Get the team number for a user (1 or 2)."""
        return 1 if user_id == self.player1_id else 2

    @discord.ui.button(
        label="I Won",
        style=discord.ButtonStyle.success,
        custom_id="premium_match:i_won",
        emoji="🏆",
    )
    async def i_won(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Player reports they won."""
        await self._report_result(interaction, self._get_team(interaction.user.id))

    @discord.ui.button(
        label="Opponent Won",
        style=discord.ButtonStyle.danger,
        custom_id="premium_match:opponent_won",
        emoji="🤝",
    )
    async def opponent_won(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Player reports opponent won."""
        opponent_team = 3 - self._get_team(interaction.user.id)  # Flip 1↔2
        await self._report_result(interaction, opponent_team)

    async def _report_result(
        self, interaction: discord.Interaction, winner_team: int
    ):
        """Handle result reporting via Premium API."""
        user_id = interaction.user.id

        # Verify user is in this match
        if user_id not in (self.player1_id, self.player2_id):
            return await interaction.response.send_message(
                "❌ You're not a participant in this match.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.client.report_match_result(
                match_id=self.match_id,
                winner_team=winner_team,
                team1_score=1,  # Simple 1-0 for now
                team2_score=0,
            )

            # Disable buttons after report
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            winner_text = "You" if winner_team == self._get_team(user_id) else "Your opponent"
            await interaction.followup.send(
                f"✅ Match result recorded: **{winner_text} won!**\n"
                f"Match ID: {self.match_id}",
                ephemeral=True,
            )

        except PremiumAPIError as e:
            log.error(f"[PREMIUM-UI] Report result failed: {e}")
            await interaction.followup.send(
                f"❌ Failed to report result: {e.message}",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Cancel Match",
        style=discord.ButtonStyle.secondary,
        custom_id="premium_match:cancel",
        emoji="❌",
    )
    async def cancel_match(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Cancel the match without Elo changes."""
        user_id = interaction.user.id

        if user_id not in (self.player1_id, self.player2_id):
            return await interaction.response.send_message(
                "❌ You're not a participant in this match.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        try:
            await self.client.cancel_match(
                match_id=self.match_id,
                reason="Cancelled by player",
            )

            # Disable buttons
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

            await interaction.followup.send(
                "✅ Match cancelled. No rating changes applied.",
                ephemeral=True,
            )

        except PremiumAPIError as e:
            log.error(f"[PREMIUM-UI] Cancel match failed: {e}")
            await interaction.followup.send(
                f"❌ Failed to cancel match: {e.message}",
                ephemeral=True,
            )


class PremiumSoloQueuePanelView(discord.ui.View):
    """Persistent view for the Premium Solo Queue panel.

    Shows Join/Leave buttons. All queue logic goes through Premium API.
    """

    def __init__(self, cog: "PremiumSoloQueueCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Join 1v1 Ranked",
        style=discord.ButtonStyle.primary,
        custom_id="premium_queue:join_1v1_ranked",
        emoji="⚔️",
        row=0,
    )
    async def join_1v1_ranked(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Join the 1v1 ranked queue."""
        await self._join_queue(interaction, "1v1_ranked")

    @discord.ui.button(
        label="Join 2v2 Ranked",
        style=discord.ButtonStyle.primary,
        custom_id="premium_queue:join_2v2_ranked",
        emoji="👥",
        row=0,
    )
    async def join_2v2_ranked(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Join the 2v2 ranked queue."""
        await self._join_queue(interaction, "2v2_ranked")

    @discord.ui.button(
        label="Leave Queue",
        style=discord.ButtonStyle.secondary,
        custom_id="premium_queue:leave",
        emoji="🚪",
        row=1,
    )
    async def leave_queue(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Leave all queues."""
        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.cog.client.leave_queue(
                discord_id=interaction.user.id,
                guild_id=interaction.guild_id,
            )

            if result.get("success"):
                await interaction.followup.send(
                    "✅ You have left the queue.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "ℹ️ You weren't in any queue.",
                    ephemeral=True,
                )

        except PremiumAPIError as e:
            log.error(f"[PREMIUM-UI] Leave queue failed: {e}")
            await interaction.followup.send(
                f"❌ Failed to leave queue: {e.message}",
                ephemeral=True,
            )

    @discord.ui.button(
        label="My Status",
        style=discord.ButtonStyle.secondary,
        custom_id="premium_queue:status",
        emoji="📊",
        row=1,
    )
    async def check_status(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Check queue and match status."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Check queue status
            queue_status = await self.cog.client.get_queue_status(
                discord_id=interaction.user.id,
                guild_id=interaction.guild_id,
            )

            # Check active match
            active_match = await self.cog.client.get_active_match(
                discord_id=interaction.user.id,
            )

            lines = []

            if active_match:
                lines.append(f"🎮 **Active Match:** ID {active_match.get('id')}")
                lines.append(f"   Mode: {active_match.get('mode')}")
                lines.append(f"   Status: {active_match.get('status')}")
            elif queue_status.get("in_queue"):
                queues = queue_status.get("queues", [])
                for q in queues:
                    lines.append(
                        f"⏳ **{q['queue_type']}:** Position #{q['position']}"
                    )
            else:
                lines.append("📭 You're not in any queue or match.")

            # Get player stats
            player = await self.cog.client.get_or_create_player(interaction.user.id)
            lines.append("")
            lines.append(f"📈 **Your Ratings:**")
            lines.append(f"   1v1: {player.get('elo_1v1', 1200)}")
            lines.append(f"   2v2: {player.get('elo_2v2', 1200)}")
            lines.append(f"   3v3: {player.get('elo_3v3', 1200)}")

            await interaction.followup.send("\n".join(lines), ephemeral=True)

        except PremiumAPIError as e:
            log.error(f"[PREMIUM-UI] Status check failed: {e}")
            await interaction.followup.send(
                f"❌ Failed to get status: {e.message}",
                ephemeral=True,
            )

    async def _join_queue(self, interaction: discord.Interaction, queue_type: str):
        """Helper to join a queue via Premium API."""
        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.cog.client.join_queue(
                discord_id=interaction.user.id,
                guild_id=interaction.guild_id,
                queue_type=queue_type,
            )

            status = result.get("status")
            position = result.get("position")
            message = result.get("message", "")

            if status == "ok":
                await interaction.followup.send(
                    f"✅ **Joined {queue_type}!** Position: #{position}\n"
                    f"Waiting for opponent...",
                    ephemeral=True,
                )
            elif status == "already_in_queue":
                await interaction.followup.send(
                    f"ℹ️ Already in queue at position #{position}.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"⚠️ {message}",
                    ephemeral=True,
                )

        except PremiumAPIError as e:
            log.error(f"[PREMIUM-UI] Join queue failed: {e}")
            await interaction.followup.send(
                f"❌ Failed to join queue: {e.message}",
                ephemeral=True,
            )


class PremiumSoloQueueCog(commands.Cog):
    """Premium Solo Queue UI Cog.

    Provides the slash command to post the Premium Solo Queue panel
    and handles the background matchmaking tick.
    """

    def __init__(self, bot: commands.Bot, client: PremiumClient):
        self.bot = bot
        self.client = client
        self._panel_channel_id: Optional[int] = None
        self._panel_message_id: Optional[int] = None

    async def cog_load(self):
        """Called when the cog is loaded."""
        # Register persistent views
        self.bot.add_view(PremiumSoloQueuePanelView(self))
        log.info("[PREMIUM-UI] Solo Queue cog loaded")

    async def cog_unload(self):
        """Called when the cog is unloaded."""
        self.matchmaking_loop.cancel()
        log.info("[PREMIUM-UI] Solo Queue cog unloaded")

    @app_commands.command(
        name="premium_post_solo_panel",
        description="Post the Premium Solo Queue panel to this channel",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def post_solo_panel(self, interaction: discord.Interaction):
        """Post the Premium Solo Queue panel.

        Admin-only command that posts the queue panel with Join/Leave buttons.
        """
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="⚔️ Premium Solo Queue",
            description=(
                "Join a ranked queue to find opponents!\n\n"
                "**How it works:**\n"
                "1. Click a Join button to enter a queue\n"
                "2. Wait for matchmaking to find you an opponent\n"
                "3. When matched, report the result using the buttons\n"
                "4. Your rating updates based on the outcome\n\n"
                "**Buttons:**\n"
                "• **Join 1v1/2v2** - Enter the ranked queue\n"
                "• **Leave Queue** - Exit the queue\n"
                "• **My Status** - Check your position and rating"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Powered by UMS Premium Service")

        view = PremiumSoloQueuePanelView(self)

        try:
            message = await interaction.channel.send(embed=embed, view=view)
            self._panel_channel_id = interaction.channel_id
            self._panel_message_id = message.id

            await interaction.followup.send(
                "✅ Premium Solo Queue panel posted!",
                ephemeral=True,
            )
            log.info(
                f"[PREMIUM-UI] Panel posted in channel {interaction.channel_id} "
                f"by {interaction.user}"
            )

        except discord.HTTPException as e:
            log.error(f"[PREMIUM-UI] Failed to post panel: {e}")
            await interaction.followup.send(
                f"❌ Failed to post panel: {e}",
                ephemeral=True,
            )

    @app_commands.command(
        name="premium_matchmaking_tick",
        description="(Dev) Run a matchmaking tick for a queue",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        queue_type="Queue type to process (e.g., 1v1_ranked)",
        elo_range="Maximum Elo difference for matching",
    )
    async def manual_matchmaking_tick(
        self,
        interaction: discord.Interaction,
        queue_type: str = "1v1_ranked",
        elo_range: int = 300,
    ):
        """Manually run a matchmaking tick.

        Dev/admin command to trigger matchmaking for a queue.
        """
        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.client.matchmaking_tick(
                guild_id=interaction.guild_id,
                queue_type=queue_type,
                elo_range=elo_range,
            )

            matches_created = result.get("matches_created", 0)
            matches = result.get("matches", [])

            if matches_created == 0:
                await interaction.followup.send(
                    f"ℹ️ No matches created. Queue may be empty or no valid pairs found.\n"
                    f"Queue: `{queue_type}`, Elo range: ±{elo_range}",
                    ephemeral=True,
                )
            else:
                lines = [f"✅ Created **{matches_created}** match(es):\n"]
                for m in matches:
                    lines.append(
                        f"• Match {m['match_id']}: "
                        f"<@{m['player1_discord_id']}> ({m['player1_elo']}) vs "
                        f"<@{m['player2_discord_id']}> ({m['player2_elo']})"
                    )

                await interaction.followup.send("\n".join(lines), ephemeral=True)

                # Post match result views for each match
                for m in matches:
                    await self._post_match_panel(
                        interaction.channel,
                        m["match_id"],
                        m["player1_discord_id"],
                        m["player2_discord_id"],
                        m["player1_elo"],
                        m["player2_elo"],
                    )

        except PremiumAPIError as e:
            log.error(f"[PREMIUM-UI] Matchmaking tick failed: {e}")
            await interaction.followup.send(
                f"❌ Matchmaking failed: {e.message}",
                ephemeral=True,
            )

    async def _post_match_panel(
        self,
        channel: discord.TextChannel,
        match_id: int,
        player1_id: int,
        player2_id: int,
        player1_elo: int,
        player2_elo: int,
    ):
        """Post a match result panel for a created match."""
        embed = discord.Embed(
            title="🎮 Match Created!",
            description=(
                f"**Match ID:** {match_id}\n\n"
                f"<@{player1_id}> ({player1_elo}) vs <@{player2_id}> ({player2_elo})\n\n"
                "Report the result when done:"
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Report honestly. False reports may be penalized.")

        view = PremiumMatchResultView(self.client, match_id, player1_id, player2_id)

        try:
            await channel.send(
                content=f"<@{player1_id}> <@{player2_id}>",
                embed=embed,
                view=view,
            )
        except discord.HTTPException as e:
            log.error(f"[PREMIUM-UI] Failed to post match panel: {e}")

    @tasks.loop(seconds=15)
    async def matchmaking_loop(self):
        """Background matchmaking tick (runs every 15 seconds)."""
        # Only run if we have a panel posted
        if not self._panel_channel_id:
            return

        try:
            channel = self.bot.get_channel(self._panel_channel_id)
            if not channel:
                return

            guild_id = channel.guild.id

            # Run tick for 1v1 ranked
            result = await self.client.matchmaking_tick(
                guild_id=guild_id,
                queue_type="1v1_ranked",
                elo_range=300,
            )

            matches = result.get("matches", [])
            for m in matches:
                await self._post_match_panel(
                    channel,
                    m["match_id"],
                    m["player1_discord_id"],
                    m["player2_discord_id"],
                    m["player1_elo"],
                    m["player2_elo"],
                )

        except PremiumAPIError as e:
            log.debug(f"[PREMIUM-UI] Background tick error: {e}")
        except Exception as e:
            log.error(f"[PREMIUM-UI] Background tick error: {e}", exc_info=True)

    @matchmaking_loop.before_loop
    async def before_matchmaking_loop(self):
        """Wait for bot to be ready before starting loop."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    """Setup function for loading the cog.

    Note: This requires bot.premium_client to be set before loading.
    """
    if not hasattr(bot, "premium_client"):
        log.error("[PREMIUM-UI] bot.premium_client not set - cannot load cog")
        raise RuntimeError("PremiumClient not initialized")

    await bot.add_cog(PremiumSoloQueueCog(bot, bot.premium_client))
