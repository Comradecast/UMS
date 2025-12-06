"""
ui/registration_views.py — Tournament Registration Views
========================================================
Registration buttons, modals, and views for tournament registration.
Includes both player-facing and admin controls.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Optional, TYPE_CHECKING

import discord
from discord import ui

from config.dev_flags import is_dev_user
from ui.registration_embeds import build_region_mismatch_embed

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# PLAYER-FACING BUTTONS (Persistent)
# -----------------------------------------------------------------------------


class RegisterButton(ui.Button):
    """Button for players to register for a tournament."""

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Register",
            custom_id="reg:register",
        )

    async def callback(self, inter: discord.Interaction):
        view: RegistrationView = self.view  # type: ignore
        state = await view._get_state_for_inter(inter)
        if not state:
            return

        if not state.get("is_open", False):
            try:
                await inter.response.send_message(
                    "❌ Registration is currently closed.", ephemeral=True
                )
            except discord.InteractionResponded:
                await inter.followup.send(
                    "❌ Registration is currently closed.", ephemeral=True
                )
            return

        # Region Check
        region = state.get("region", "OPEN")
        match, player_regions = view.cog._check_region_match(inter.user, region)

        if not match and region != "OPEN":
            # Show warning using embed builder
            embed = build_region_mismatch_embed(region, player_regions)

            await inter.response.send_message(
                embed=embed,
                view=RegionMismatchView(view.cog, state["key"], inter.user),
                ephemeral=True,
            )
            return

        # Use the centralized method to handle Role + State + Panels
        added = await view.cog.add_participant(state["key"], inter.user.id, inter.user)

        msg = (
            "✅ You have been registered!" if added else "⚠️ You are already registered."
        )
        try:
            await inter.response.send_message(msg, ephemeral=True)
        except discord.InteractionResponded:
            await inter.followup.send(msg, ephemeral=True)


class UnregisterButton(ui.Button):
    """Button for players to unregister from a tournament."""

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Unregister",
            custom_id="reg:unregister",
        )

    async def callback(self, inter: discord.Interaction):
        view: RegistrationView = self.view  # type: ignore
        state = await view._get_state_for_inter(inter)
        if not state:
            return

        removed = await view.cog.remove_participant(
            state["key"], inter.user.id, inter.user
        )

        msg = (
            "✅ You have been unregistered."
            if removed
            else "⚠️ You were not registered."
        )
        try:
            await inter.response.send_message(msg, ephemeral=True)
        except discord.InteractionResponded:
            await inter.followup.send(msg, ephemeral=True)


class RefreshButton(ui.Button):
    """Button to refresh the registration panel."""

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Refresh",
            custom_id="reg:refresh",
        )

    async def callback(self, inter: discord.Interaction):
        view: RegistrationView = self.view  # type: ignore
        state = await view._get_state_for_inter(inter)
        if not state:
            return

        try:
            await inter.response.send_message(
                "♻️ Registration panel refreshed!", ephemeral=True
            )
        except discord.InteractionResponded:
            await inter.followup.send("♻️ Registration panel refreshed!", ephemeral=True)

        await view.cog.update_public_panel(state["key"])


# -----------------------------------------------------------------------------
# REGION MISMATCH CONFIRMATION
# -----------------------------------------------------------------------------


class RegionMismatchView(ui.View):
    """View for confirming registration despite region mismatch."""

    def __init__(self, cog, key: str, user: discord.Member):
        super().__init__(timeout=60)
        self.cog = cog
        self.key = key
        self.user = user

    @ui.button(label="Join Anyway", style=discord.ButtonStyle.danger)
    async def confirm(self, inter: discord.Interaction, button: ui.Button):
        # Proceed with registration
        added = await self.cog.add_participant(self.key, self.user.id, self.user)
        msg = (
            "✅ You have been registered!" if added else "⚠️ You are already registered."
        )

        # Disable buttons
        for child in self.children:
            child.disabled = True

        await inter.response.edit_message(content=msg, embed=None, view=None)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, inter: discord.Interaction, button: ui.Button):
        await inter.response.edit_message(
            content="❌ Registration cancelled.", embed=None, view=None
        )


# -----------------------------------------------------------------------------
# ADMIN MODALS
# -----------------------------------------------------------------------------


class ManualRegisterModal(ui.Modal, title="Register Player Manually"):
    """Modal for manually registering a player by user ID."""

    user_id = ui.TextInput(
        label="User ID", placeholder="123456789012345678", required=True
    )

    def __init__(self, cog, key: str):
        super().__init__()
        self.cog = cog
        self.key = key

    async def on_submit(self, inter: discord.Interaction):
        try:
            uid = int(self.user_id.value.strip())
            user = inter.guild.get_member(uid)
            if not user:
                # Try fetching if not in cache
                try:
                    user = await inter.guild.fetch_member(uid)
                except discord.NotFound:
                    return await inter.response.send_message(
                        "User not found in this server.", ephemeral=True
                    )

            await self.cog.add_participant(self.key, user.id, user)
            await inter.response.send_message(
                f"✅ Registered {user.mention}.", ephemeral=True
            )
        except ValueError:
            await inter.response.send_message("Invalid User ID.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error: {e}", ephemeral=True)


class KickPlayerModal(ui.Modal, title="Kick Player"):
    """Modal for kicking a player from registration."""

    user_id = ui.TextInput(
        label="User ID", placeholder="123456789012345678", required=True
    )

    def __init__(self, cog, key: str):
        super().__init__()
        self.cog = cog
        self.key = key

    async def on_submit(self, inter: discord.Interaction):
        try:
            uid = int(self.user_id.value.strip())
            # We don't strictly need the member object to remove them from the set,
            # but we need it to remove the role.
            user = inter.guild.get_member(uid)
            if not user:
                try:
                    user = await inter.guild.fetch_member(uid)
                except:
                    user = None  # Just remove from DB if they left server

            await self.cog.remove_participant(self.key, uid, user)
            await inter.response.send_message(f"✅ Removed user {uid}.", ephemeral=True)
        except ValueError:
            await inter.response.send_message("Invalid User ID.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error: {e}", ephemeral=True)


class AddDummiesModal(ui.Modal, title="Add Dummy Players"):
    """Modal for adding dummy players for testing."""

    count = ui.TextInput(label="How many?", placeholder="e.g. 8", required=True)

    def __init__(self, cog, key: str):
        super().__init__()
        self.cog = cog
        self.key = key

    async def on_submit(self, inter: discord.Interaction):
        try:
            num = int(self.count.value.strip())
            if num < 1:
                return await inter.response.send_message(
                    "Please enter a positive number.", ephemeral=True
                )

            await inter.response.defer(ephemeral=True)

            # Check for team tournament
            state = self.cog.tournaments.get(self.key)
            team_size = state.get("team_size", 1) if state else 1

            teams_cog = self.cog.bot.get_cog("TeamsCog")

            # Add dummies
            count = 0
            for i in range(num):
                if team_size > 1 and teams_cog:
                    if await teams_cog.create_dummy_team(self.key, team_size):
                        count += 1
                    # Small sleep to ensure unique IDs if using time in create_dummy_team
                    await asyncio.sleep(0.01)
                else:
                    # Use negative IDs for dummies to avoid conflicts
                    dummy_id = -1 * (int(time.time()) + i)
                    success = await self.cog.add_participant(self.key, dummy_id, None)
                    if success:
                        count += 1
                    # Small sleep to ensure unique IDs
                    await asyncio.sleep(0.01)

            await inter.followup.send(
                f"✅ Added {count} dummy participants.", ephemeral=True
            )
        except ValueError:
            await inter.followup.send("Invalid number.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error: {e}", ephemeral=True)


class EditTournamentModal(ui.Modal, title="Edit Tournament Details"):
    """Modal for editing tournament details before it starts."""

    name = ui.TextInput(
        label="Tournament Name", placeholder="e.g. Summer Showdown", max_length=50
    )
    region = ui.TextInput(
        label="Region", placeholder="NA / EU / APAC…", required=False, max_length=20
    )
    fmt = ui.TextInput(
        label="Format",
        placeholder="single / double / swiss / round robin",
        max_length=30,
    )
    match_length = ui.TextInput(
        label="Match Length",
        placeholder="Bo3 / Bo5 / Bo3+Bo5",
        required=False,
        max_length=20,
    )
    start_time = ui.TextInput(
        label="Start Time",
        placeholder="e.g. 6pm, tomorrow 7pm, friday 8pm",
        required=False,
        max_length=50,
    )

    def __init__(self, cog, key: str, current_state: dict):
        super().__init__()
        self.cog = cog
        self.key = key

        # Pre-fill with current values
        self.name.default = current_state.get("name", "")
        self.region.default = current_state.get("region", "")
        self.fmt.default = current_state.get("format", "")
        self.match_length.default = current_state.get("match_length", "Bo3")
        self.start_time.default = current_state.get("start_time", "")

    async def on_submit(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)

        new_name = str(self.name.value).strip()
        new_region = str(self.region.value).strip()
        new_fmt = str(self.fmt.value).strip()
        new_match_length = str(self.match_length.value).strip() or "Bo3"
        new_start_time = str(self.start_time.value).strip()

        # Check if name changed and if new name is unique
        current_state = self.cog.tournaments.get(self.key)
        if not current_state:
            return await inter.followup.send("❌ Tournament not found.", ephemeral=True)

        if new_name.lower() != current_state.get("name", "").lower():
            # Name changed, check uniqueness
            for other_key, other_data in self.cog.tournaments.items():
                if (
                    other_key != self.key
                    and other_data.get("name", "").lower() == new_name.lower()
                ):
                    return await inter.followup.send(
                        f"❌ A tournament named '{new_name}' already exists.\n"
                        f"Please choose a different name.",
                        ephemeral=True,
                    )

        # Update Discord role and category names if tournament name changed
        if new_name != current_state.get("name", ""):
            guild = inter.guild
            if guild:
                # Update role name
                role_id = current_state.get("role_id")
                if role_id:
                    role = guild.get_role(role_id)
                    if role:
                        try:
                            await role.edit(name=new_name)
                            log.info(f"Updated role name to '{new_name}'")
                        except Exception as e:
                            log.warning(f"Failed to update role name: {e}")

                # Update category name
                category_id = current_state.get("category_id")
                if category_id:
                    category = guild.get_channel(category_id)
                    if category:
                        try:
                            await category.edit(name=f"Tournaments: {new_name}")
                            log.info(
                                f"Updated category name to 'Tournaments: {new_name}'"
                            )
                        except Exception as e:
                            log.warning(f"Failed to update category name: {e}")

        # Update state
        current_state["name"] = new_name
        current_state["region"] = new_region
        current_state["format"] = new_fmt
        current_state["match_length"] = new_match_length
        current_state["start_time"] = new_start_time

        # Save to DB
        await self.cog.save_tournament(self.key)

        # Update public panel if it exists
        await self.cog.update_public_panel(self.key)

        await inter.followup.send(
            f"✅ **Tournament updated!**\n\n"
            f"**Name**: {new_name}\n"
            f"**Region**: {new_region or 'N/A'}\n"
            f"**Format**: {new_fmt}\n"
            f"**Match Length**: {new_match_length}\n"
            f"**Start Time**: {new_start_time or 'N/A'}",
            ephemeral=True,
        )
        log.info(f"Tournament {self.key} details updated by {inter.user}")


# -----------------------------------------------------------------------------
# REGISTRATION VIEW (Public Panel)
# -----------------------------------------------------------------------------


class RegistrationView(ui.View):
    """Public member-facing view with Register/Unregister/Refresh buttons."""

    def __init__(
        self,
        cog,
        tournament_key: Optional[str] = None,
        is_open: bool = False,
    ):
        super().__init__(timeout=None)  # Persistent view
        self.cog = cog
        self.tournament_key = tournament_key
        self.is_open = is_open

        # Add persistent buttons with custom IDs
        self.add_item(RegisterButton())
        self.add_item(UnregisterButton())
        self.add_item(RefreshButton())

    async def _get_state_for_inter(self, inter: discord.Interaction) -> Optional[dict]:
        """Get the state for the given interaction with error handling."""
        state = None
        if self.tournament_key:
            state = self.cog.tournaments.get(self.tournament_key)

        if not state and inter.message:
            state = self.cog.get_state_by_message(inter.message.id)

        if not state:
            try:
                await inter.response.send_message(
                    "Tournament data not found. Try refreshing.", ephemeral=True
                )
            except discord.InteractionResponded:
                await inter.followup.send(
                    "Tournament data not found. Try refreshing.", ephemeral=True
                )
        return state


# -----------------------------------------------------------------------------
# ADMIN CONTROLS VIEW
# -----------------------------------------------------------------------------


class AdminControlsView(ui.View):
    """
    Admin-only controls for a specific tournament.
    Persistent view that lives in #temp-admin.
    """

    def __init__(self, cog, key: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.key = key

    # Row 0: Player Management
    @ui.button(
        label="Register Player",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="admin:reg_player",
    )
    async def reg_player(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.send_modal(ManualRegisterModal(self.cog, self.key))

    @ui.button(
        label="Add Dummies",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="admin:add_dummies",
    )
    async def add_dummies(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.send_modal(AddDummiesModal(self.cog, self.key))

    @ui.button(
        label="Kick Player",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="admin:kick_player",
    )
    async def kick_player(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.send_modal(KickPlayerModal(self.cog, self.key))

    @ui.button(
        label="Manual Check-In",
        style=discord.ButtonStyle.secondary,
        row=0,
        custom_id="admin:checkin",
    )
    async def checkin(self, inter: discord.Interaction, _: ui.Button):
        # For now, just a toggle or simple message since check-in logic is Phase 4
        await inter.response.send_message(
            "Check-in system coming in Phase 4.", ephemeral=True
        )

    @ui.button(
        label="Resend Score Panel",
        style=discord.ButtonStyle.primary,
        row=0,
        custom_id="admin:resend_score",
    )
    async def resend_score(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.defer(ephemeral=True)
        bracket_cog = inter.client.get_cog("BracketCog")
        if not bracket_cog:
            return await inter.followup.send(
                "Bracket system not loaded.", ephemeral=True
            )

        await bracket_cog.post_score_view(self.key)
        await inter.followup.send("✅ Score panel resent.", ephemeral=True)

    # Row 1: Tournament Flow
    @ui.button(
        label="✏️ Edit Details",
        style=discord.ButtonStyle.primary,
        row=1,
        custom_id="admin:edit",
    )
    async def edit_details(self, inter: discord.Interaction, _: ui.Button):
        reg_cog = inter.client.get_cog("RegistrationCog")
        if not reg_cog:
            return await inter.response.send_message("System error.", ephemeral=True)

        # Track interaction
        await reg_cog.update_organizer_interaction(self.key, inter.user.id)

        # Get tournament state
        state = reg_cog.tournaments.get(self.key)
        if not state:
            return await inter.response.send_message(
                "❌ Tournament not found.", ephemeral=True
            )

        # Check if tournament has started (check if bracket exists)
        bracket_cog = inter.client.get_cog("BracketCog")
        if bracket_cog and self.key in bracket_cog.matches:
            return await inter.response.send_message(
                "❌ Cannot edit tournament details after it has started.",
                ephemeral=True,
            )

        # Open edit modal
        await inter.response.send_modal(EditTournamentModal(reg_cog, self.key, state))

    @ui.button(
        label="Dev: Auto-Simulate",
        style=discord.ButtonStyle.secondary,
        row=1,
        custom_id="admin:dev_auto_sim",
    )
    async def dev_auto_simulate(
        self,
        inter: discord.Interaction,
        button: ui.Button,
    ):
        """Dev-only button to auto-simulate this tournament."""
        # Only allow server admins to use this
        if not inter.user.guild_permissions.administrator:
            await inter.response.send_message(
                "You must be a server admin to use this dev tool.",
                ephemeral=True,
            )
            return

        # 🔒 Dev-user guard: requires both admin perms AND dev-user whitelist.
        # This provides dual-layer security for dev tools.
        if not is_dev_user(inter.user.id):
            await inter.response.send_message(
                "⚠️ Auto-simulation is available only to authorized dev users.",
                ephemeral=True,
            )
            return

        bracket_cog = inter.client.get_cog("BracketCog")
        if bracket_cog is None:
            await inter.response.send_message(
                "BracketCog is not loaded; cannot auto-simulate.",
                ephemeral=True,
            )
            return

        await inter.response.defer(ephemeral=True, thinking=True)

        async def send(msg: str):
            await inter.followup.send(msg, ephemeral=True)

        # 1.0 second delay between matches by default
        await bracket_cog._run_auto_simulation(send, self.key, delay=1.0)

    @ui.button(
        label="Start Tournament",
        style=discord.ButtonStyle.success,
        row=1,
        custom_id="admin:start",
    )
    async def start_tourney(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.defer(ephemeral=True)

        reg_cog = inter.client.get_cog("RegistrationCog")
        bracket_cog = inter.client.get_cog("BracketCog")

        if not reg_cog or not bracket_cog:
            return await inter.followup.send(
                "System error: Cogs not loaded.", ephemeral=True
            )

        # Track interaction
        await reg_cog.update_organizer_interaction(self.key, inter.user.id)

        # Get participants
        participants = reg_cog.get_participants(self.key)
        if len(participants) < 2:
            return await inter.followup.send(
                "❌ Need at least 2 players to start.", ephemeral=True
            )

        # Check Format
        state = reg_cog.tournaments.get(self.key)
        tourney_format = (
            state.get("format", "Single Elimination") if state else "Single Elimination"
        )

        if tourney_format == "Double Elimination":
            de_cog = inter.client.get_cog("DoubleEliminationCog")
            if not de_cog:
                return await inter.followup.send(
                    "❌ Double Elimination system not loaded.", ephemeral=True
                )

            success, msg = await de_cog.start_tournament(
                inter.guild, self.key, participants
            )
        else:
            success, msg = await bracket_cog.start_tournament(
                inter.guild, self.key, participants
            )

        if success:
            await inter.followup.send(msg, ephemeral=True)
            # Update panel to show it's started?
        else:
            await inter.followup.send(f"❌ Failed to start: {msg}", ephemeral=True)

    @ui.button(
        label="End Tournament",
        style=discord.ButtonStyle.danger,
        row=1,
        custom_id="admin:end",
    )
    async def end_tourney(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.defer(ephemeral=True)
        reg_cog = inter.client.get_cog("RegistrationCog")
        if reg_cog:
            # Track interaction
            await reg_cog.update_organizer_interaction(self.key, inter.user.id)
            await reg_cog.end_tournament(inter, self.key)

    @ui.button(
        label="Reset Bracket",
        style=discord.ButtonStyle.danger,
        row=2,
        custom_id="admin:reset",
    )
    async def reset_tourney(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.defer(ephemeral=True)
        reg_cog = inter.client.get_cog("RegistrationCog")
        if reg_cog:
            # Track interaction
            await reg_cog.update_organizer_interaction(self.key, inter.user.id)
            await reg_cog.reset_tournament(inter, self.key)

    @ui.button(
        label="Delete Tournament",
        style=discord.ButtonStyle.danger,
        row=2,
        custom_id="admin:delete",
    )
    async def delete_tourney(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.defer(ephemeral=True)

        reg_cog = inter.client.get_cog("RegistrationCog")
        if reg_cog:
            # Track interaction
            await reg_cog.update_organizer_interaction(self.key, inter.user.id)

        try:
            await self.cog.delete_tournament(self.key)
            # Don't send followup since the channel will be deleted
            # The deletion itself serves as confirmation
        except Exception as e:
            log.error(f"Error deleting tournament {self.key}: {e}", exc_info=True)
            try:
                await inter.followup.send(
                    f"❌ Error during deletion: {e}", ephemeral=True
                )
            except discord.NotFound:
                pass

    # Row 3: Toggles
    @ui.button(
        label="Open/Close Reg",
        style=discord.ButtonStyle.secondary,
        row=3,
        custom_id="admin:toggle_reg",
    )
    async def toggle_reg(self, inter: discord.Interaction, _: ui.Button):
        await inter.response.defer(ephemeral=True)
        state = self.cog.tournaments.get(self.key)
        if not state:
            return await inter.followup.send("Tournament not found", ephemeral=True)

        new_status = not state.get("is_open", True)
        await self.cog.set_registration_open(self.key, new_status)
        await inter.followup.send(
            f"Registration is now {'OPEN' if new_status else 'CLOSED'}", ephemeral=True
        )


# -----------------------------------------------------------------------------
# NEW TOURNAMENT SERVICE VIEWS (from tournaments.py)
# These are used by the new TournamentService-based flow
# -----------------------------------------------------------------------------


class Registration1v1View(ui.View):
    """Registration view for 1v1 tournaments (TournamentService flow)."""

    def __init__(self, cog, tournament_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.cog = cog
        self.tournament_id = tournament_id

    @ui.button(
        label="✅ Register",
        style=discord.ButtonStyle.success,
        custom_id="tournament_register_1v1",
    )
    async def register(self, interaction: discord.Interaction, button: ui.Button):
        """Handle 1v1 registration."""
        # Get tournament to verify it's still open
        tournament = await self.cog.tournament_service.get_by_id(self.tournament_id)

        if not tournament:
            await interaction.response.send_message(
                "❌ Tournament not found.",
                ephemeral=True,
            )
            return

        if tournament.status != "reg_open":
            await interaction.response.send_message(
                f"❌ Registration is **{tournament.status}**. Cannot register now.",
                ephemeral=True,
            )
            return

        # Check entry count
        entry_count = await self.cog.tournament_service.count_entries(tournament.id)
        if entry_count >= tournament.size:
            await interaction.response.send_message(
                "❌ Tournament is full!",
                ephemeral=True,
            )
            return

        # Check restrictions (region/rank)
        restriction_error = await self._check_restrictions(
            interaction.user.id, tournament
        )
        if restriction_error:
            await interaction.response.send_message(
                f"❌ {restriction_error}", ephemeral=True
            )
            return

        # Try to add entry
        entry, error = await self.cog.tournament_service.add_entry_1v1(
            tournament_id=tournament.id,
            user_id=interaction.user.id,
        )

        if error:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ You are registered for **{tournament.name}**!\n" f"Entry #{entry.id}",
            ephemeral=True,
        )

        log.info(
            f"[TOURNAMENT] Player {interaction.user.id} registered for tournament {tournament.id}"
        )

    async def _check_restrictions(self, user_id: int, tournament) -> Optional[str]:
        """Check if player meets tournament restrictions. Returns error message or None."""
        # No restrictions = allow everyone
        if not tournament.allowed_regions and not tournament.allowed_ranks:
            return None

        # Get player profile
        try:
            player = await self.cog.bot.player_service.get_or_create(user_id)
        except Exception:
            return "Could not verify your profile. Please complete onboarding first."

        if not player:
            return "You need to complete onboarding first."

        # Check region restriction
        if tournament.allowed_regions:
            allowed = [r.strip().upper() for r in tournament.allowed_regions.split(",")]
            player_region = (player.region or "").upper()
            if player_region not in allowed:
                return f"This tournament is restricted to regions: **{tournament.allowed_regions}**. Your region: **{player.region or 'Not set'}**"

        # Check rank restriction
        if tournament.allowed_ranks:
            allowed = [r.strip().title() for r in tournament.allowed_ranks.split(",")]
            player_rank = (player.claimed_rank or "").title()
            if player_rank not in allowed:
                return f"This tournament is restricted to ranks: **{tournament.allowed_ranks}**. Your rank: **{player.claimed_rank or 'Not set'}**"

        return None


class Registration2v2View(ui.View):
    """Registration view for 2v2 tournaments (TournamentService flow)."""

    def __init__(self, cog, tournament_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.cog = cog
        self.tournament_id = tournament_id

    @ui.button(
        label="✅ Register Team",
        style=discord.ButtonStyle.success,
        custom_id="tournament_register_2v2",
    )
    async def register_team(self, interaction: discord.Interaction, button: ui.Button):
        """Open team registration modal."""
        # Get tournament to verify it's still open
        tournament = await self.cog.tournament_service.get_by_id(self.tournament_id)

        if not tournament:
            await interaction.response.send_message(
                "❌ Tournament not found.",
                ephemeral=True,
            )
            return

        if tournament.status != "reg_open":
            await interaction.response.send_message(
                f"❌ Registration is **{tournament.status}**. Cannot register now.",
                ephemeral=True,
            )
            return

        # Check entry count
        entry_count = await self.cog.tournament_service.count_entries(tournament.id)
        if entry_count >= tournament.size:
            await interaction.response.send_message(
                "❌ Tournament is full!",
                ephemeral=True,
            )
            return

        # Show modal
        modal = TeamRegistrationModal(self.cog, tournament)
        await interaction.response.send_modal(modal)


class TeamRegistrationModal(ui.Modal, title="Register Your Team"):
    """Modal for 2v2 team registration (TournamentService flow)."""

    team_name = ui.TextInput(
        label="Team Name (optional)",
        placeholder="Enter a team name or leave blank",
        required=False,
        max_length=50,
    )

    teammate = ui.TextInput(
        label="Teammate",
        placeholder="@mention or Discord ID (e.g., 123456789)",
        required=True,
        max_length=100,
    )

    def __init__(self, cog, tournament):
        super().__init__()
        self.cog = cog
        self.tournament = tournament

    async def on_submit(self, interaction: discord.Interaction):
        """Handle team registration submission."""
        # Parse teammate input
        teammate_id = self._parse_user_id(self.teammate.value)

        if not teammate_id:
            await interaction.response.send_message(
                "❌ Could not parse teammate. Please use a valid @mention or Discord ID.",
                ephemeral=True,
            )
            return

        if teammate_id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot team with yourself!",
                ephemeral=True,
            )
            return

        # Verify teammate is in the guild
        guild = interaction.guild
        try:
            teammate_member = await guild.fetch_member(teammate_id)
        except discord.NotFound:
            await interaction.response.send_message(
                "❌ Teammate not found in this server.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Could not verify teammate. Please try again.",
                ephemeral=True,
            )
            return

        # Check restrictions for player 1
        error = await self._check_restrictions(interaction.user.id, "You")
        if error:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        # Check restrictions for teammate
        error = await self._check_restrictions(teammate_id, "Your teammate")
        if error:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        # Get team name
        team_name = self.team_name.value.strip() if self.team_name.value else None
        if not team_name:
            team_name = (
                f"{interaction.user.display_name} & {teammate_member.display_name}"
            )

        # Try to add entry
        entry, error = await self.cog.tournament_service.add_entry_2v2(
            tournament_id=self.tournament.id,
            player1_id=interaction.user.id,
            player2_id=teammate_id,
            team_name=team_name,
        )

        if error:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ Team **{team_name}** is registered for **{self.tournament.name}**!\n"
            f"Team: {interaction.user.mention} + {teammate_member.mention}\n"
            f"Entry #{entry.id}",
            ephemeral=True,
        )

        log.info(
            f"[TOURNAMENT] Team '{team_name}' ({interaction.user.id} + {teammate_id}) "
            f"registered for tournament {self.tournament.id}"
        )

    async def _check_restrictions(self, user_id: int, label: str) -> Optional[str]:
        """Check if player meets tournament restrictions. Returns error message or None."""
        # No restrictions = allow everyone
        if not self.tournament.allowed_regions and not self.tournament.allowed_ranks:
            return None

        # Get player profile
        try:
            player = await self.cog.bot.player_service.get_or_create(user_id)
        except Exception:
            return f"{label} profile could not be verified. Complete onboarding first."

        if not player:
            return f"{label} need to complete onboarding first."

        # Check region restriction
        if self.tournament.allowed_regions:
            allowed = [
                r.strip().upper() for r in self.tournament.allowed_regions.split(",")
            ]
            player_region = (player.region or "").upper()
            if player_region not in allowed:
                return f"{label} region (**{player.region or 'Not set'}**) is not allowed. This tournament is restricted to: **{self.tournament.allowed_regions}**"

        # Check rank restriction
        if self.tournament.allowed_ranks:
            allowed = [
                r.strip().title() for r in self.tournament.allowed_ranks.split(",")
            ]
            player_rank = (player.claimed_rank or "").title()
            if player_rank not in allowed:
                return f"{label} rank (**{player.claimed_rank or 'Not set'}**) is not allowed. This tournament is restricted to: **{self.tournament.allowed_ranks}**"

        return None

    def _parse_user_id(self, value: str) -> Optional[int]:
        """Parse user ID from mention or raw ID."""
        value = value.strip()

        # Try mention format: <@123456789> or <@!123456789>
        match = re.match(r"<@!?(\d+)>", value)
        if match:
            return int(match.group(1))

        # Try raw ID
        if value.isdigit():
            return int(value)

        return None
