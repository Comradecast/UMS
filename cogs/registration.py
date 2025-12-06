"""
cogs/registration.py — Tournament Registration Management for UMS Bot Core
===========================================================================
Manages tournament registration, infrastructure, and state.

Slash Commands:
- /registration_panel - Create a tournament
- /admin - Open admin dashboard
- /resync_panel - Resync admin panel after bot restart
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Dict, Optional, Tuple

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks
from services.status_helpers import is_tournament_open

import database
from config.dev_flags import is_dev_user
from utils.server_config import ServerConfigManager
from services.tournament_service import TournamentService

# Import UI components from ui/ package
from ui.registration_views import (
    RegisterButton,
    UnregisterButton,
    RefreshButton,
    RegionMismatchView,
    ManualRegisterModal,
    KickPlayerModal,
    AddDummiesModal,
    RegistrationView,
    EditTournamentModal,
    AdminControlsView,
)
from ui.registration_embeds import (
    build_public_registration_embed,
    build_admin_registration_embed,
    build_region_mismatch_embed,
)

log = logging.getLogger(__name__)


# NOTE(core-bot): Team/Queue button classes removed - TeamsCog, ClansCog, QuickQueueView not in core-bot
# Removed: CreateTeamButton, JoinTeamButton, SoloQueueButton, RegisterExistingTeamButton, TeamRegistrationView


class RegistrationCog(commands.Cog):
    """Manages tournament registration, infrastructure, and state."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ServerConfigManager()

        # State management
        self.tournaments: Dict[str, dict] = {}
        self.active_key: Optional[str] = None
        self.by_message_id: Dict[int, str] = {}

    async def _safe_create_role(self, guild: discord.Guild, **kwargs):
        """
        Create a role in a way that works both in real guilds and in tests.

        - In production: calls guild.create_role(**kwargs)
        - In tests (MockGuild without create_role): returns a dummy role object
        """
        create_role = getattr(guild, "create_role", None)
        name = kwargs.get("name", "Tournament Role")

        if create_role is None:
            # Test path: MockGuild has no create_role; return a dummy role
            class DummyRole:
                def __init__(self, name: str):
                    self.name = name
                    self.id = 0
                    self.mention = f"@{name}"

            log.debug("Mock guild without create_role; using DummyRole for %s", name)
            return DummyRole(name)

        # Normal Discord path
        return await create_role(**kwargs)

    async def _safe_create_category(self, guild: discord.Guild, **kwargs):
        """
        Create a category in a way that works both in real guilds and in tests.

        - In production: calls guild.create_category(**kwargs)
        - In tests (MockGuild without create_category): returns a dummy category
        """
        create_category = getattr(guild, "create_category", None)
        name = kwargs.get("name", "Tournament")

        if create_category is None:

            class DummyCategory:
                def __init__(self, name: str):
                    self.name = name
                    self.id = 0

            log.debug(
                "Mock guild without create_category; using DummyCategory for %s", name
            )
            return DummyCategory(name)

        return await create_category(**kwargs)

    async def _safe_create_text_channel(self, guild: discord.Guild, **kwargs):
        """
        Create a text channel in a way that works both in real guilds and in tests.

        - In production: calls guild.create_text_channel(**kwargs)
        - In tests (MockGuild without create_text_channel): returns a dummy channel
          with no-op send()/set_permissions so tests can still call these.
        """
        create_text_channel = getattr(guild, "create_text_channel", None)
        name = kwargs.get("name", "tournament-text")

        if create_text_channel is None:

            class DummyTextChannel:
                def __init__(self, name: str):
                    self.name = name
                    self.id = 0
                    self.mention = f"#{name}"
                    # add more attrs here later if tests/handlers need them
                    # e.g. self.category = None

                async def send(self, *args, **kwargs):
                    """No-op send for tests."""

                    class DummyMessage:
                        id = 0

                    return DummyMessage()

                async def set_permissions(self, *args, **kwargs):
                    """No-op set_permissions for tests."""
                    pass

            log.debug(
                "Mock guild without create_text_channel; using DummyTextChannel for %s",
                name,
            )
            return DummyTextChannel(name)

        return await create_text_channel(**kwargs)

    def _check_region_match(
        self, member: discord.Member, tournament_region: str
    ) -> Tuple[bool, list]:
        """Check if member has a role matching the tournament region."""
        if tournament_region.upper() == "OPEN":
            return True, []

        # Get player's region roles
        region_roles = []
        for role in member.roles:
            name = role.name.upper()
            if name in ["NA", "EU", "APAC", "OCE", "SA", "USE", "USW"]:
                region_roles.append(role.name)

        # Check if any region role matches tournament region
        tournament_regions = [r.strip().upper() for r in tournament_region.split(",")]
        for player_region in region_roles:
            if player_region.upper() in tournament_regions:
                return True, region_roles

        return False, region_roles

    async def cog_load(self):
        """Async setup called by bot."""
        await self.load_state()

        # Register persistent views
        self.bot.add_view(RegistrationView(self))
        self.bot.add_view(AdminControlsView(self, ""))  # Template for all admin panels

        # Start cleanup task
        if not self.cleanup_stale_tournaments.is_running():
            self.cleanup_stale_tournaments.start()

        log.info("[REGISTRATION] Cog loaded and persistent views registered")

    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.cleanup_stale_tournaments.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Ensure cleanup task is running."""
        if not self.cleanup_stale_tournaments.is_running():
            self.cleanup_stale_tournaments.start()

    @tasks.loop(hours=1)
    async def cleanup_stale_tournaments(self):
        """
        Clean up stale tournaments periodically.

        Uses the full delete_tournament() path so categories, channels, roles,
        and panel messages are all removed properly.
        """
        now = time.time()
        stale_threshold = 48 * 3600  # 48 hours

        to_delete = []
        for key, data in self.tournaments.items():
            created = data.get("created_at", 0)
            if now - created > stale_threshold:
                # Check if tournament is still active
                if not data.get("is_open", False):
                    to_delete.append(key)

        for key in to_delete:
            try:
                await self.delete_tournament(key)
                log.info(f"[CLEANUP] Deleted stale tournament: {key}")
            except Exception as e:
                log.error(f"[CLEANUP] Failed to delete {key}: {e}")

    @cleanup_stale_tournaments.before_loop
    async def before_cleanup(self):
        """Wait for bot to be ready before starting cleanup."""
        await self.bot.wait_until_ready()

    def get_state_by_message(self, message_id: int) -> Optional[dict]:
        """Helper to find tournament state by a message ID (public or admin)."""
        key = self.by_message_id.get(message_id)
        if key:
            return self.tournaments.get(key)

        # Fall back to scanning all tournaments
        for k, data in self.tournaments.items():
            if data.get("public_message_id") == message_id:
                return data
            if data.get("admin_message_id") == message_id:
                return data

        return None

    async def load_state(self):
        """Load tournament data from SQLite."""
        try:
            async with database.get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT key, name, region, format, size, start_time, is_open,
                           participants, role_id, category_id, channels,
                           public_channel_id, public_message_id,
                           admin_channel_id, admin_message_id,
                           requester_id, created_at, match_length,
                           rank_restriction, region_restriction, team_size
                    FROM registration_tournaments
                    """
                )
                rows = await cursor.fetchall()

                for row in rows:
                    import json

                    key = row[0]
                    self.tournaments[key] = {
                        "key": key,
                        "name": row[1],
                        "region": row[2],
                        "format": row[3],
                        "size": row[4],
                        "start_time": row[5],
                        "is_open": bool(row[6]),
                        "participants": set(json.loads(row[7] or "[]")),
                        "role_id": row[8],
                        "category_id": row[9],
                        "channels": json.loads(row[10] or "{}"),
                        "public_channel_id": row[11],
                        "public_message_id": row[12],
                        "admin_channel_id": row[13],
                        "admin_message_id": row[14],
                        "requester_id": row[15],
                        "created_at": row[16] or time.time(),
                        "match_length": row[17] or "Bo3",
                        "rank_restriction": row[18] or "",
                        "region_restriction": row[19] or "",
                        "team_size": row[20] or 1,
                    }

                    # Index by message IDs
                    if row[12]:
                        self.by_message_id[row[12]] = key
                    if row[14]:
                        self.by_message_id[row[14]] = key

                log.info(
                    f"[REGISTRATION] Loaded {len(self.tournaments)} tournaments from DB"
                )
        except Exception as e:
            log.error(f"[REGISTRATION] Failed to load state: {e}")

    async def save_tournament(self, key: str):
        """Save a specific tournament's state to DB."""
        data = self.tournaments.get(key)
        if not data:
            return

        try:
            import json

            async with database.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO registration_tournaments
                    (key, name, region, format, size, start_time, is_open,
                     participants, role_id, category_id, channels,
                     public_channel_id, public_message_id,
                     admin_channel_id, admin_message_id,
                     requester_id, created_at, match_length,
                     rank_restriction, region_restriction, team_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        data.get("name"),
                        data.get("region"),
                        data.get("format"),
                        data.get("size"),
                        data.get("start_time"),
                        int(data.get("is_open", False)),
                        json.dumps(list(data.get("participants", set()))),
                        data.get("role_id"),
                        data.get("category_id"),
                        json.dumps(data.get("channels", {})),
                        data.get("public_channel_id"),
                        data.get("public_message_id"),
                        data.get("admin_channel_id"),
                        data.get("admin_message_id"),
                        data.get("requester_id"),
                        data.get("created_at"),
                        data.get("match_length"),
                        data.get("rank_restriction"),
                        data.get("region_restriction"),
                        data.get("team_size"),
                    ),
                )
                await conn.commit()
        except Exception as e:
            log.error(f"[REGISTRATION] Failed to save tournament {key}: {e}")

    async def add_participant(
        self, key: str, user_id: int, member: Optional[discord.Member] = None
    ) -> bool:
        """Add a user to the tournament: update state, add role, update panels."""
        state = self.tournaments.get(key)
        if not state:
            return False

        participants = state.get("participants", set())
        if user_id in participants:
            return False  # Already registered

        participants.add(user_id)
        state["participants"] = participants

        # Add role if member provided
        if member and state.get("role_id"):
            try:
                role = member.guild.get_role(state["role_id"])
                if role:
                    await member.add_roles(role)
            except Exception as e:
                log.warning(f"[REGISTRATION] Failed to add role: {e}")

        await self.save_tournament(key)
        await self.update_public_panel(key)
        return True

    async def remove_participant(
        self, key: str, user_id: int, member: Optional[discord.Member] = None
    ) -> bool:
        """Remove a user: update state, remove role, update panels."""
        state = self.tournaments.get(key)
        if not state:
            return False

        participants = state.get("participants", set())
        if user_id not in participants:
            return False

        participants.discard(user_id)
        state["participants"] = participants

        # Remove role if member provided
        if member and state.get("role_id"):
            try:
                role = member.guild.get_role(state["role_id"])
                if role:
                    await member.remove_roles(role)
            except Exception as e:
                log.warning(f"[REGISTRATION] Failed to remove role: {e}")

        await self.save_tournament(key)
        await self.update_public_panel(key)
        return True

    def get_participants(self, key: str) -> list:
        """Get list of participant IDs."""
        state = self.tournaments.get(key)
        if not state:
            return []
        return list(state.get("participants", set()))

    async def setup_tournament(
        self,
        guild: discord.Guild,
        name: str,
        region: str,
        fmt: str,
        size: str,
        start_time: str,
        requester_id: int,
        match_length: str = "Bo3",
        rank_restriction: str = "",
        region_restriction: str = "",
        team_size: int = 1,
    ) -> Optional[str]:
        """
        Full provisioning: Role, Category, Channels, Admin Panel, Public Panel.
        Returns the tournament key on success, None on failure.
        """
        import uuid

        key = str(uuid.uuid4())[:8]

        try:
            # Create role
            role = await self._safe_create_role(
                guild,
                name=name,
                color=discord.Color.gold(),
                mentionable=True,
            )

            # Create category
            category = await self._safe_create_category(
                guild,
                name=f"Tournaments: {name}",
            )

            channels = {}

            async def create_channel(name, overwrites=None):
                ch = await self._safe_create_text_channel(
                    guild,
                    name=name,
                    category=category,
                    overwrites=overwrites,
                )
                return ch

            # Create channels
            reg_channel = await create_channel("registration")
            admin_channel = await create_channel("temp-admin")
            match_chat = await create_channel("match-chat")
            results_channel = await create_channel("results")
            standings_channel = await create_channel("standings")
            submit_score = await create_channel("submit-score")

            channels["registration"] = reg_channel.id
            channels["temp_admin"] = admin_channel.id
            channels["match_chat"] = match_chat.id
            channels["results"] = results_channel.id
            channels["standings"] = standings_channel.id
            channels["submit_score"] = submit_score.id

            # Initialize tournament state
            self.tournaments[key] = {
                "key": key,
                "name": name,
                "region": region,
                "format": fmt,
                "size": size,
                "start_time": start_time,
                "is_open": True,
                "participants": set(),
                "role_id": role.id,
                "category_id": category.id,
                "channels": channels,
                "public_channel_id": reg_channel.id,
                "public_message_id": None,
                "admin_channel_id": admin_channel.id,
                "admin_message_id": None,
                "requester_id": requester_id,
                "created_at": time.time(),
                "match_length": match_length,
                "rank_restriction": rank_restriction,
                "region_restriction": region_restriction,
                "team_size": team_size,
            }

            state = self.tournaments[key]

            # Post public registration panel
            embed = build_public_registration_embed(state)
            view = RegistrationView(self, tournament_key=key, is_open=True)
            public_msg = await reg_channel.send(embed=embed, view=view)
            state["public_message_id"] = public_msg.id
            self.by_message_id[public_msg.id] = key

            # Post admin panel
            admin_embed = build_admin_registration_embed(state)
            admin_view = AdminControlsView(self, key)
            admin_msg = await admin_channel.send(embed=admin_embed, view=admin_view)
            state["admin_message_id"] = admin_msg.id
            self.by_message_id[admin_msg.id] = key

            # Save to DB
            await self.save_tournament(key)

            log.info(f"[REGISTRATION] Created tournament {key}: {name}")
            return key

        except Exception as e:
            log.error(f"[REGISTRATION] Failed to setup tournament: {e}", exc_info=True)
            return None

    async def delete_tournament(self, key: str):
        """Delete tournament and clean up ALL resources."""
        state = self.tournaments.get(key)
        if not state:
            return

        guild_id = None

        # Delete channels and category
        if state.get("category_id"):
            for g in self.bot.guilds:
                cat = g.get_channel(state["category_id"])
                if cat:
                    guild_id = g.id
                    # Delete all channels in category
                    for ch in cat.channels:
                        try:
                            await ch.delete(reason="Tournament deleted")
                        except Exception as e:
                            log.warning(f"Failed to delete channel {ch.name}: {e}")
                    # Delete category
                    try:
                        await cat.delete(reason="Tournament deleted")
                    except Exception as e:
                        log.warning(f"Failed to delete category: {e}")
                    break

        # Delete role
        if state.get("role_id") and guild_id:
            for g in self.bot.guilds:
                if g.id == guild_id:
                    role = g.get_role(state["role_id"])
                    if role:
                        try:
                            await role.delete(reason="Tournament deleted")
                        except Exception as e:
                            log.warning(f"Failed to delete role: {e}")
                    break

        # Remove from state
        self.tournaments.pop(key, None)

        # Remove message ID mappings
        for msg_id, k in list(self.by_message_id.items()):
            if k == key:
                del self.by_message_id[msg_id]

        # Delete from DB
        try:
            async with database.get_connection() as conn:
                await conn.execute(
                    "DELETE FROM registration_tournaments WHERE key = ?",
                    (key,),
                )
                await conn.commit()
        except Exception as e:
            log.error(f"[REGISTRATION] Failed to delete tournament from DB: {e}")

        log.info(f"[REGISTRATION] Deleted tournament {key}")

    async def update_organizer_interaction(self, key: str, user_id: int):
        """Update the last interaction timestamp for the tournament organizer."""
        state = self.tournaments.get(key)
        if state:
            organizer_id = state.get("requester_id")

            # Only update if it's the organizer interacting
            if organizer_id and user_id == organizer_id:
                state["organizer_last_interaction"] = int(time.time())

                # If tournament was auto-started, mark that organizer has returned
                if state.get("auto_started", False):
                    state["organizer_returned"] = True

                # We don't strictly need to save this to DB every time as it's transient state for abandonment check
                # But if we want persistence across restarts for abandonment logic, we should.
                # For now, I'll skip DB update for performance, unless it's the "returned" flag.
                if state.get("organizer_returned"):
                    await self.save_tournament(key)

                log.info(f"Updated organizer interaction for {key}")

    def _public_embed(self, state: dict) -> discord.Embed:
        """Create a public embed from tournament state."""
        return build_public_registration_embed(state)

    def _admin_embed(self, state: dict) -> discord.Embed:
        """Create an admin embed from tournament state."""
        return build_admin_registration_embed(state)

    async def update_public_panel(self, key: str) -> None:
        """Update the public panel with current state."""
        state = self.tournaments.get(key)
        if not state:
            return

        try:
            channel = self.bot.get_channel(state.get("public_channel_id"))
            if not channel:
                return
            msg = await channel.fetch_message(state.get("public_message_id"))

            embed = self._public_embed(state)

            # core-bot: team registration UI removed; always use player-level registration
            view = RegistrationView(self, tournament_key=key, is_open=state["is_open"])

            await msg.edit(embed=embed, view=view)

            # Also update Admin Panel
            admin_ch = self.bot.get_channel(state.get("admin_channel_id"))
            if admin_ch:
                admin_msg = await admin_ch.fetch_message(state.get("admin_message_id"))
                admin_embed = self._admin_embed(state)
                admin_view = AdminControlsView(self, key)
                await admin_msg.edit(embed=admin_embed, view=admin_view)

        except Exception as e:
            log.error(f"Error updating panels: {e}")

    async def set_registration_open(self, key: str, is_open: bool) -> None:
        st = self.tournaments.get(key)
        if not st:
            return
        st["is_open"] = bool(is_open)
        await self.save_tournament(key)
        await self.update_public_panel(key)

    # Slash command to manually post a registration panel (useful for testing)
    @app_commands.command(
        name="registration_panel", description="Manually create a tournament"
    )
    async def registration_panel(
        self,
        inter: discord.Interaction,
        name: str,
        region: str,
        fmt: str,
        size: str,
        start_time: str,
    ):
        await inter.response.defer(ephemeral=True)

        key = await self.setup_tournament(
            guild=inter.guild,
            name=name,
            region=region,
            fmt=fmt,
            size=size,
            start_time=start_time,
            requester_id=inter.user.id,
        )

        if key:
            await inter.followup.send(
                f"Tournament '{name}' created! Check the new category.", ephemeral=True
            )
        else:
            await inter.followup.send(
                "Failed to create tournament. Check logs/permissions.", ephemeral=True
            )

    async def end_tournament(self, inter: discord.Interaction, key: str):
        """End the tournament, lock channels, and archive."""
        data = self.tournaments.get(key)
        if not data:
            return await inter.followup.send("Tournament not found.", ephemeral=True)

        guild = inter.guild
        channels = data.get("channels", {}) or {}

        # --- helper to be test-friendly ---
        def _get_channel(channel_id: int | None):
            """Safely get a channel from a guild; returns None on MockGuilds without get_channel."""
            if not guild or not channel_id:
                return None
            get_ch = getattr(guild, "get_channel", None)
            if callable(get_ch):
                try:
                    return get_ch(channel_id)
                except Exception:
                    return None
            # MockGuild path: no get_channel; we just skip channel operations
            return None

        # 1. Lock / cleanup channels

        # Delete submit-score
        submit_score_id = channels.get("submit_score")
        if submit_score_id:
            ch = _get_channel(submit_score_id)
            if ch is not None and hasattr(ch, "delete"):
                try:
                    await ch.delete(reason="Tournament Ended")
                except Exception as e:
                    log.warning(
                        f"Failed to delete submit-score channel {submit_score_id}: {e}"
                    )

        # Lock match-chat (read only) – test-friendly
        match_chat_id = channels.get("match_chat")
        if match_chat_id:
            ch = _get_channel(match_chat_id)
            if ch:
                default_role = getattr(guild, "default_role", None)

                if default_role is not None and hasattr(ch, "set_permissions"):
                    try:
                        await ch.set_permissions(default_role, send_messages=False)
                    except Exception as e:
                        log.warning(f"Failed to lock match-chat {match_chat_id}: {e}")

                if hasattr(ch, "send"):
                    try:
                        await ch.send(
                            "🛑 **Tournament Ended!** This channel is now read-only."
                        )
                    except Exception as e:
                        log.warning(
                            f"Failed to send end notice in match-chat {match_chat_id}: {e}"
                        )

        # 2. Get results from appropriate cog based on format
        tournament_format = data.get("format", "Single Elimination")

        if "Double Elimination" in tournament_format:
            de_cog = self.bot.get_cog("DoubleEliminationCog")
            results = de_cog.get_results(key) if de_cog else {}
        else:
            bracket_cog = self.bot.get_cog("BracketCog")
            results = bracket_cog.get_results(key) if bracket_cog else {}

        # Check for abandonment (Auto-started + Auto-concluded + No organizer return + Admin ending it)
        requester_id = data.get("requester_id")

        if (
            data.get("auto_started")
            and data.get("auto_concluded")
            and not data.get("organizer_returned")
            and requester_id
            and inter.user.id != requester_id
        ):
            # Admin is cleaning up an abandoned tournament
            req_cog = self.bot.get_cog("RequestsCog")
            if req_cog:
                req_cog.organizer_mgr.ban_user(
                    requester_id,
                    "Abandoned tournament (auto-started and never returned)",
                    data.get("name", "Unknown"),
                    key,
                )
                await inter.followup.send(
                    f"🚫 **Organizer Banned**: <@{requester_id}> for abandoning the tournament.",
                    ephemeral=True,
                )
                log.warning(
                    f"Banned user {requester_id} for abandoning tournament {key}"
                )

        winner_id_raw = results.get("winner_id")
        runner_up_id_raw = results.get("runner_up_id")

        # Normalize to ints where possible (so we can check for dummy IDs)
        try:
            winner_id = int(winner_id_raw) if winner_id_raw is not None else None
        except (TypeError, ValueError):
            winner_id = None

        try:
            runner_up_id = (
                int(runner_up_id_raw) if runner_up_id_raw is not None else None
            )
        except (TypeError, ValueError):
            runner_up_id = None

        embed = discord.Embed(
            title=f"🏆 Tournament Results: {data['name']}",
            color=discord.Color.gold(),
        )

        # Champion field
        if winner_id is not None:
            if winner_id < 0:
                winner_text = f"Dummy {abs(winner_id)}"
            else:
                winner_text = f"<@{winner_id}>"
            embed.add_field(name="🥇 Champion", value=winner_text, inline=False)

        # Runner-up field
        if runner_up_id is not None:
            if runner_up_id < 0:
                runner_text = f"Dummy {abs(runner_up_id)}"
            else:
                runner_text = f"<@{runner_up_id}>"
            embed.add_field(name="🥈 Runner Up", value=runner_text, inline=False)

        embed.set_footer(
            text=f"Format: {data.get('format')} | Region: {data.get('region')}"
        )
        embed.timestamp = discord.utils.utcnow()

        # Generate final bracket image (for SE tournaments only)
        bracket_file = None
        tournament_format = data.get("format", "Single Elimination")
        if "Double Elimination" not in tournament_format:
            try:
                from services.bracket_snapshot import get_bracket_snapshot
                from services.bracket_render_service import get_bracket_render_service

                snapshot = await get_bracket_snapshot(self.bot, key, data)
                if snapshot:
                    render_service = get_bracket_render_service()
                    image_bytes = render_service.render_bracket(snapshot)
                    if image_bytes:
                        import io

                        bracket_file = discord.File(
                            io.BytesIO(image_bytes), filename="final_bracket.png"
                        )
                        # Attach the image to the embed
                        embed.set_image(url="attachment://final_bracket.png")
                        log.info(f"Generated final bracket image for {key}")
            except ImportError as e:
                log.warning(f"Bracket rendering unavailable for final results: {e}")
            except Exception as e:
                log.error(f"Failed to generate final bracket image: {e}", exc_info=True)

        # 3. Post to local tournament results channel
        local_results_id = channels.get("results")
        if local_results_id:
            ch = _get_channel(local_results_id)
            if ch is not None and hasattr(ch, "send"):
                try:
                    if bracket_file:
                        # Need to recreate file for each send (can't reuse)
                        import io
                        from services.bracket_snapshot import get_bracket_snapshot
                        from services.bracket_render_service import (
                            get_bracket_render_service,
                        )

                        snapshot = await get_bracket_snapshot(self.bot, key, data)
                        if snapshot:
                            render_service = get_bracket_render_service()
                            image_bytes = render_service.render_bracket(snapshot)
                            if image_bytes:
                                local_file = discord.File(
                                    io.BytesIO(image_bytes),
                                    filename="final_bracket.png",
                                )
                                await ch.send(embed=embed, file=local_file)
                            else:
                                await ch.send(embed=embed)
                        else:
                            await ch.send(embed=embed)
                    else:
                        await ch.send(embed=embed)
                except Exception as e:
                    log.warning(
                        f"Failed to send local results in channel {local_results_id}: {e}"
                    )

        # 4. Post to CENTRAL results channel (only if different from local)
        central_results_id = (
            await self.config.get_channel_id(guild.id, "results") if guild else None
        )
        if central_results_id:
            try:
                central_id = int(central_results_id)
                if central_id != local_results_id:
                    central_ch = _get_channel(central_id)
                    if central_ch is not None and hasattr(central_ch, "send"):
                        # Regenerate file for central channel
                        if bracket_file:
                            try:
                                import io
                                from services.bracket_snapshot import (
                                    get_bracket_snapshot,
                                )
                                from services.bracket_render_service import (
                                    get_bracket_render_service,
                                )

                                snapshot = await get_bracket_snapshot(
                                    self.bot, key, data
                                )
                                if snapshot:
                                    render_service = get_bracket_render_service()
                                    image_bytes = render_service.render_bracket(
                                        snapshot
                                    )
                                    if image_bytes:
                                        central_file = discord.File(
                                            io.BytesIO(image_bytes),
                                            filename="final_bracket.png",
                                        )
                                        await central_ch.send(
                                            embed=embed, file=central_file
                                        )
                                    else:
                                        await central_ch.send(embed=embed)
                                else:
                                    await central_ch.send(embed=embed)
                            except Exception:
                                await central_ch.send(embed=embed)
                        else:
                            await central_ch.send(embed=embed)
            except Exception as e:
                log.error(f"Failed to post to central results: {e}")

        await inter.followup.send(
            "✅ Tournament ended and results published.", ephemeral=True
        )

    async def reset_tournament(self, inter: discord.Interaction, key: str):
        """Reset the bracket and reopen registration."""
        bracket_cog = self.bot.get_cog("BracketCog")
        if bracket_cog:
            bracket_cog.clear_bracket(key)

        # Re-open registration
        await self.set_registration_open(key, True)

        # Clear standings channel
        data = self.tournaments.get(key)
        if data and "channels" in data:
            standings_id = data["channels"].get("standings")
            if standings_id:
                ch = inter.guild.get_channel(standings_id)
                if ch:
                    await ch.purge(limit=100)

        await inter.followup.send(
            "🔄 Tournament reset! Bracket cleared, registration reopened.",
            ephemeral=True,
        )

    @app_commands.command(
        name="admin", description="Open the Tournament Admin Dashboard"
    )
    async def admin_panel(self, inter: discord.Interaction):
        """Open the ephemeral admin dashboard."""
        if not inter.user.guild_permissions.administrator:
            return await inter.response.send_message("❌ Admin only.", ephemeral=True)

        if not self.tournaments:
            return await inter.response.send_message(
                "❌ No tournaments found.", ephemeral=True
            )

        # Just grab the first key for now
        key = list(self.tournaments.keys())[0]
        data = self.tournaments[key]

        embed = discord.Embed(
            title=f"Admin Dashboard: {data['name']}", color=discord.Color.dark_grey()
        )
        embed.add_field(
            name="Status", value="Active" if data.get("is_open") else "Closed/Ended"
        )
        embed.add_field(
            name="Participants", value=str(len(data.get("participants", [])))
        )

        view = AdminControlsView(self, key)
        await inter.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="resync_panel")
    @app_commands.describe(tournament_key="Tournament key to resync")
    @app_commands.default_permissions(administrator=True)
    async def resync_panel(self, interaction: discord.Interaction, tournament_key: str):
        """Re-post the admin panel for a tournament (fixes 'interaction failed' after bot restart)."""
        await interaction.response.defer(ephemeral=True)

        # Get tournament
        state = self.tournaments.get(tournament_key)
        if not state:
            return await interaction.followup.send(
                f"❌ Tournament `{tournament_key}` not found.", ephemeral=True
            )

        # Get temp-admin channel
        admin_channel_id = state.get("admin_channel_id") or state.get(
            "channels", {}
        ).get("temp_admin")
        if not admin_channel_id:
            return await interaction.followup.send(
                "❌ Admin channel not found for this tournament.", ephemeral=True
            )

        admin_channel = interaction.guild.get_channel(admin_channel_id)
        if not admin_channel:
            return await interaction.followup.send(
                f"❌ Admin channel {admin_channel_id} not found.", ephemeral=True
            )

        # Delete old message if it exists
        old_msg_id = state.get("admin_message_id")
        if old_msg_id:
            try:
                old_msg = await admin_channel.fetch_message(old_msg_id)
                await old_msg.delete()
            except:
                pass  # Message already gone, that's fine

        # Post new admin panel
        embed = self._admin_embed(state)
        view = AdminControlsView(self, tournament_key)
        msg = await admin_channel.send(embed=embed, view=view)

        # Update state
        state["admin_message_id"] = msg.id
        self.by_message_id[msg.id] = tournament_key
        if old_msg_id and old_msg_id in self.by_message_id:
            del self.by_message_id[old_msg_id]

        await self.save_tournament(tournament_key)

        await interaction.followup.send(
            f"✅ Re-synced admin panel for `{tournament_key}`\n"
            f"New panel posted in <#{admin_channel.id}>",
            ephemeral=True,
        )

        log.info(f"Re-synced admin panel for {tournament_key}")


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot))
