"""
services/tournament_service.py — Tournament Management for UMS Core
====================================================================
Handles tournament CRUD, entries, and match management for Single
Elimination tournaments.

Status progression:
  draft → reg_open → reg_closed → in_progress → completed
                                            ↘ cancelled
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, List

import aiosqlite

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------


@dataclass
class Tournament:
    """Tournament record."""

    id: int
    guild_id: int
    name: str
    format: str  # '1v1' or '2v2'
    size: int  # 8, 16, 32, 64
    status: str
    tournament_code: Optional[str] = None  # Human-friendly code like JTP6F9KE
    reg_message_id: Optional[int] = None
    reg_channel_id: Optional[int] = None
    allowed_regions: Optional[str] = None  # CSV: "USE,EU"
    allowed_ranks: Optional[str] = None  # CSV: "Gold,Platinum"
    dashboard_channel_id: Optional[int] = None
    dashboard_message_id: Optional[int] = None
    created_at: Optional[int] = None


@dataclass
class TournamentEntry:
    """Tournament entry (player or team)."""

    id: int
    tournament_id: int
    player1_id: int
    player2_id: Optional[int] = None  # Only for 2v2
    team_name: Optional[str] = None
    seed: Optional[int] = None
    created_at: Optional[int] = None


@dataclass
class Match:
    """Bracket match."""

    id: int
    tournament_id: int
    round: int
    match_index: int
    entry1_id: Optional[int] = None
    entry2_id: Optional[int] = None  # None = BYE
    winner_entry_id: Optional[int] = None
    score_text: Optional[str] = None
    status: str = "pending"
    pending_winner_entry_id: Optional[int] = None  # Awaiting confirmation
    pending_reported_by: Optional[int] = None  # Who reported first


# -----------------------------------------------------------------------------
# Tournament Service
# -----------------------------------------------------------------------------


class TournamentService:
    """
    Service for managing Single Elimination tournaments.

    Provides:
    - Tournament creation with one-active-per-guild enforcement
    - Entry management for 1v1 and 2v2 formats
    - Status transitions
    """

    # Valid statuses for tournaments
    VALID_STATUSES = {
        "draft",
        "reg_open",
        "reg_closed",
        "in_progress",
        "completed",
        "cancelled",
    }
    ACTIVE_STATUSES = {"draft", "reg_open", "reg_closed", "in_progress"}

    # Tournament code alphabet (no confusing chars: 0/O, 1/I)
    CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    CODE_LENGTH = 8

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    # -------------------------------------------------------------------------
    # Tournament Code Helpers
    # -------------------------------------------------------------------------

    async def generate_unique_tournament_code(self) -> str:
        """Generate a unique 8-character tournament code."""
        import random

        while True:
            code = "".join(
                random.choice(self.CODE_ALPHABET) for _ in range(self.CODE_LENGTH)
            )
            cursor = await self.db.execute(
                "SELECT 1 FROM tournaments WHERE tournament_code = ?",
                (code,),
            )
            row = await cursor.fetchone()
            if row is None:
                return code

    async def get_by_code(self, code: str) -> Optional[Tournament]:
        """Get tournament by its human-friendly code."""
        cursor = await self.db.execute(
            "SELECT * FROM tournaments WHERE tournament_code = ?",
            (code.upper(),),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_tournament(row)

    async def get_by_code_or_id(self, code_or_id: str) -> Optional[Tournament]:
        """
        Get tournament by code (preferred) or integer ID (fallback).

        Useful for dev commands that accept either format.
        """
        # Try as code first
        tournament = await self.get_by_code(code_or_id.upper())
        if tournament:
            return tournament

        # Try as integer ID
        try:
            tournament_id = int(code_or_id)
            return await self.get_by_id(tournament_id)
        except ValueError:
            return None

    # -------------------------------------------------------------------------
    # Tournament CRUD
    # -------------------------------------------------------------------------

    async def create_tournament(
        self,
        guild_id: int,
        name: str,
        format: str,
        size: int,
        allowed_regions: Optional[str] = None,
        allowed_ranks: Optional[str] = None,
    ) -> tuple[Optional[Tournament], Optional[str]]:
        """
        Create a new tournament.

        Returns: (Tournament, None) on success, (None, error_message) on failure.

        Enforces one active tournament per guild.

        Args:
            allowed_regions: Optional CSV like "USE,EU"
            allowed_ranks: Optional CSV like "Gold,Platinum"
        """
        # Validate format
        if format not in ("1v1", "2v2"):
            return None, f"Invalid format: {format}. Must be '1v1' or '2v2'."

        # Validate size
        if size not in (8, 16, 32, 64):
            return None, f"Invalid size: {size}. Must be 8, 16, 32, or 64."

        # Check for existing active tournament
        existing = await self.get_active_for_guild(guild_id)
        if existing:
            return (
                None,
                f"You already have an active tournament: **{existing.name}** (status: {existing.status})",
            )

        try:
            # Generate unique tournament code
            tournament_code = await self.generate_unique_tournament_code()

            now = int(time.time())
            cursor = await self.db.execute(
                """
                INSERT INTO tournaments (
                    guild_id, name, tournament_code, format, size, status,
                    allowed_regions, allowed_ranks, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)
                """,
                (
                    guild_id,
                    name,
                    tournament_code,
                    format,
                    size,
                    allowed_regions,
                    allowed_ranks,
                    now,
                ),
            )
            await self.db.commit()

            tournament_id = cursor.lastrowid
            log.info(
                f"[TOURNAMENT] Created tournament {tournament_id} (code={tournament_code}): {name} ({format}, size={size})"
            )

            return await self.get_by_id(tournament_id), None

        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to create tournament: {e}")
            return None, f"Database error: {e}"

    def _row_to_tournament(self, row) -> Tournament:
        """Convert a DB row to Tournament object."""
        return Tournament(
            id=row["id"],
            guild_id=row["guild_id"],
            name=row["name"],
            format=row["format"],
            size=row["size"],
            status=row["status"],
            tournament_code=(
                row["tournament_code"] if "tournament_code" in row.keys() else None
            ),
            reg_message_id=row["reg_message_id"],
            reg_channel_id=row["reg_channel_id"],
            allowed_regions=(
                row["allowed_regions"] if "allowed_regions" in row.keys() else None
            ),
            allowed_ranks=(
                row["allowed_ranks"] if "allowed_ranks" in row.keys() else None
            ),
            dashboard_channel_id=(
                row["dashboard_channel_id"]
                if "dashboard_channel_id" in row.keys()
                else None
            ),
            dashboard_message_id=(
                row["dashboard_message_id"]
                if "dashboard_message_id" in row.keys()
                else None
            ),
            created_at=row["created_at"],
        )

    def _row_to_match(self, row) -> Match:
        """Convert a DB row to Match object."""
        return Match(
            id=row["id"],
            tournament_id=row["tournament_id"],
            round=row["round"],
            match_index=row["match_index"],
            entry1_id=row["entry1_id"],
            entry2_id=row["entry2_id"],
            winner_entry_id=row["winner_entry_id"],
            score_text=row["score_text"],
            status=row["status"],
            pending_winner_entry_id=(
                row["pending_winner_entry_id"]
                if "pending_winner_entry_id" in row.keys()
                else None
            ),
            pending_reported_by=(
                row["pending_reported_by"]
                if "pending_reported_by" in row.keys()
                else None
            ),
        )

    @staticmethod
    def is_dummy_player_id(player_id: int) -> bool:
        """Check if a player ID is a dummy (synthetic ID for testing)."""
        # Dummy IDs are 9900000000000000+ (17 digits starting with 99)
        return player_id >= 9900000000000000

    async def get_by_id(self, tournament_id: int) -> Optional[Tournament]:
        """Get tournament by ID."""
        cursor = await self.db.execute(
            "SELECT * FROM tournaments WHERE id = ?",
            (tournament_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_tournament(row)

    async def get_active_for_guild(self, guild_id: int) -> Optional[Tournament]:
        """
        Get the active tournament for a guild.

        Active = status in (draft, reg_open, reg_closed, in_progress)
        """
        cursor = await self.db.execute(
            """
            SELECT * FROM tournaments
            WHERE guild_id = ? AND status IN ('draft', 'reg_open', 'reg_closed', 'in_progress')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (guild_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_tournament(row)

    async def set_status(
        self,
        tournament_id: int,
        status: str,
    ) -> bool:
        """Update tournament status."""
        if status not in self.VALID_STATUSES:
            log.error(f"[TOURNAMENT] Invalid status: {status}")
            return False

        try:
            await self.db.execute(
                "UPDATE tournaments SET status = ? WHERE id = ?",
                (status, tournament_id),
            )
            await self.db.commit()
            log.info(f"[TOURNAMENT] Tournament {tournament_id} status → {status}")
            return True
        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to update status: {e}")
            return False

    async def archive_tournament(
        self,
        tournament_id: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Archive a completed/cancelled tournament.

        - Preserves winner/runner-up trophy data
        - Deletes matches and entries
        - Marks status = 'archived'

        Returns: (success, error_message)
        """
        tournament = await self.get_by_id(tournament_id)
        if not tournament:
            return False, "Tournament not found."

        if tournament.status not in ("completed", "cancelled"):
            return False, "Only completed or cancelled tournaments can be archived."

        try:
            # First, determine winner and runner-up from final match
            winner_id = None
            runner_up_id = None
            completed_at = None

            matches = await self.list_matches(tournament_id)
            if matches:
                # Find the final match (highest round)
                final_match = max(matches, key=lambda m: m.round)
                if final_match.winner_entry_id:
                    # Get player ID from winner entry
                    cursor = await self.db.execute(
                        "SELECT player1_id FROM tournament_entries WHERE id = ?",
                        (final_match.winner_entry_id,),
                    )
                    row = await cursor.fetchone()
                    if row:
                        winner_id = row["player1_id"]

                    # Get runner-up (the loser of the final)
                    loser_entry_id = (
                        final_match.entry1_id
                        if final_match.winner_entry_id == final_match.entry2_id
                        else final_match.entry2_id
                    )
                    if loser_entry_id:
                        cursor = await self.db.execute(
                            "SELECT player1_id FROM tournament_entries WHERE id = ?",
                            (loser_entry_id,),
                        )
                        row = await cursor.fetchone()
                        if row:
                            runner_up_id = row["player1_id"]

            # Set completed_at timestamp
            import time

            completed_at = int(time.time())

            # Update tournament with trophy data and status
            await self.db.execute(
                """
                UPDATE tournaments
                SET status = 'archived',
                    winner_player_id = ?,
                    runner_up_player_id = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (winner_id, runner_up_id, completed_at, tournament_id),
            )

            # Delete entries
            await self.db.execute(
                "DELETE FROM tournament_entries WHERE tournament_id = ?",
                (tournament_id,),
            )

            # Delete matches
            await self.db.execute(
                "DELETE FROM matches WHERE tournament_id = ?",
                (tournament_id,),
            )

            await self.db.commit()

            log.info(
                f"[TOURNAMENT] Archived tournament {tournament_id}: "
                f"winner={winner_id}, runner_up={runner_up_id}"
            )

            return True, None

        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to archive tournament: {e}")
            return False, f"Database error: {e}"

    async def set_registration_message(
        self,
        tournament_id: int,
        message_id: int,
        channel_id: int,
    ) -> bool:
        """Store the registration message reference."""
        try:
            await self.db.execute(
                "UPDATE tournaments SET reg_message_id = ?, reg_channel_id = ? WHERE id = ?",
                (message_id, channel_id, tournament_id),
            )
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to set registration message: {e}")
            return False

    async def set_dashboard_message(
        self,
        tournament_id: int,
        channel_id: int,
        message_id: int,
    ) -> bool:
        """Store the dashboard message reference."""
        try:
            await self.db.execute(
                "UPDATE tournaments SET dashboard_channel_id = ?, dashboard_message_id = ? WHERE id = ?",
                (channel_id, message_id, tournament_id),
            )
            await self.db.commit()
            log.info(
                f"[TOURNAMENT] Set dashboard message for tournament {tournament_id}"
            )
            return True
        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to set dashboard message: {e}")
            return False

    # -------------------------------------------------------------------------
    # Entry Management
    # -------------------------------------------------------------------------

    async def add_entry_1v1(
        self,
        tournament_id: int,
        user_id: int,
    ) -> tuple[Optional[TournamentEntry], Optional[str]]:
        """
        Add a 1v1 entry.

        Returns: (TournamentEntry, None) on success, (None, error_message) on failure.
        """
        # Check if player already registered
        if await self.has_entry_for_player(tournament_id, user_id):
            return None, "You are already registered for this tournament."

        try:
            now = int(time.time())
            cursor = await self.db.execute(
                """
                INSERT INTO tournament_entries (tournament_id, player1_id, created_at)
                VALUES (?, ?, ?)
                """,
                (tournament_id, user_id, now),
            )
            await self.db.commit()

            entry_id = cursor.lastrowid
            log.info(f"[TOURNAMENT] Added 1v1 entry {entry_id}: player {user_id}")

            return (
                TournamentEntry(
                    id=entry_id,
                    tournament_id=tournament_id,
                    player1_id=user_id,
                    created_at=now,
                ),
                None,
            )

        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to add 1v1 entry: {e}")
            return None, f"Database error: {e}"

    async def add_dummy_entry(
        self,
        tournament_id: int,
        dummy_player_id: int,
    ) -> Optional[TournamentEntry]:
        """
        Add a dummy entry for dev/testing (skips duplicate check).

        Used by /ums_dev_fill_dummies command.
        """
        try:
            now = int(time.time())
            cursor = await self.db.execute(
                """
                INSERT INTO tournament_entries (tournament_id, player1_id, created_at)
                VALUES (?, ?, ?)
                """,
                (tournament_id, dummy_player_id, now),
            )
            await self.db.commit()

            entry_id = cursor.lastrowid
            log.info(f"[DEV] Added dummy entry {entry_id}: player {dummy_player_id}")

            return TournamentEntry(
                id=entry_id,
                tournament_id=tournament_id,
                player1_id=dummy_player_id,
                created_at=now,
            )

        except Exception as e:
            log.error(f"[DEV] Failed to add dummy entry: {e}")
            return None

    async def add_entry_2v2(
        self,
        tournament_id: int,
        player1_id: int,
        player2_id: int,
        team_name: Optional[str] = None,
    ) -> tuple[Optional[TournamentEntry], Optional[str]]:
        """
        Add a 2v2 entry.

        Returns: (TournamentEntry, None) on success, (None, error_message) on failure.
        """
        if player1_id == player2_id:
            return None, "You cannot team with yourself."

        # Check if either player is already registered
        if await self.has_entry_for_player(tournament_id, player1_id):
            return None, "You are already registered for this tournament."

        if await self.has_entry_for_player(tournament_id, player2_id):
            return None, "Your teammate is already registered for this tournament."

        # Default team name if not provided
        if not team_name:
            team_name = f"Team {player1_id}"

        try:
            now = int(time.time())
            cursor = await self.db.execute(
                """
                INSERT INTO tournament_entries (tournament_id, player1_id, player2_id, team_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tournament_id, player1_id, player2_id, team_name, now),
            )
            await self.db.commit()

            entry_id = cursor.lastrowid
            log.info(
                f"[TOURNAMENT] Added 2v2 entry {entry_id}: {team_name} (p1={player1_id}, p2={player2_id})"
            )

            return (
                TournamentEntry(
                    id=entry_id,
                    tournament_id=tournament_id,
                    player1_id=player1_id,
                    player2_id=player2_id,
                    team_name=team_name,
                    created_at=now,
                ),
                None,
            )

        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to add 2v2 entry: {e}")
            return None, f"Database error: {e}"

    async def has_entry_for_player(
        self,
        tournament_id: int,
        user_id: int,
    ) -> bool:
        """Check if a player is already registered in any entry."""
        cursor = await self.db.execute(
            """
            SELECT COUNT(*) FROM tournament_entries
            WHERE tournament_id = ? AND (player1_id = ? OR player2_id = ?)
            """,
            (tournament_id, user_id, user_id),
        )
        row = await cursor.fetchone()
        return row[0] > 0

    async def list_entries(
        self,
        tournament_id: int,
    ) -> List[TournamentEntry]:
        """List all entries for a tournament."""
        cursor = await self.db.execute(
            """
            SELECT * FROM tournament_entries
            WHERE tournament_id = ?
            ORDER BY created_at ASC
            """,
            (tournament_id,),
        )
        rows = await cursor.fetchall()

        return [
            TournamentEntry(
                id=row["id"],
                tournament_id=row["tournament_id"],
                player1_id=row["player1_id"],
                player2_id=row["player2_id"],
                team_name=row["team_name"],
                seed=row["seed"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def count_entries(self, tournament_id: int) -> int:
        """Count entries for a tournament."""
        cursor = await self.db.execute(
            "SELECT COUNT(*) FROM tournament_entries WHERE tournament_id = ?",
            (tournament_id,),
        )
        row = await cursor.fetchone()
        return row[0]

    async def remove_entry(
        self,
        tournament_id: int,
        user_id: int,
    ) -> bool:
        """Remove a player's entry from a tournament."""
        try:
            await self.db.execute(
                """
                DELETE FROM tournament_entries
                WHERE tournament_id = ? AND (player1_id = ? OR player2_id = ?)
                """,
                (tournament_id, user_id, user_id),
            )
            await self.db.commit()
            log.info(
                f"[TOURNAMENT] Removed entry for player {user_id} from tournament {tournament_id}"
            )
            return True
        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to remove entry: {e}")
            return False

    # -------------------------------------------------------------------------
    # Bracket Generation
    # -------------------------------------------------------------------------

    async def build_bracket(
        self,
        tournament_id: int,
    ) -> tuple[List[Match], Optional[str]]:
        """
        Build the SE bracket for a tournament.

        1. Get all entries
        2. Shuffle them
        3. Pad with BYEs to reach tournament size
        4. Create round 1 matches

        Returns: (list of matches, error_message)
        """
        import random

        # Get tournament
        tournament = await self.get_by_id(tournament_id)
        if not tournament:
            return [], "Tournament not found."

        if tournament.status != "reg_closed":
            return (
                [],
                f"Cannot build bracket. Tournament status is '{tournament.status}'.",
            )

        # Get entries
        entries = await self.list_entries(tournament_id)

        if len(entries) < 2:
            return [], "Need at least 2 entries to start a tournament."

        # Shuffle entries
        random.shuffle(entries)

        # Create slots: entries + BYEs to fill bracket
        bracket_size = tournament.size
        slots = [entry.id for entry in entries]

        # Pad with BYEs (None values) to reach bracket size
        while len(slots) < bracket_size:
            slots.append(None)  # BYE

        # Create first-round matches
        # In an SE bracket, round 1 has size/2 matches
        num_matches = bracket_size // 2
        matches = []

        try:
            for i in range(num_matches):
                entry1_id = slots[i * 2]
                entry2_id = slots[i * 2 + 1]

                # Determine initial status
                # If one side is a BYE, the match is auto-completed
                if entry1_id is None and entry2_id is None:
                    # Both BYEs - shouldn't happen in a valid bracket
                    status = "completed"
                    winner_id = None
                elif entry1_id is None:
                    # entry1 is BYE, entry2 advances
                    status = "completed"
                    winner_id = entry2_id
                elif entry2_id is None:
                    # entry2 is BYE, entry1 advances
                    status = "completed"
                    winner_id = entry1_id
                else:
                    # Normal match
                    status = "pending"
                    winner_id = None

                cursor = await self.db.execute(
                    """
                    INSERT INTO matches (
                        tournament_id, round, match_index,
                        entry1_id, entry2_id, winner_entry_id, status
                    ) VALUES (?, 1, ?, ?, ?, ?, ?)
                    """,
                    (tournament_id, i, entry1_id, entry2_id, winner_id, status),
                )

                match_id = cursor.lastrowid
                matches.append(
                    Match(
                        id=match_id,
                        tournament_id=tournament_id,
                        round=1,
                        match_index=i,
                        entry1_id=entry1_id,
                        entry2_id=entry2_id,
                        winner_entry_id=winner_id,
                        status=status,
                    )
                )

            await self.db.commit()

            log.info(
                f"[TOURNAMENT] Built bracket for tournament {tournament_id}: "
                f"{len(entries)} entries, {num_matches} round 1 matches"
            )

            return matches, None

        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to build bracket: {e}")
            return [], f"Database error: {e}"

    # -------------------------------------------------------------------------
    # Match Management
    # -------------------------------------------------------------------------

    async def list_matches(
        self,
        tournament_id: int,
        round_num: Optional[int] = None,
    ) -> List[Match]:
        """List matches for a tournament, optionally filtered by round."""
        if round_num:
            cursor = await self.db.execute(
                """
                SELECT * FROM matches
                WHERE tournament_id = ? AND round = ?
                ORDER BY match_index ASC
                """,
                (tournament_id, round_num),
            )
        else:
            cursor = await self.db.execute(
                """
                SELECT * FROM matches
                WHERE tournament_id = ?
                ORDER BY round ASC, match_index ASC
                """,
                (tournament_id,),
            )

        rows = await cursor.fetchall()

        return [self._row_to_match(row) for row in rows]

    async def get_match(self, match_id: int) -> Optional[Match]:
        """Get a match by ID."""
        cursor = await self.db.execute(
            "SELECT * FROM matches WHERE id = ?",
            (match_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_match(row)

    async def find_active_match_for_player(
        self,
        tournament_id: int,
        player_id: int,
    ) -> Optional[Match]:
        """
        Find a player's active (pending) match in a tournament.

        Returns the pending match if the player has one, None otherwise.
        """
        # First, get the player's entry
        entry = await self.get_entry_for_player(tournament_id, player_id)
        if not entry:
            return None

        # Find pending match where this entry is a participant
        cursor = await self.db.execute(
            """
            SELECT * FROM matches
            WHERE tournament_id = ?
            AND status = 'pending'
            AND (entry1_id = ? OR entry2_id = ?)
            LIMIT 1
            """,
            (tournament_id, entry.id, entry.id),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_match(row)

    async def get_entry_display_name(
        self,
        entry_id: int,
        tournament_format: str,
    ) -> str:
        """Get a display name for an entry."""
        cursor = await self.db.execute(
            "SELECT * FROM tournament_entries WHERE id = ?",
            (entry_id,),
        )
        row = await cursor.fetchone()

        if not row:
            return f"Entry #{entry_id}"

        if tournament_format == "2v2" and row["team_name"]:
            return row["team_name"]

        return f"<@{row['player1_id']}>"

    async def get_match_player_ids(self, match_id: int) -> List[int]:
        """
        Get all Discord user IDs for players in a match.

        For 1v1: returns [player1_id, player2_id]
        For 2v2: returns [team1_player1, team1_player2, team2_player1, team2_player2]
        """
        match = await self.get_match(match_id)
        if not match:
            return []

        player_ids = []

        # Get entry1 players
        if match.entry1_id:
            cursor = await self.db.execute(
                "SELECT player1_id, player2_id FROM tournament_entries WHERE id = ?",
                (match.entry1_id,),
            )
            row = await cursor.fetchone()
            if row:
                player_ids.append(row["player1_id"])
                if row["player2_id"]:
                    player_ids.append(row["player2_id"])

        # Get entry2 players
        if match.entry2_id:
            cursor = await self.db.execute(
                "SELECT player1_id, player2_id FROM tournament_entries WHERE id = ?",
                (match.entry2_id,),
            )
            row = await cursor.fetchone()
            if row:
                player_ids.append(row["player1_id"])
                if row["player2_id"]:
                    player_ids.append(row["player2_id"])

        return player_ids

    async def get_entry_player_id(self, entry_id: int) -> Optional[int]:
        """Get the primary player ID for an entry (player1_id)."""
        cursor = await self.db.execute(
            "SELECT player1_id FROM tournament_entries WHERE id = ?",
            (entry_id,),
        )
        row = await cursor.fetchone()
        return row["player1_id"] if row else None

    async def is_dummy_match(self, match_id: int) -> tuple[bool, bool, bool]:
        """
        Check if a match involves dummies.

        Returns: (entry1_is_dummy, entry2_is_dummy, both_are_dummies)
        """
        match = await self.get_match(match_id)
        if not match:
            return False, False, False

        entry1_player = (
            await self.get_entry_player_id(match.entry1_id) if match.entry1_id else None
        )
        entry2_player = (
            await self.get_entry_player_id(match.entry2_id) if match.entry2_id else None
        )

        entry1_dummy = entry1_player is not None and self.is_dummy_player_id(
            entry1_player
        )
        entry2_dummy = entry2_player is not None and self.is_dummy_player_id(
            entry2_player
        )

        return entry1_dummy, entry2_dummy, entry1_dummy and entry2_dummy

    async def auto_resolve_dummy_match(
        self,
        match_id: int,
    ) -> tuple[Optional["Tournament"], Optional[Match], Optional[str]]:
        """
        Auto-resolve a dummy vs dummy match with random winner.

        Only works if BOTH players are dummies.
        Returns: (tournament, match, error)
        """
        import random

        match = await self.get_match(match_id)
        if not match:
            return None, None, "Match not found."

        if match.status != "pending":
            return None, None, "Match already completed."

        entry1_dummy, entry2_dummy, both_dummy = await self.is_dummy_match(match_id)

        if not both_dummy:
            return None, None, "Can only auto-resolve dummy vs dummy matches."

        # Random winner
        winner_entry_id = random.choice([match.entry1_id, match.entry2_id])

        return await self.report_result_by_entry(
            match_id=match_id,
            winner_entry_id=winner_entry_id,
            score="AUTO",
        )

    # -------------------------------------------------------------------------
    # Result Reporting
    # -------------------------------------------------------------------------

    async def get_entry_for_player(
        self,
        tournament_id: int,
        player_id: int,
    ) -> Optional[TournamentEntry]:
        """Get entry for a player in a tournament."""
        cursor = await self.db.execute(
            """
            SELECT * FROM tournament_entries
            WHERE tournament_id = ? AND (player1_id = ? OR player2_id = ?)
            """,
            (tournament_id, player_id, player_id),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return TournamentEntry(
            id=row["id"],
            tournament_id=row["tournament_id"],
            player1_id=row["player1_id"],
            player2_id=row["player2_id"],
            team_name=row["team_name"],
            seed=row["seed"],
            created_at=row["created_at"],
        )

    async def find_match_for_players(
        self,
        tournament_id: int,
        player1_id: int,
        player2_id: int,
    ) -> Optional[Match]:
        """
        Find a pending match between two players.

        Looks up both players' entries and finds any pending match
        where those entries face each other (in either order).
        """
        # Get entries for both players
        entry1 = await self.get_entry_for_player(tournament_id, player1_id)
        entry2 = await self.get_entry_for_player(tournament_id, player2_id)

        if not entry1 or not entry2:
            return None

        # Find pending match with these entries
        cursor = await self.db.execute(
            """
            SELECT * FROM matches
            WHERE tournament_id = ?
              AND status = 'pending'
              AND (
                  (entry1_id = ? AND entry2_id = ?)
                  OR (entry1_id = ? AND entry2_id = ?)
              )
            """,
            (tournament_id, entry1.id, entry2.id, entry2.id, entry1.id),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return Match(
            id=row["id"],
            tournament_id=row["tournament_id"],
            round=row["round"],
            match_index=row["match_index"],
            entry1_id=row["entry1_id"],
            entry2_id=row["entry2_id"],
            winner_entry_id=row["winner_entry_id"],
            score_text=row["score_text"],
            status=row["status"],
        )

    async def report_result(
        self,
        guild_id: int,
        winner_id: int,
        loser_id: int,
        score: Optional[str] = None,
        tournament_id: Optional[int] = None,
    ) -> tuple[Optional[Tournament], Optional[Match], Optional[str]]:
        """
        Report a match result.

        Args:
            guild_id: The guild ID
            winner_id: Discord ID of winner
            loser_id: Discord ID of loser
            score: Optional score text (e.g., "2-1")
            tournament_id: Optional tournament ID (auto-resolves if None)

        Returns:
            (Tournament, Match, None) on success
            (None, None, error_message) on failure
        """
        # Resolve tournament
        if tournament_id:
            tournament = await self.get_by_id(tournament_id)
        else:
            tournament = await self.get_active_for_guild(guild_id)

        if not tournament:
            return None, None, "No active tournament found."

        if tournament.status != "in_progress":
            return (
                None,
                None,
                f"Tournament is not in progress (status: {tournament.status}).",
            )

        # Find the match
        match = await self.find_match_for_players(tournament.id, winner_id, loser_id)

        if not match:
            return None, None, "No pending match found between these players."

        # Get winner's entry
        winner_entry = await self.get_entry_for_player(tournament.id, winner_id)
        if not winner_entry:
            return None, None, "Winner not found in tournament entries."

        try:
            # Update match
            await self.db.execute(
                """
                UPDATE matches
                SET status = 'completed',
                    winner_entry_id = ?,
                    score_text = ?
                WHERE id = ?
                """,
                (winner_entry.id, score, match.id),
            )
            await self.db.commit()

            # Update match object
            match.status = "completed"
            match.winner_entry_id = winner_entry.id
            match.score_text = score

            log.info(
                f"[TOURNAMENT] Match {match.id} completed: winner={winner_id}, "
                f"score={score}, tournament={tournament.id}"
            )

            # Advance bracket
            await self._advance_single_elim(tournament.id)

            # Refresh tournament status
            tournament = await self.get_by_id(tournament.id)

            return tournament, match, None

        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to report result: {e}")
            return None, None, f"Database error: {e}"

    async def report_result_by_entry(
        self,
        match_id: int,
        winner_entry_id: int,
        score: Optional[str] = None,
    ) -> tuple[Optional[Tournament], Optional[Match], Optional[str]]:
        """
        Report a match result by entry ID (for button-based reporting).

        Args:
            match_id: The match ID
            winner_entry_id: Entry ID of the winner
            score: Optional score text

        Returns:
            (Tournament, Match, None) on success
            (None, None, error_message) on failure
        """
        # Get match
        match = await self.get_match(match_id)
        if not match:
            return None, None, "Match not found."

        if match.status != "pending":
            return None, None, "Match has already been completed."

        # Validate winner is one of the entries
        if winner_entry_id not in (match.entry1_id, match.entry2_id):
            return None, None, "Winner is not a participant in this match."

        # Get tournament
        tournament = await self.get_by_id(match.tournament_id)
        if not tournament:
            return None, None, "Tournament not found."

        try:
            # Update match
            await self.db.execute(
                """
                UPDATE matches
                SET status = 'completed',
                    winner_entry_id = ?,
                    score_text = ?
                WHERE id = ?
                """,
                (winner_entry_id, score, match_id),
            )
            await self.db.commit()

            # Update match object
            match.status = "completed"
            match.winner_entry_id = winner_entry_id
            match.score_text = score

            log.info(
                f"[TOURNAMENT] Match {match_id} completed via button: winner_entry={winner_entry_id}"
            )

            # Advance bracket
            await self._advance_single_elim(tournament.id)

            # Refresh tournament status
            tournament = await self.get_by_id(tournament.id)

            return tournament, match, None

        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to report result by entry: {e}")
            return None, None, f"Database error: {e}"

    async def _advance_single_elim(self, tournament_id: int) -> None:
        """
        Advance the single elimination bracket.

        If all matches in the current round are completed:
        1. Generate next round matches
        2. If final is completed, mark tournament as completed
        """
        tournament = await self.get_by_id(tournament_id)
        if not tournament:
            return

        # Get all matches
        matches = await self.list_matches(tournament_id)
        if not matches:
            return

        # Find current (latest) round
        current_round = max(m.round for m in matches)
        round_matches = [m for m in matches if m.round == current_round]

        # Check if all matches in current round are completed
        pending = [m for m in round_matches if m.status == "pending"]
        if pending:
            # Still have pending matches in current round
            return

        # All matches completed - get winners
        winners = [m.winner_entry_id for m in round_matches if m.winner_entry_id]

        # If only 1 winner left, tournament is complete
        if len(winners) <= 1:
            await self.set_status(tournament_id, "completed")
            log.info(f"[TOURNAMENT] Tournament {tournament_id} completed!")
            return

        # Create next round matches
        next_round = current_round + 1
        num_matches = len(winners) // 2

        try:
            for i in range(num_matches):
                entry1_id = winners[i * 2]
                entry2_id = winners[i * 2 + 1] if i * 2 + 1 < len(winners) else None

                # If one is a BYE (shouldn't happen in later rounds normally)
                if entry2_id is None:
                    status = "completed"
                    winner_id = entry1_id
                else:
                    status = "pending"
                    winner_id = None

                await self.db.execute(
                    """
                    INSERT INTO matches (
                        tournament_id, round, match_index,
                        entry1_id, entry2_id, winner_entry_id, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tournament_id,
                        next_round,
                        i,
                        entry1_id,
                        entry2_id,
                        winner_id,
                        status,
                    ),
                )

            await self.db.commit()
            log.info(
                f"[TOURNAMENT] Advanced to round {next_round} with {num_matches} matches"
            )

        except Exception as e:
            log.error(f"[TOURNAMENT] Failed to advance bracket: {e}")
