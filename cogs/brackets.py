"""
BracketCog - Tournament Bracket Management

Manages tournament brackets, seeding, match progression, and score reporting.
UI components have been extracted to ui/bracket_views.py and ui/bracket_embeds.py.
"""

import asyncio
import logging
import math
import random
from typing import Any, Dict, List, Optional

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from config.dev_flags import is_dev_user
from database import DB_NAME
from services.status_enums import MatchStatus

# UI Components (extracted from this file)
from ui.bracket_views import ScoreModal, ScoreSubmissionView, ScoreVerificationView
from ui.bracket_embeds import (
    build_bracket_embed,
    build_score_submit_embed,
    build_standings_embed,
)

log = logging.getLogger(__name__)


class BracketCog(commands.Cog):
    """
    Manages tournament brackets, seeding, and match progression.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.matches: Dict[str, List[dict]] = {}  # key -> list of match dicts

    @commands.command(name="dumpmatches")
    @commands.has_permissions(administrator=True)
    async def dumpmatches(self, ctx: commands.Context, key: str):
        """Debug: dump raw match data for a tournament key."""
        matches = self.matches.get(key)

        if not matches:
            await ctx.send(f"No matches found for `{key}`.")
            return

        import json
        import textwrap

        pretty = json.dumps(matches, indent=2, default=str)

        # Discord message limit is 2000 chars – chunk it
        for chunk in textwrap.wrap(pretty, 1900, replace_whitespace=False):
            await ctx.send(f"```json\n{chunk}\n```")

    async def cog_load(self):
        await self.load_state()

    async def load_state(self):
        """Load match data from SQLite."""
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM matches") as cursor:
                    rows = await cursor.fetchall()

                self.matches = {}
                for row in rows:
                    m = dict(row)
                    key = m["tournament_key"]
                    if key not in self.matches:
                        self.matches[key] = []

                    # Map DB columns to internal dict structure
                    match_data = {
                        "id": m["match_id_in_tournament"],
                        "p1": m["p1_id"],
                        "p2": m["p2_id"],
                        "winner": m["winner_id"],
                        "round": m["round"],
                        "score": m["score"],
                        "status": m["status"],
                        "reports": {},  # Reports are transient for now
                    }
                    self.matches[key].append(match_data)

                # Re-register views
                for key in self.matches.keys():
                    self.bot.add_view(ScoreSubmissionView(self, key))

                log.info(
                    f"Loaded brackets for {len(self.matches)} tournaments from DB."
                )
        except Exception as e:
            log.error(f"Failed to load brackets: {e}")

    async def save_match(self, key: str, match: dict):
        """Save/Update a single match in DB."""
        try:
            # Get channel_id from tournament state
            channel_id = None
            reg_cog = self.bot.get_cog("RegistrationCog")
            if reg_cog:
                state = reg_cog.tournaments.get(key)
                if state:
                    channel_id = state.get("channels", {}).get("match_chat")

            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO matches (
                        tournament_key, match_id_in_tournament, p1_id, p2_id, winner_id, round, score, status, channel_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        key,
                        match["id"],
                        match["p1"],
                        match["p2"],
                        match["winner"],
                        match["round"],
                        match["score"],
                        match.get("status", MatchStatus.PENDING.value),
                        channel_id,
                    ),
                )
                await db.commit()
        except Exception as e:
            log.error(f"Failed to save match {match['id']} for {key}: {e}")

    def get_results(self, key: str) -> dict:
        """Get the results of a tournament (Winner, Runner-up)."""
        matches = self.matches.get(key, [])
        if not matches:
            return {}

        # Find the final match (highest round)
        final_round = max((m["round"] for m in matches), default=0)
        final_matches = [m for m in matches if m["round"] == final_round]

        if not final_matches:
            return {}

        # Assuming single elimination, there is only one match in the final round
        final = final_matches[0]
        winner_id = final.get("winner")

        if not winner_id:
            return {}

        # Runner up is the other player
        p1 = final["p1"]
        p2 = final["p2"]
        runner_up_id = p1 if p1 != winner_id else p2

        return {
            "winner_id": winner_id,
            "runner_up_id": runner_up_id,
            "round_count": final_round,
        }

    async def _update_standings_channel(self, key: str):
        """
        Update the standings channel with a bracket image.

        Posts or edits a single message containing the rendered bracket PNG.
        Stores the message ID in tournaments.standings_message_id for edit-in-place.
        """
        try:
            # Get tournament data
            reg_cog = self.bot.get_cog("RegistrationCog")
            if not reg_cog:
                log.warning(
                    f"Cannot update standings for {key}: RegistrationCog not found"
                )
                return

            state = reg_cog.tournaments.get(key)
            if not state:
                log.warning(
                    f"Cannot update standings for {key}: Tournament state not found"
                )
                return

            # Get standings channel
            standings_ch_id = state.get("channels", {}).get("standings")
            if not standings_ch_id:
                log.warning(f"Cannot update standings for {key}: No standings channel")
                return

            channel = self.bot.get_channel(standings_ch_id)
            if not channel:
                log.warning(
                    f"Cannot update standings for {key}: Channel {standings_ch_id} not found"
                )
                return

            # Import snapshot and render services
            try:
                from services.bracket_snapshot import get_bracket_snapshot
                from services.bracket_render_service import get_bracket_render_service

                # Build snapshot
                snapshot = await get_bracket_snapshot(self.bot, key, state)
                if not snapshot:
                    log.info(f"No bracket data yet for {key}, skipping image update")
                    return

                # Render image
                render_service = get_bracket_render_service()
                image_bytes = render_service.render_bracket(snapshot)

                if not image_bytes:
                    log.warning(
                        f"Failed to render bracket for {key}, falling back to embed"
                    )
                    # Fall back to existing embed-based display
                    await self._fallback_embed_standings(key, state, channel)
                    return

                # Create discord.File from bytes
                import io

                file = discord.File(io.BytesIO(image_bytes), filename="bracket.png")

                # Check if we have an existing standings message to edit
                standings_msg_id = state.get("standings_message_id")
                message = None

                if standings_msg_id:
                    try:
                        message = await channel.fetch_message(standings_msg_id)
                    except discord.NotFound:
                        log.info(
                            f"Standings message {standings_msg_id} not found, will create new"
                        )
                        message = None
                    except discord.HTTPException as e:
                        log.warning(f"Error fetching standings message: {e}")
                        message = None

                # Build embed using extracted function
                embed = build_standings_embed(
                    name=state.get("name", "Tournament"),
                    participant_count=snapshot.participant_count,
                    winner_name=snapshot.winner_name,
                )

                if message:
                    # Edit existing message - need to delete and re-send since we can't edit attachments
                    try:
                        await message.delete()
                    except discord.HTTPException:
                        pass

                # Send new message with image
                new_msg = await channel.send(embed=embed, file=file)

                # Store the new message ID
                state["standings_message_id"] = new_msg.id

                # Save to database
                from services.tournament_service import TournamentService

                await TournamentService.update_tournament(
                    key, standings_message_id=new_msg.id
                )

                log.info(
                    f"Updated standings for {key} with bracket image (msg: {new_msg.id})"
                )

            except ImportError as e:
                log.warning(
                    f"Bracket rendering unavailable ({e}), using embed fallback"
                )
                # Fall back to existing embed-based display
                await self._fallback_embed_standings(key, state, channel)

        except Exception as e:
            log.error(
                f"Failed to update standings channel for {key}: {e}", exc_info=True
            )

    async def _fallback_embed_standings(
        self, key: str, state: dict, channel: discord.TextChannel
    ):
        """Fall back to embed-based bracket display when image rendering unavailable."""
        matches = self.matches.get(key, [])
        teams_cog = self.bot.get_cog("TeamsCog")
        get_team_name = teams_cog.get_team_name if teams_cog else None
        embed = await build_bracket_embed(
            state.get("name", "Tournament"), matches, get_team_name
        )
        await channel.purge(limit=5)
        await channel.send(embed=embed)

    # [PHASE3] Unified clear_bracket implementation – earlier duplicate removed.
    async def async_clear_bracket(self, key: str):
        if key in self.matches:
            del self.matches[key]

        try:
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("DELETE FROM matches WHERE tournament_key = ?", (key,))
                await db.commit()
            log.info(f"Cleared bracket for {key}")
        except Exception as e:
            log.error(f"Failed to clear bracket DB: {e}")

    def clear_bracket(self, key: str):
        # Wrapper for sync callers - schedules async cleanup
        self.bot.loop.create_task(self.async_clear_bracket(key))

    async def generate_bracket(
        self, participants: List[Any], fmt: str = "Single Elimination"
    ) -> List[dict]:
        """
        Generate the initial set of matches based on format with rank-based seeding.
        Participants are seeded by skill rating if PlayerProfile cog is available.
        """
        if fmt != "Single Elimination":
            raise NotImplementedError(f"Format '{fmt}' is not yet implemented.")

        # --- Rank-Based Seeding ---
        seeded_participants = await self._seed_participants(participants)

        # --- Single Elimination Logic ---
        matches = []
        match_id = 1

        i = 0
        while i < len(seeded_participants):
            p1 = seeded_participants[i]
            p2 = (
                seeded_participants[i + 1] if i + 1 < len(seeded_participants) else None
            )

            # Auto-resolve BYEs only (dummy vs dummy now requires dev auto-sim)
            winner = None
            score = None
            status = MatchStatus.PENDING.value

            if p2 is None:
                winner = p1
                score = "BYE"
                status = MatchStatus.COMPLETED.value

            matches.append(
                {
                    "id": match_id,
                    "p1": p1,
                    "p2": p2,
                    "winner": winner,
                    "round": 1,
                    "score": score,
                    "status": status,
                    "reports": {},
                }
            )
            match_id += 1
            i += 2

        return matches

    async def _seed_participants(self, participants: List[Any]) -> List[Any]:
        """
        Seed participants by skill rating (Elo-based).

        - Individual players: use ProfileService / PlayerProfile Elo (1v1).
        - Teams: use TeamsCog-provided average rating (implementation-dependent).
        - Dummy players: seeded as average Elo (1000) so they don't distort brackets.

        Handles both individual users (int) and teams (str).
        """
        profile_cog = self.bot.get_cog("PlayerProfile")
        teams_cog = self.bot.get_cog("TeamsCog")

        if not participants:
            return []

        # Determine if we are seeding teams or players
        is_team = isinstance(participants[0], str)

        if not profile_cog and not is_team:
            # No rank/Elo system, just shuffle randomly
            log.info("PlayerProfile cog not found - using random seeding")
            random.shuffle(participants)
            return participants

        ratings: list[tuple[Any, float]] = []

        for p in participants:
            # Dummy players (negative sentinel IDs)
            if isinstance(p, int) and p < 0:
                # Use a neutral mid-range Elo for dummies
                ratings.append((p, 1000.0))

            elif is_team:
                # Team seeding – defer to TeamsCog's notion of rating
                if teams_cog:
                    # NOTE: you may want this to return Elo as well in Phase 3
                    avg_rating = await teams_cog.get_team_average_rank(p)
                    ratings.append((p, float(avg_rating)))
                else:
                    ratings.append((p, 1000.0))

            else:
                # Individual seeding – use Elo as the unified skill metric
                skill_rating = await profile_cog.get_skill_rating(p)  # now returns Elo

                # If player is flagged as a smurf, bump effective Elo
                smurf_flagged = await profile_cog.is_smurf_flagged(p)
                if smurf_flagged:
                    # +200 Elo is roughly one full rank tier bump
                    skill_rating += 200
                    log.info(f"Adjusted seeding for flagged smurf {p}: +200 Elo")

                ratings.append((p, float(skill_rating)))

        # Sort by skill rating (highest Elo first)
        ratings.sort(key=lambda x: x[1], reverse=True)

        # Classic seeding: pair 1 vs n, 2 vs n-1, etc.
        n = len(ratings)
        seeded: list[Any] = []

        for i in range((n + 1) // 2):
            # Add top seed
            seeded.append(ratings[i][0])
            # Add corresponding bottom seed if there is one
            if n - 1 - i > i:
                seeded.append(ratings[n - 1 - i][0])

        log.info(f"Seeded {len(participants)} participants by Elo-based skill rating")
        return seeded

    async def get_active_match(self, key: str, user_id: int) -> Optional[dict]:
        """Find the current active match for a user (or their team)."""
        matches = self.matches.get(key, [])
        teams_cog = self.bot.get_cog("TeamsCog")

        for m in matches:
            if not m.get("winner"):
                p1 = m["p1"]
                p2 = m["p2"]

                # Check for Team ID (string)
                if isinstance(p1, str) and teams_cog:
                    if await teams_cog.is_user_in_team(
                        user_id, p1
                    ) or await teams_cog.is_user_in_team(user_id, p2):
                        return m
                else:
                    if p1 == user_id or p2 == user_id:
                        return m
        return None

    async def find_match(self, key: str, p1_id: Any, p2_id: Any) -> Optional[dict]:
        """Find active match between two entities (users or teams)."""
        matches = self.matches.get(key, [])
        for m in matches:
            if not m.get("winner"):
                # Compare as strings to handle mixed types safely
                if (str(m["p1"]) == str(p1_id) and str(m["p2"]) == str(p2_id)) or (
                    str(m["p1"]) == str(p2_id) and str(m["p2"]) == str(p1_id)
                ):
                    return m
        return None

    async def handle_match_report(
        self,
        inter: discord.Interaction,
        key: str,
        match: dict,
        winner_id: int,
        score: str,
    ):
        """Handle a score report: Auto-confirm Dummies, Store & Wait, or Compare & Verify."""

        # 1. Check for Dummy Opponent (Auto-Confirm)
        opponent_id = match["p1"] if match["p2"] == inter.user.id else match["p2"]
        if opponent_id < 0:
            await self._resolve_match(key, match["id"], winner_id, score)
            await inter.followup.send(
                "✅ Match vs Dummy auto-confirmed!", ephemeral=True
            )
            return

        # 2. Store Report
        if "reports" not in match:
            match["reports"] = {}

        match["reports"][str(inter.user.id)] = {"winner": winner_id, "score": score}
        # We don't save reports to DB currently, just in memory.
        # If bot restarts, reports are lost. This is acceptable for now (players just report again).

        # 3. Check if Opponent has reported
        opp_report = match["reports"].get(str(opponent_id))

        if not opp_report:
            await inter.followup.send(
                f"✅ Report submitted! Waiting for <@{opponent_id}> to confirm.",
                ephemeral=True,
            )
            return

        # 4. Compare Reports
        if opp_report["winner"] == winner_id and opp_report["score"] == score:
            # MATCH! Auto-confirm
            await self._resolve_match(key, match["id"], winner_id, score)
            await inter.followup.send(
                "✅ Match confirmed! (Both players reported same result)",
                ephemeral=True,
            )
        else:
            # CONFLICT! Request Admin Verification
            await self.request_verification(
                inter, key, match, winner_id, score, conflict=True
            )

    async def request_verification(
        self,
        inter: discord.Interaction,
        key: str,
        match: dict,
        winner_id: Any,
        score: str,
        conflict: bool = False,
    ):
        """Post verification request to #match-chat."""
        reg_cog = self.bot.get_cog("RegistrationCog")
        teams_cog = self.bot.get_cog("TeamsCog")
        if not reg_cog:
            return

        state = reg_cog.tournaments.get(key)
        if not state:
            return

        match_ch_id = state["channels"].get("match_chat")
        if not match_ch_id:
            return

        channel = self.bot.get_channel(match_ch_id)
        if not channel:
            return

        # Resolve Names
        p1 = match["p1"]
        p2 = match["p2"]
        p1_str = "Unknown"
        p2_str = "Unknown"

        if isinstance(p1, str) and teams_cog:
            p1_str = await teams_cog.get_team_name(p1)
        elif isinstance(p1, int):
            p1_str = f"<@{p1}>" if p1 > 0 else f"Dummy {abs(p1)}"

        if isinstance(p2, str) and teams_cog:
            p2_str = await teams_cog.get_team_name(p2)
        elif isinstance(p2, int):
            p2_str = f"<@{p2}>" if p2 > 0 else f"Dummy {abs(p2)}"

        title = "⚠️ Match Conflict!" if conflict else "⚖️ Match Verification"
        color = discord.Color.red() if conflict else discord.Color.orange()

        embed = discord.Embed(
            title=title,
            description=f"**Match {match['id']}**\n{p1_str} vs {p2_str}",
            color=color,
        )

        if conflict:
            # Show both reports
            reports = match.get("reports", {})
            for uid, r in reports.items():
                user_str = f"<@{uid}>"
                w_id = r["winner"]
                w_str = str(w_id)

                if isinstance(w_id, str) and teams_cog:
                    w_str = await teams_cog.get_team_name(w_id)
                elif isinstance(w_id, int):
                    w_str = f"<@{w_id}>" if w_id > 0 else f"Dummy {abs(w_id)}"

                embed.add_field(
                    name=f"Report by {user_str}",
                    value=f"Winner: {w_str}\nScore: {r['score']}",
                    inline=False,
                )
            embed.set_footer(text="Admins: Please resolve this conflict.")
        else:
            w_str = str(winner_id)
            if isinstance(winner_id, str) and teams_cog:
                w_str = await teams_cog.get_team_name(winner_id)
            elif isinstance(winner_id, int):
                w_str = (
                    f"<@{winner_id}>" if winner_id > 0 else f"Dummy {abs(winner_id)}"
                )

            embed.add_field(name="Reported Winner", value=w_str, inline=True)
            embed.add_field(name="Score", value=score, inline=True)
            embed.set_footer(text="Admins: Confirm if this is correct.")

        view = ScoreVerificationView(self, key, match["id"], winner_id, score)
        await channel.send(embed=embed, view=view)
        if conflict:
            await inter.followup.send(
                "⚠️ Conflict detected! Admins have been notified.", ephemeral=True
            )
        else:
            await inter.followup.send(
                "✅ Score reported! Waiting for admin verification.", ephemeral=True
            )

    async def confirm_match(
        self,
        inter: discord.Interaction,
        key: str,
        match_id: int,
        winner_id: int,
        score: str,
    ):
        """Admin manually confirms a match."""
        await self._resolve_match(key, match_id, winner_id, score)
        await inter.message.edit(
            content=f"✅ Match {match_id} verified by {inter.user.mention}!",
            view=None,
            embed=None,
        )

    async def _resolve_match(self, key: str, match_id: int, winner_id: int, score: str):
        """Core logic to resolve a match and advance state."""
        matches = self.matches.get(key)
        if not matches:
            return

        # Update match
        match = next((m for m in matches if m["id"] == match_id), None)
        if not match:
            return

        match["winner"] = winner_id
        match["score"] = score
        match["status"] = MatchStatus.COMPLETED.value

        # Save to DB
        await self.save_match(key, match)

        # ============================================================
        # PHASE 1: CORE SERVICES INTEGRATION
        # ============================================================
        #  Get tournament data to determine team_size
        reg_cog = self.bot.get_cog("RegistrationCog")
        tournament_data = None
        team_size = 1  # Default to 1v1
        region = None

        if reg_cog:
            tournament_data = reg_cog.tournaments.get(key)
            if tournament_data:
                team_size = tournament_data.get("team_size", 1)
                region = tournament_data.get("region")

        loser_id = match["p1"] if match["p1"] != winner_id else match["p2"]

        # Only apply Phase 1 services for individual (non-team) matches
        if isinstance(winner_id, int) and isinstance(loser_id, int):
            if winner_id > 0 and loser_id > 0:
                # Use Phase 1 services
                try:
                    from services.rating_service import Mode

                    # Get or create players
                    p1 = await self.bot.player_service.get_or_create(winner_id)
                    p2 = await self.bot.player_service.get_or_create(loser_id)

                    # Parse score (expect format like "2-1" or "3-0")
                    try:
                        parts = score.split("-")
                        if len(parts) == 2:
                            score_p1 = int(parts[0])
                            score_p2 = int(parts[1])
                        else:
                            score_p1 = 1
                            score_p2 = 0
                    except:
                        score_p1 = 1
                        score_p2 = 0

                    # Apply Elo for 1v1 tournaments only
                    mode_enum = None
                    mode_str = f"{team_size}v{team_size}"

                    if team_size == 1:
                        mode_enum = Mode.ONES
                        mode_str = "1v1"

                        # Update Elo ratings
                        new_elo_p1, new_elo_p2 = (
                            await self.bot.rating_service.apply_match_result(
                                p1, p2, mode_enum, score_p1, score_p2
                            )
                        )

                        log.info(
                            f"[PHASE1-ELO] Tournament {key} Match {match_id}: "
                            f"Player {winner_id} -> {new_elo_p1}, "
                            f"Player {loser_id} -> {new_elo_p2}"
                        )

                    # UMS Phase 1.8: Log to matches_unified and match_participants
                    guild_id = tournament_data.get("guild_id") if tournament_data else 0
                    match_unified_id = await self.bot.global_match_service.log_match(
                        guild_id=guild_id,
                        mode="tournament_se",
                        source="tournament_se",
                        team1_score=score_p1,
                        team2_score=score_p2,
                        winner_team=1 if winner_id == match["p1"] else 2,
                    )

                    await self.bot.global_match_service.log_participants(
                        match_id=match_unified_id,
                        players_team1=[winner_id],
                        players_team2=[loser_id],
                    )

                    log.info(
                        f"[UMS] Recorded SE tournament match {match_unified_id} "
                        f"for {key} ({mode_str}, {winner_id} def. {loser_id})"
                    )

                except Exception as e:
                    log.error(
                        f"[PHASE1-ERROR] Failed to apply Phase 1 services: {e}",
                        exc_info=True,
                    )

        # ============================================================
        # LEGACY SYSTEMS (Keep for now)
        # ============================================================
        # Update Leaderboard & Player Stats
        leaderboard = self.bot.get_cog("LeaderboardCog")
        profile_cog = self.bot.get_cog("PlayerProfile")
        teams_cog = self.bot.get_cog("TeamsCog")

        # Handle Team vs Team
        if isinstance(winner_id, str) and teams_cog:
            pass  # TODO: Implement team stats update
            log.info(f"Team Match Resolved: {winner_id} def. {loser_id}")

        else:
            # Individual Match
            if leaderboard:
                if isinstance(winner_id, int) and isinstance(loser_id, int):
                    if winner_id > 0 or loser_id > 0:
                        await leaderboard.record_match_result(
                            winner_id, loser_id, tournament_key=key
                        )

            if profile_cog:
                if isinstance(winner_id, int) and isinstance(loser_id, int):
                    if winner_id > 0 and loser_id > 0:
                        await profile_cog.update_player_stats_after_match(
                            winner_id, loser_id, key
                        )

        # Update Standings
        await self._update_standings_channel(key)

        # Check for next round / winner
        await self.advance_bracket(key)

    async def _run_auto_simulation(
        self,
        send,
        key: str,
        delay: float = 1.0,
    ) -> None:
        """
        Dev-only: Auto-simulate a dummy-only Single Elimination bracket.

        Runs the tournament round-by-round, picking random winners for each
        match and using the standard _resolve_match flow (DB updates, standings
        image updates, bracket advancement).

        Safety: Only works if ALL participants have negative IDs (dummy players).
        Real-player tournaments will be rejected.

        Args:
            send: Async callable that takes a string and sends a message
                  (e.g., ctx.send, interaction.followup.send).
            key: Tournament key.
            delay: Seconds to wait between match resolutions (default 1.0).
        """
        matches = self.matches.get(key)
        if not matches:
            await send(
                f"⚠️ No matches found for `{key}`. "
                "Make sure the tournament has been started so matches are generated."
            )
            return

        # Collect participant IDs from the bracket
        participants: set[int] = set()
        for m in matches:
            for pid_key in ("p1", "p2"):
                pid = m.get(pid_key)
                if isinstance(pid, int):
                    participants.add(pid)

        # Only allow dev auto-sim if all participants are dummy IDs (negative ints)
        if not participants or not all(pid < 0 for pid in participants):
            await send(
                "⚠️ Auto-simulation is only allowed for dummy-only tournaments "
                "(all participant IDs < 0)."
            )
            return

        await send(
            f"🧪 Starting auto-simulation for `{key}` "
            f"(delay: {delay:.1f}s between matches)..."
        )

        while True:
            matches = self.matches.get(key, [])
            if not matches:
                await send("⚠️ Tournament matches disappeared; aborting.")
                return

            # Find all pending matches (no winner assigned yet)
            pending = [m for m in matches if not m.get("winner")]
            if not pending:
                # All matches resolved; check for a winner
                results = self.get_results(key)
                if results:
                    winner_id = results.get("winner_id")
                    await send(
                        f"✅ Simulation complete. "
                        f"Winner: `{winner_id}` (see standings / results embeds)."
                    )
                else:
                    await send(
                        "✅ Simulation complete, but no winner could be determined."
                    )
                break

            # Work round-by-round: choose the lowest round that still has pending matches
            current_round = min(m["round"] for m in pending)
            round_matches = [m for m in pending if m["round"] == current_round]

            await send(
                f"▶️ Simulating Round {current_round} "
                f"({len(round_matches)} match(es))..."
            )

            for m in round_matches:
                p1 = m["p1"]
                p2 = m["p2"]

                if p2 is None:
                    winner = p1
                    score = "BYE"
                else:
                    winner = random.choice([p1, p2])
                    score = "Simulated"

                await self._resolve_match(key, m["id"], winner, score)
                await asyncio.sleep(delay)

            # Small pause between rounds
            await asyncio.sleep(delay)

    @app_commands.command(
        name="simulate_tournament",
        description="Dev: auto-play a dummy-only tournament (admin only).",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def simulate_tournament_slash(
        self,
        interaction: discord.Interaction,
        key: str,
        delay: app_commands.Range[float, 0.1, 10.0] = 1.0,
    ):
        """Slash command wrapper around the auto-sim logic."""
        # 🔒 Dev-user guard: requires both admin perms AND dev-user status.
        if not is_dev_user(interaction.user.id):
            await interaction.response.send_message(
                "⚠️ Auto-simulation is available only to authorized dev users.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        async def send(msg: str):
            await interaction.followup.send(msg, ephemeral=True)

        await self._run_auto_simulation(send, key, float(delay))

    async def start_tournament(
        self, guild: discord.Guild, key: str, participants: List[int]
    ):
        """
        Start the tournament: generate bracket and post standings.
        """
        # Check for team tournament
        reg_cog = self.bot.get_cog("RegistrationCog")
        teams_cog = self.bot.get_cog("TeamsCog")

        final_participants = participants

        if reg_cog:
            state = reg_cog.tournaments.get(key)
            if state and state.get("team_size", 1) > 1:
                # Team Tournament!
                if teams_cog:
                    # Fetch Team IDs instead of User IDs
                    team_ids = await teams_cog.get_tournament_teams(key)
                    if len(team_ids) < 2:
                        return False, "Not enough teams to start (need at least 2)."
                    final_participants = team_ids
                    log.info(
                        f"Starting Team Tournament {key} with {len(team_ids)} teams."
                    )
                else:
                    return False, "Teams system not loaded."

        if len(final_participants) < 2:
            return False, "Not enough players to start (need at least 2)."

        matches = await self.generate_bracket(final_participants)
        self.matches[key] = matches

        # Save all matches to DB
        for m in matches:
            await self.save_match(key, m)

        # Get RegistrationCog to find channels
        reg_cog = self.bot.get_cog("RegistrationCog")
        if not reg_cog:
            return False, "Registration system not found."

        tourney_data = reg_cog.tournaments.get(key)
        if not tourney_data:
            return False, "Tournament data not found."

        # Close registration
        await reg_cog.set_registration_open(key, False)

        # Post Standings
        await self._update_standings_channel(key)

        # Post Score Submission View
        await self.post_score_view(key)

        # Ping match chat
        match_ch_id = tourney_data["channels"].get("match_chat")
        if match_ch_id:
            match_ch = guild.get_channel(match_ch_id)
            if match_ch:
                standings_ch_id = tourney_data["channels"].get("standings")
                standings_mention = (
                    f"<#{standings_ch_id}>" if standings_ch_id else "#standings"
                )
                await match_ch.send(
                    f"🏆 **Tournament Started!** Check {standings_mention} for matchups.\nGLHF!"
                )

        # Notify players of their Round 1 matches
        await self.notify_round_matches(key, round_num=1)

        return True, "Tournament started successfully!"

    async def advance_bracket(self, key: str):
        """Check if round is complete and generate next round."""
        matches = self.matches.get(key, [])
        if not matches:
            return

        # Find current round
        current_round = max(m["round"] for m in matches)

        # Get matches for this round
        round_matches = [m for m in matches if m["round"] == current_round]

        # Check if all complete
        if not all(m.get("winner") for m in round_matches):
            return  # Round not finished

        # Round finished! Generate next round.
        # Sort by ID to ensure consistent pairing
        round_matches.sort(key=lambda x: x["id"])

        winners = [m["winner"] for m in round_matches]

        if len(winners) == 1:
            # Tournament Over!
            await self.announce_winner(key, winners[0])
            return

        # Generate next round pairings
        next_round = current_round + 1
        new_matches = []
        match_id = max(m["id"] for m in matches) + 1

        i = 0
        while i < len(winners):
            p1 = winners[i]
            p2 = winners[i + 1] if i + 1 < len(winners) else None

            # Auto-resolve BYEs only (dummy vs dummy now uses dev auto-sim)
            winner = None
            score = None
            status = MatchStatus.PENDING.value

            if p2 is None:
                winner = p1
                score = "BYE"
                status = MatchStatus.COMPLETED.value

            new_matches.append(
                {
                    "id": match_id,
                    "p1": p1,
                    "p2": p2,
                    "winner": winner,
                    "round": next_round,
                    "score": score,
                    "status": status,
                    "reports": {},
                }
            )
            match_id += 1
            i += 2

        self.matches[key].extend(new_matches)

        # Save new matches to DB
        for m in new_matches:
            await self.save_match(key, m)

        # Update Standings
        await self._update_standings_channel(key)

        # Announce Next Round
        await self.announce_round(key, next_round)

        # Notify players of their matches for this round
        await self.notify_round_matches(key, next_round)

        # Check if THIS round is also finished (e.g. Dummy vs Dummy)
        if all(m["winner"] for m in new_matches):
            await self.advance_bracket(key)

    async def announce_round(self, key: str, round_num: int):
        reg_cog = self.bot.get_cog("RegistrationCog")
        if not reg_cog:
            return
        state = reg_cog.tournaments.get(key)
        if not state:
            return

        match_ch_id = state["channels"].get("match_chat")
        if match_ch_id:
            ch = self.bot.get_channel(match_ch_id)
            if ch:
                await ch.send(f"🔔 **Round {round_num} has started!** Good luck!")

    async def announce_winner(self, key: str, winner_id: Any):
        reg_cog = self.bot.get_cog("RegistrationCog")
        teams_cog = self.bot.get_cog("TeamsCog")
        if not reg_cog:
            return
        state = reg_cog.tournaments.get(key)
        if not state:
            return

        match_ch_id = state["channels"].get("match_chat")

        winner_str = str(winner_id)
        if isinstance(winner_id, str) and teams_cog:
            winner_str = await teams_cog.get_team_name(winner_id)
        elif isinstance(winner_id, int):
            winner_str = (
                f"<@{winner_id}>" if winner_id > 0 else f"Dummy {abs(winner_id)}"
            )

        # Mark as auto-concluded if it was auto-started
        if state.get("auto_started"):
            state["auto_concluded"] = True
            await reg_cog.save_tournament(key)

        # Record Tournament Win in Leaderboard
        leaderboard = self.bot.get_cog("LeaderboardCog")
        if leaderboard and isinstance(winner_id, int) and winner_id > 0:
            await leaderboard.record_tournament_placement(
                winner_id, 1, tournament_key=key, tournament_name=state.get("name")
            )

            # Record Runner Up
            results = self.get_results(key)
            runner_up = results.get("runner_up_id")
            if runner_up and isinstance(runner_up, int) and runner_up > 0:
                await leaderboard.record_tournament_placement(
                    runner_up, 2, tournament_key=key, tournament_name=state.get("name")
                )

        if match_ch_id:
            ch = self.bot.get_channel(match_ch_id)
            if ch:
                await ch.send(
                    f"🎉 🏆 **CONGRATULATIONS {winner_str}!!** 🏆 🎉\nYou are the tournament champion!"
                )

        # If this is a recurring tournament, trigger auto-cleanup after delay
        if state.get("schedule_id"):
            asyncio.create_task(self._auto_cleanup_recurring(key, winner_id, state))

    async def notify_round_matches(self, key: str, round_num: int):
        """
        Ping players in #match-chat about their active matches for a specific round.
        """
        reg_cog = self.bot.get_cog("RegistrationCog")
        teams_cog = self.bot.get_cog("TeamsCog")
        if not reg_cog:
            return

        state = reg_cog.tournaments.get(key)
        if not state:
            return

        match_ch_id = state["channels"].get("match_chat")
        if not match_ch_id:
            return

        match_ch = self.bot.get_channel(match_ch_id)
        if not match_ch:
            return

        # Get all active matches for this round
        matches = self.matches.get(key, [])
        round_matches = [
            m for m in matches if m["round"] == round_num and not m.get("winner")
        ]

        if not round_matches:
            return

        # Send header
        await match_ch.send(f"⚔️ **Round {round_num} Matches** ⚔️")

        # Notify each match
        for match in round_matches:
            p1_id = match["p1"]
            p2_id = match["p2"]
            match_id = match["id"]

            p1_str = "Unknown"
            p2_str = "Unknown"
            p1_ping = None
            p2_ping = None

            # Resolve P1
            if isinstance(p1_id, str) and teams_cog:
                p1_str = await teams_cog.get_team_name(p1_id)
                p1_ping = await teams_cog.get_team_captain(p1_id)
            elif isinstance(p1_id, int):
                if p1_id < 0:
                    p1_str = f"Dummy {abs(p1_id)}"
                else:
                    p1_str = f"<@{p1_id}>"
                    p1_ping = p1_id

            # Resolve P2
            if p2_id is None:
                p2_str = "**BYE**"
            elif isinstance(p2_id, str) and teams_cog:
                p2_str = await teams_cog.get_team_name(p2_id)
                p2_ping = await teams_cog.get_team_captain(p2_id)
            elif isinstance(p2_id, int):
                if p2_id < 0:
                    p2_str = f"Dummy {abs(p2_id)}"
                else:
                    p2_str = f"<@{p2_id}>"
                    p2_ping = p2_id

            # Send match notification
            if p2_id is None:
                # BYE match
                await match_ch.send(
                    f"Match #{match_id}: {p1_str} has a **BYE** and advances automatically!"
                )
            elif (
                isinstance(p1_id, int)
                and p1_id < 0
                and isinstance(p2_id, int)
                and p2_id < 0
            ):
                # Dummy vs Dummy (auto-simulated)
                await match_ch.send(
                    f"Match #{match_id}: {p1_str} vs {p2_str} (auto-simulated)"
                )
            else:
                # Real match - ping the players/captains
                ping_list = []
                if p1_ping:
                    ping_list.append(f"<@{p1_ping}>")
                if p2_ping:
                    ping_list.append(f"<@{p2_ping}>")

        log.info(
            f"Notified {len(round_matches)} matches for Round {round_num} in tournament {key}"
        )

    async def post_score_view(self, key: str):
        """Post the score submission view to the submit-score channel."""
        reg_cog = self.bot.get_cog("RegistrationCog")
        if not reg_cog:
            return

        tourney_data = reg_cog.tournaments.get(key)
        if not tourney_data:
            return

        submit_ch_id = tourney_data["channels"].get("submit_score")
        if not submit_ch_id:
            return

        submit_ch = self.bot.get_channel(submit_ch_id)
        if not submit_ch:
            return

        try:
            # Purge old messages to keep it clean
            await submit_ch.purge(limit=5)

            embed = build_score_submit_embed()
            await submit_ch.send(embed=embed, view=ScoreSubmissionView(self, key))
            log.info(f"Posted score submission view to {submit_ch.name}")
        except Exception as e:
            log.error(f"Failed to post score submission view: {e}")

    async def _auto_cleanup_recurring(self, key: str, winner_id: Any, state: dict):
        """Auto-cleanup for recurring tournaments - archive and delete."""
        from utils.recurring_helpers import archive_tournament

        # Wait 5 minutes to let players see results
        await asyncio.sleep(300)

        log.info(f"Starting auto-cleanup for recurring tournament {key}")

        try:
            # Get results
            results = self.get_results(key)
            runner_up = results.get("runner_up_id")

            # Archive tournament
            await archive_tournament(
                tournament_key=key,
                winner_id=winner_id if isinstance(winner_id, int) else None,
                runner_up_id=runner_up if isinstance(runner_up, int) else None,
                schedule_id=state.get("schedule_id"),
                tournament_name=state.get("name"),
                guild_id=state.get("guild_id"),
                format=state.get("format"),
                participants_count=len(state.get("participants", set())),
            )

            # Delete tournament via RegistrationCog
            reg_cog = self.bot.get_cog("RegistrationCog")
            if reg_cog:
                try:
                    await reg_cog.delete_tournament(key)
                    log.info("Auto-cleaned up recurring tournament %s", key)
                except Exception:
                    log.error(
                        "Failed to auto-cleanup tournament %s from BracketCog",
                        key,
                        exc_info=True,
                    )

        except Exception as e:
            log.error(f"Failed to auto-cleanup tournament {key}: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BracketCog(bot))
